"""Synthetic regressions for project-mapped series power paths."""

from __future__ import annotations

import hashlib
import unittest

from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PowerPathElementRequirement,
    PowerPathEndpointRequirement,
    PowerPathMap,
    PowerPathRequirement,
)
from kicad_tooling.hwrepo.power_paths import power_path_mismatches

RULE_ID = "power.mapped_series_path_mismatch"


def power_path_map(*, two_elements: bool = False) -> PowerPathMap:
    elements = [
        PowerPathElementRequirement(
            reference="FB1",
            symbol="Device:FerriteBead",
            footprint="Synthetic:0603",
            side_a_pin="FB1.1",
            side_b_pin="FB1.2",
            side_a_net="VIN",
            side_b_net="VPROTECTED" if two_elements else "VLOAD",
        )
    ]
    end_net = "VLOAD"
    if two_elements:
        elements.append(
            PowerPathElementRequirement(
                reference="F1",
                symbol="Device:Fuse",
                footprint="Synthetic:1206",
                side_a_pin="F1.1",
                side_b_pin="F1.2",
                side_a_net="VPROTECTED",
                side_b_net="VLOAD",
            )
        )
    return PowerPathMap(
        basis="Synthetic reviewed source-to-load path requirement",
        paths=(
            PowerPathRequirement(
                id="input-to-controller",
                basis="Synthetic power tree requires the fitted bead and optional fuse",
                start=PowerPathEndpointRequirement(
                    reference="J1",
                    pin="J1.1",
                    symbol="Synthetic:PowerInput",
                    footprint="Synthetic:Conn2",
                    net="VIN",
                ),
                end=PowerPathEndpointRequirement(
                    reference="U1",
                    pin="U1.3",
                    symbol="Synthetic:Controller",
                    footprint="Synthetic:QFN",
                    net=end_net,
                ),
                elements=tuple(elements),
            ),
        ),
    )


