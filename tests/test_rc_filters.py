"""Synthetic regressions for explicitly mapped first-order RC filters."""

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
    RcFilterMap,
    RcFilterRequirement,
)


def rc_filter_map() -> RcFilterMap:
    return RcFilterMap(
        filters=(
            RcFilterRequirement(
                id="sensor-input",
                resistor_reference="R1",
                expected_resistor_symbol="Device:R",
                expected_resistor_footprint="Synthetic:0603",
                resistor_first_pin="R1.1",
                resistor_second_pin="R1.2",
                capacitor_reference="C1",
                expected_capacitor_symbol="Device:C",
                expected_capacitor_footprint="Synthetic:0603",
                capacitor_signal_pin="C1.1",
                capacitor_reference_pin="C1.2",
                input_net="FILTER_IN",
                filtered_net="FILTER_OUT",
                reference_net="GND",
                minimum_nominal_resistance_ohms=900,
                maximum_nominal_resistance_ohms=1100,
                minimum_nominal_capacitance_pf=90000,
                maximum_nominal_capacitance_pf=110000,
                minimum_target_corner_hz=1500,
                maximum_target_corner_hz=1700,
                basis="Synthetic interface timing requirement and reviewed RC topology",
            ),
        ),
    )


def rc_filter_netlist(
    *,
    resistor_value: str = "1k",
    capacitor_value: str = "100nF",
    fault: str | None = None,
) -> NetlistContract:
    components = {
        "R1": ComponentContract(value=resistor_value, footprint="Synthetic:0603"),
        "C1": ComponentContract(value=capacitor_value, footprint="Synthetic:0603"),
    }
    symbols = {"R1": "Device:R", "C1": "Device:C"}
    pin_numbers = {"R1": ("1", "2"), "C1": ("1", "2")}
    nets: dict[str, tuple[str, ...]] = {
        "FILTER_IN": ("R1.1",),
        "FILTER_OUT": ("R1.2", "C1.1"),
        "GND": ("C1.2",),
    }
    dnp: tuple[str, ...] = ()
    if fault == "wrong-capacitor-net":
        nets["FILTER_OUT"] = ("R1.2",)
        nets["OTHER_FILTER"] = ("C1.1",)
    elif fault == "disconnected-capacitor-return":
        nets.pop("GND")
    elif fault == "dnp-capacitor":
        dnp = ("C1",)
    elif fault == "missing-capacitor-component":
        components.pop("C1")
        symbols.pop("C1")
        pin_numbers.pop("C1")
    elif fault == "missing-capacitor-pin-inventory":
        pin_numbers.pop("C1")
    elif fault == "unsupported-resistor-value":
        components["R1"] = ComponentContract(value="top", footprint="Synthetic:0603")
    elif fault == "wrong-capacitor-symbol":
        symbols["C1"] = "Device:LED"
    elif fault == "wrong-resistor-footprint":
        components["R1"] = ComponentContract(value=resistor_value, footprint="Synthetic:QFN")
    elif fault == "unsupported-capacitor-value":
        components["C1"] = ComponentContract(value="filter-cap", footprint="Synthetic:0603")
    elif fault == "extra-parallel-capacitor":
        components["C2"] = ComponentContract(value="10nF", footprint="Synthetic:0603")
        symbols["C2"] = "Device:C"
        pin_numbers["C2"] = ("1", "2")
        nets["FILTER_OUT"] = (*nets["FILTER_OUT"], "C2.1")
        nets["GND"] = (*nets["GND"], "C2.2")
    elif fault == "extra-parallel-resistor":
        components["R2"] = ComponentContract(value="10k", footprint="Synthetic:0603")
        symbols["R2"] = "Device:R"
        pin_numbers["R2"] = ("1", "2")
        nets["FILTER_IN"] = (*nets["FILTER_IN"], "R2.1")
        nets["FILTER_OUT"] = (*nets["FILTER_OUT"], "R2.2")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def report(
    netlist: NetlistContract,
    filter_map: RcFilterMap | None = None,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
    netlist_sha256: str = "e" * 64,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-rc-filter",
        observed=netlist,
        netlist_sha256=netlist_sha256,
    )
    return evaluate(
        "synthetic-rc-filter",
        coach,
        DesignLintPolicy(
            rc_filter_map=filter_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )


class RcFilterTests(unittest.TestCase):
    def test_explicit_network_and_calculated_corner_pass(self) -> None:
        result = report(rc_filter_netlist(), rc_filter_map())
        self.assertEqual(result.status, "PASS", result.issues)
        coverage = result.rc_filter_coverage
        self.assertEqual(coverage.status, "COMPLETE")
        self.assertEqual(coverage.netlist_sha256, "e" * 64)
        self.assertEqual(coverage.entries[0].status, "COMPLETE")
        self.assertAlmostEqual(coverage.entries[0].calculated_corner_hz or 0, 1591.55, delta=0.02)
        self.assertFalse(
            any(item.rule_id == "filter.rc_corner_mismatch" for item in result.findings)
        )

    def test_schematic_value_mutations_are_detected_with_topology_unchanged(self) -> None:
        original = rc_filter_netlist()
        changed_values = (
            rc_filter_netlist(capacitor_value="220nF"),
            rc_filter_netlist(resistor_value="2k"),
        )
        for changed in changed_values:
            with self.subTest(
                resistor=changed.components["R1"].value,
                capacitor=changed.components["C1"].value,
            ):
                self.assertEqual(original.nets, changed.nets)
                self.assertEqual(original.component_pin_numbers, changed.component_pin_numbers)

                result = report(changed, rc_filter_map())
                self.assertEqual(result.status, "REVIEW")
                entry = result.rc_filter_coverage.entries[0]
                self.assertEqual(entry.status, "OUT_OF_RANGE")
                self.assertIsNotNone(entry.calculated_corner_hz)
                finding = next(
                    item for item in result.findings if item.rule_id == "filter.rc_corner_mismatch"
                )
                self.assertIn("calculated_nominal_corner_hz", finding.evidence)
                self.assertIn("1500–1700 Hz", finding.evidence["target_corner_hz"])
                self.assertIn("RC filter coverage: COMPLETE", text_report(result))
        capacitor_mutation = report(rc_filter_netlist(capacitor_value="220nF"), rc_filter_map())
        self.assertAlmostEqual(
            capacitor_mutation.rc_filter_coverage.entries[0].calculated_corner_hz or 0,
            723.43,
            delta=0.02,
        )

    def test_corner_mismatch_is_order_stable_and_corrected_value_clears_it(self) -> None:
        rule_id = "filter.rc_corner_mismatch"
        source = rc_filter_netlist(capacitor_value="220nF")

        def lint(netlist: NetlistContract):
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return source_hash, report(
                netlist,
                rc_filter_map(),
                netlist_sha256=source_hash,
            )

        source_hash, original = lint(source)
        self.assertEqual(original.rc_filter_coverage.netlist_sha256, source_hash)
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 1)

        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered_hash, reordered = lint(reordered_source)
        self.assertNotEqual(source_hash, reordered_hash)
        self.assertEqual(reordered.rc_filter_coverage.netlist_sha256, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_hash, repaired = lint(rc_filter_netlist())
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_wrong_assignment_dnp_missing_inventory_and_extra_parts_need_review(self) -> None:
        for fault in (
            "wrong-capacitor-net",
            "disconnected-capacitor-return",
            "dnp-capacitor",
            "missing-capacitor-component",
            "missing-capacitor-pin-inventory",
            "wrong-capacitor-symbol",
            "wrong-resistor-footprint",
            "unsupported-capacitor-value",
            "unsupported-resistor-value",
            "extra-parallel-capacitor",
            "extra-parallel-resistor",
        ):
            with self.subTest(fault=fault):
                result = report(rc_filter_netlist(fault=fault), rc_filter_map())
                self.assertEqual(result.rc_filter_coverage.status, "INCOMPLETE")
                self.assertEqual(result.rc_filter_coverage.entries[0].status, "INCOMPLETE")
                self.assertEqual(result.status, "REVIEW")
                self.assertTrue(
                    any(item.rule_id == "filter.rc_corner_mismatch" for item in result.findings)
                )

    def test_rule_can_be_blocked_or_disabled_and_exact_ignore_is_project_owned(self) -> None:
        out_of_range = rc_filter_netlist(capacitor_value="220nF")
        blocked = report(
            out_of_range,
            rc_filter_map(),
            override=DesignLintRuleOverride(
                rule_id="filter.rc_corner_mismatch",
                mode="block",
                reason="This interface's filter corner is a release requirement",
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        candidate = next(
            item
            for item in report(out_of_range, rc_filter_map()).findings
            if item.rule_id == "filter.rc_corner_mismatch"
        )
        ignored = report(
            out_of_range,
            rc_filter_map(),
            ignore=DesignLintIgnore(
                rule_id=candidate.rule_id,
                fingerprint=candidate.fingerprint,
                reason="Reviewed against the approved input filter specification",
            ),
        )
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "filter.rc_corner_mismatch"
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(ignored_finding.disposition, "IGNORED")

        disabled = report(
            out_of_range,
            rc_filter_map(),
            override=DesignLintRuleOverride(
                rule_id="filter.rc_corner_mismatch",
                mode="off",
                reason="Not applicable to this assembly configuration",
            ),
        )
        disabled_finding = next(
            item for item in disabled.findings if item.rule_id == "filter.rc_corner_mismatch"
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(disabled_finding.disposition, "RULE_OFF")

    def test_unmapped_network_is_not_inferred_and_coverage_is_not_requested(self) -> None:
        result = report(rc_filter_netlist())
        self.assertEqual(result.rc_filter_coverage.status, "NOT_REQUESTED")
        self.assertFalse(
            any(item.rule_id == "filter.rc_corner_mismatch" for item in result.findings)
        )

    def test_invalid_component_ownership_and_ranges_are_rejected(self) -> None:
        data = rc_filter_map().filters[0].model_dump()
        data["resistor_first_pin"] = "R9.1"
        with self.assertRaises(ValidationError):
            RcFilterRequirement.model_validate(data)

        data = rc_filter_map().filters[0].model_dump()
        data["minimum_target_corner_hz"] = 1800
        with self.assertRaises(ValidationError):
            RcFilterRequirement.model_validate(data)