def power_path_netlist(*, fault: str | None = None, two_elements: bool = False) -> NetlistContract:
    components = {
        "J1": ComponentContract(value="Synthetic source", footprint="Synthetic:Conn2"),
        "FB1": ComponentContract(value="Ferrite bead", footprint="Synthetic:0603"),
        "U1": ComponentContract(value="Synthetic controller", footprint="Synthetic:QFN"),
    }
    symbols = {
        "J1": "Synthetic:PowerInput",
        "FB1": "Device:FerriteBead",
        "U1": "Synthetic:Controller",
    }
    pin_numbers = {"J1": ("1", "2"), "FB1": ("1", "2"), "U1": ("1", "2", "3")}
    nets: dict[str, tuple[str, ...]] = {
        "VIN": ("J1.1", "FB1.1"),
        "VLOAD": ("FB1.2", "U1.3"),
    }
    dnp: tuple[str, ...] = ()
    if two_elements:
        components["F1"] = ComponentContract(value="2A fuse", footprint="Synthetic:1206")
        symbols["F1"] = "Device:Fuse"
        pin_numbers["F1"] = ("1", "2")
        nets["VLOAD"] = ("F1.2", "U1.3")
        nets["VPROTECTED"] = ("FB1.2", "F1.1")
    if fault == "open-source":
        nets["VIN"] = ("FB1.1",)
    elif fault == "open-element":
        if two_elements:
            nets["VLOAD"] = ("F1.2", "U1.3")
            nets["VPROTECTED"] = ("FB1.2",)
            nets["FLOATING"] = ("F1.1",)
        else:
            nets["VLOAD"] = ("U1.3",)
            nets["FLOATING"] = ("FB1.2",)
    elif fault == "open-load":
        nets["VLOAD"] = tuple(pin for pin in nets["VLOAD"] if pin != "U1.3")
        nets["FLOATING"] = ("U1.3",)
    elif fault == "dnp-element":
        dnp = ("F1" if two_elements else "FB1",)
    elif fault == "wrong-element-symbol":
        symbols["FB1"] = "Device:L"
    elif fault == "extra-element-pin":
        pin_numbers["FB1"] = ("1", "2", "3")
    elif fault == "bypassed-element":
        nets["VIN"] = ("J1.1", "FB1.1", "FB1.2")
        if two_elements:
            nets["VPROTECTED"] = ("F1.1",)
        else:
            nets["VLOAD"] = ("U1.3",)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def lint_report(
    netlist: NetlistContract,
    path_map: PowerPathMap | None = None,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-power-path",
        observed=netlist,
        netlist_sha256=hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest(),
    )
    return evaluate(
        "synthetic-power-path",
        coach,
        DesignLintPolicy(
            power_path_map=path_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )


class PowerPathTests(unittest.TestCase):
    def test_reviewed_ferrite_and_multistage_paths_pass(self) -> None:
        for two_elements in (False, True):
            with self.subTest(two_elements=two_elements):
                report = lint_report(
                    power_path_netlist(two_elements=two_elements),
                    power_path_map(two_elements=two_elements),
                )
                self.assertEqual(report.status, "PASS", report.issues)
                self.assertNotIn(RULE_ID, {item.rule_id for item in report.findings})
                run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
                expected_map_sha = hashlib.sha256(
                    power_path_map(two_elements=two_elements).model_dump_json().encode("utf-8")
                ).hexdigest()
                self.assertEqual(run.status, "EVALUATED")
                self.assertEqual(run.map_sha256, expected_map_sha)
                self.assertEqual(run.netlist_sha256, report.netlist_sha256)
                self.assertEqual(run.requirement_count, 1)
                self.assertEqual(run.finding_count, 0)
                rendered = text_report(report)
                self.assertIn("Mapped topology check runs:", rendered)
                self.assertIn(
                    f"{RULE_ID}: EVALUATED (mode: review; 1 authored item(s), 0 finding(s))",
                    rendered,
                )

    def test_missing_endpoint_element_dnp_identity_and_bypass_faults_are_reported(self) -> None:
        cases = (
            ("open-source", "J1.1 is assigned to unconnected"),
            ("open-element", "FB1.2 is assigned to FLOATING"),
            ("open-load", "U1.3 is assigned to FLOATING"),
            ("dnp-element", "FB1 is marked DNP"),
            ("wrong-element-symbol", "FB1 symbol is Device:L"),
            ("extra-element-pin", "FB1 has 3 native pins"),
            ("bypassed-element", "FB1.2 is assigned to VIN"),
        )
        for fault, expected_issue in cases:
            with self.subTest(fault=fault):
                report = lint_report(power_path_netlist(fault=fault), power_path_map())
                self.assertEqual(report.status, "REVIEW")
                run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
                self.assertEqual(run.status, "EVALUATED")
                self.assertEqual(run.finding_count, 1)
                finding = next(item for item in report.findings if item.rule_id == RULE_ID)
                self.assertTrue(
                    any(expected_issue in issue for issue in finding.evidence["issues"]),
                    finding.evidence["issues"],
                )
                self.assertEqual(finding.evidence["start_endpoint"], ("J1.1 on VIN",))
                self.assertEqual(finding.evidence["end_endpoint"], ("U1.3 on VLOAD",))
                self.assertIn("does not establish component conduction", finding.message)

    def test_two_stage_path_detects_open_fuse_and_dnp_fuse(self) -> None:
        for fault, expected_issue in (
            ("open-element", "F1.1 is assigned to FLOATING"),
            ("dnp-element", "F1 is marked DNP"),
        ):
            with self.subTest(fault=fault):
                mismatches = power_path_mismatches(
                    power_path_map(two_elements=True),
                    power_path_netlist(fault=fault, two_elements=True),
                )
                self.assertEqual(len(mismatches), 1)
                self.assertTrue(
                    any(expected_issue in issue for issue in mismatches[0].issues),
                    mismatches[0].issues,
                )
                self.assertEqual(len(mismatches[0].elements), 2)

    def test_rule_uses_review_block_off_and_exact_ignore_lifecycle(self) -> None:
        fault_netlist = power_path_netlist(fault="open-element")
        path_map = power_path_map()
        blocked = lint_report(
            fault_netlist,
            path_map,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="Synthetic release policy requires this reviewed input path",
            ),
        )
        self.assertEqual(blocked.status, "FAIL")
        finding = next(
            item
            for item in lint_report(fault_netlist, path_map).findings
            if item.rule_id == RULE_ID
        )
        ignored = lint_report(
            fault_netlist,
            path_map,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic test records the reviewed assembly exception",
            ),
        )
        self.assertEqual(
            next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition,
            "IGNORED",
        )
        disabled = lint_report(
            fault_netlist,
            path_map,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="Synthetic alternate configuration is checked by another contract",
            ),
        )
        self.assertEqual(
            next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition,
            "RULE_OFF",
        )
        disabled_run = next(item for item in disabled.mapped_check_runs if item.rule_id == RULE_ID)
        self.assertEqual((disabled_run.status, disabled_run.mode), ("EVALUATED", "off"))
        self.assertEqual(disabled_run.finding_count, 1)

    def test_unconfigured_and_unbound_maps_have_explicit_execution_states(self) -> None:
        without_map = lint_report(power_path_netlist())
        unconfigured = next(
            item for item in without_map.mapped_check_runs if item.rule_id == RULE_ID
        )
        self.assertEqual(unconfigured.status, "NOT_CONFIGURED")
        self.assertIsNone(unconfigured.map_sha256)
        self.assertEqual(unconfigured.requirement_count, 0)
        self.assertIn("No project-authored map", unconfigured.reason or "")

        unbound_coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-power-path",
            observed=power_path_netlist(),
        )
        unbound = evaluate(
            "synthetic-power-path",
            unbound_coach,
            DesignLintPolicy(power_path_map=power_path_map()),
        )
        blocked = next(item for item in unbound.mapped_check_runs if item.rule_id == RULE_ID)
        self.assertEqual(unbound.status, "BLOCKED")
        self.assertEqual(blocked.status, "BLOCKED")
        self.assertEqual(blocked.requirement_count, 1)
        self.assertIn("no source-bound SHA-256", blocked.reason or "")

    def test_map_order_is_stable_and_fixing_path_clears_finding(self) -> None:
        faulty = power_path_netlist(fault="open-element")
        path_map = power_path_map()
        report = lint_report(faulty, path_map)
        original = next(item for item in report.findings if item.rule_id == RULE_ID)
        reordered = faulty.model_copy(update={"nets": dict(reversed(tuple(faulty.nets.items())))})
        reordered_report = lint_report(reordered, path_map)
        reordered_finding = next(
            item for item in reordered_report.findings if item.rule_id == RULE_ID
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original.fingerprint, original.evidence),
        )

        unrelated = faulty.model_copy(
            update={
                "components": {
                    **faulty.components,
                    "R3": ComponentContract(value="10k", footprint="Synthetic:R_0603"),
                },
                "nets": {
                    **faulty.nets,
                    "+3V3": ("R3.1",),
                    "GND": ("R3.2",),
                },
                "component_symbols": {**faulty.component_symbols, "R3": "Device:R"},
                "component_pin_numbers": {
                    **faulty.component_pin_numbers,
                    "R3": ("1", "2"),
                },
            }
        )
        unrelated_report = lint_report(unrelated, path_map)
        unrelated_finding = next(
            item for item in unrelated_report.findings if item.rule_id == RULE_ID
        )
        self.assertNotEqual(unrelated_report.netlist_sha256, report.netlist_sha256)
        self.assertEqual(
            (unrelated_finding.fingerprint, unrelated_finding.evidence),
            (original.fingerprint, original.evidence),
        )
        original_run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
        unrelated_run = next(
            item for item in unrelated_report.mapped_check_runs if item.rule_id == RULE_ID
        )
        self.assertEqual(unrelated_run.netlist_sha256, unrelated_report.netlist_sha256)
        self.assertNotEqual(unrelated_run.netlist_sha256, original_run.netlist_sha256)
        self.assertEqual(unrelated_run.map_sha256, original_run.map_sha256)

        exact_ignore = DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=original.fingerprint,
            reason="Synthetic review accepts this explicit source-to-load path exception",
        )
        for candidate in (faulty, unrelated):
            ignored_report = lint_report(candidate, path_map, ignore=exact_ignore)
            ignored_finding = next(
                item for item in ignored_report.findings if item.rule_id == RULE_ID
            )
            self.assertEqual(ignored_finding.fingerprint, original.fingerprint)
            self.assertEqual(ignored_finding.disposition, "IGNORED")

        fixed = lint_report(power_path_netlist(), path_map)
        self.assertNotIn(RULE_ID, {item.rule_id for item in fixed.findings})

    def test_map_rejects_discontinuous_or_reused_component_paths(self) -> None:
        raw = power_path_map().model_dump(mode="python")
        raw["paths"][0]["elements"][0]["side_a_net"] = "OTHER"
        with self.assertRaisesRegex(ValidationError, "ordered net chain"):
            PowerPathMap.model_validate(raw)

        raw = power_path_map().model_dump(mode="python")
        raw["paths"][0]["elements"][0]["reference"] = "J1"
        raw["paths"][0]["elements"][0]["side_a_pin"] = "J1.2"
        raw["paths"][0]["elements"][0]["side_b_pin"] = "J1.3"
        with self.assertRaisesRegex(ValidationError, "references must be unique"):
            PowerPathMap.model_validate(raw)


if __name__ == "__main__":
    unittest.main()
