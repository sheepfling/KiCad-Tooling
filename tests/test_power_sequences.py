"""Synthetic regressions for project-mapped power-sequence dependencies."""

from __future__ import annotations

import hashlib
import unittest

from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PowerSequenceDependencyRequirement,
    PowerSequenceEndpointRequirement,
    PowerSequenceMap,
    PowerSequenceStageRequirement,
)
from kicad_tooling.hwrepo.power_sequences import (
    power_sequence_graph_has_cycle,
    power_sequence_mismatches,
    power_sequence_observed_enable_cycles,
)

RULE_ID = "power.mapped_sequence_dependency_mismatch"


def power_sequence_map(*, cycle: bool = False, firmware_enable: bool = True) -> PowerSequenceMap:
    stage_one = PowerSequenceStageRequirement(
        id="rail-a",
        output=PowerSequenceEndpointRequirement(
            reference="U1",
            pin="U1.2",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net="RAIL_A",
            part_id="SYNTH-REG-A",
        ),
        power_good=PowerSequenceEndpointRequirement(
            reference="U1",
            pin="U1.3",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net="GOOD_A",
            part_id="SYNTH-REG-A",
        ),
        enable=PowerSequenceEndpointRequirement(
            reference="U1",
            pin="U1.1",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net="GOOD_B" if cycle else "CONTROL_ON",
            part_id="SYNTH-REG-A",
        ),
        enable_control="netlist" if cycle else "always_on",
        basis="Synthetic upstream rail; independent requirement states this startup role",
    )
    stage_two = PowerSequenceStageRequirement(
        id="rail-b",
        output=PowerSequenceEndpointRequirement(
            reference="U2",
            pin="U2.2",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net="RAIL_B",
            part_id="SYNTH-REG-B",
        ),
        power_good=(
            PowerSequenceEndpointRequirement(
                reference="U2",
                pin="U2.3",
                symbol="Synthetic:Regulator",
                footprint="Synthetic:SOT23-5",
                net="GOOD_B",
                part_id="SYNTH-REG-B",
            )
            if cycle
            else None
        ),
        enable=PowerSequenceEndpointRequirement(
            reference="U2",
            pin="U2.1",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net="GOOD_A",
            part_id="SYNTH-REG-B",
        ),
        enable_control="firmware" if firmware_enable else "netlist",
        basis="Synthetic downstream rail with a mapped enable pin",
    )
    dependencies = [
        PowerSequenceDependencyRequirement(
            id="rail-a-before-rail-b",
            predecessor_stage="rail-a",
            successor_stage="rail-b",
            signal_net="GOOD_A",
            basis="Synthetic device requirement: rail A power-good drives rail B enable",
        )
    ]
    stages = [stage_one, stage_two]
    if cycle:
        dependencies.append(
            PowerSequenceDependencyRequirement(
                id="rail-b-before-rail-a",
                predecessor_stage="rail-b",
                successor_stage="rail-a",
                signal_net="GOOD_B",
                basis="Synthetic malformed source requirement closes a cycle",
            )
        )
    return PowerSequenceMap(
        basis="Synthetic source page 4, startup dependency table",
        stages=tuple(stages),
        dependencies=tuple(dependencies),
    )


def power_sequence_netlist(*, fault: str | None = None, cycle: bool = False) -> NetlistContract:
    components = {
        "U1": ComponentContract(
            value="Synthetic regulator A",
            footprint="Synthetic:SOT23-5",
            part_id="SYNTH-REG-A",
        ),
        "U2": ComponentContract(
            value="Synthetic regulator B",
            footprint="Synthetic:SOT23-5",
            part_id="SYNTH-REG-B",
        ),
    }
    symbols = {"U1": "Synthetic:Regulator", "U2": "Synthetic:Regulator"}
    pin_numbers = {"U1": ("1", "2", "3"), "U2": ("1", "2", "3")}
    nets: dict[str, tuple[str, ...]] = {
        "RAIL_A": ("U1.2",),
        "GOOD_A": ("U1.3", "U2.1"),
        "RAIL_B": ("U2.2",),
        "CONTROL_ON": ("U1.1",),
    }
    dnp: tuple[str, ...] = ()
    if cycle:
        nets.pop("CONTROL_ON")
        nets["GOOD_B"] = ("U2.3", "U1.1")
    if fault == "open-enable":
        nets["GOOD_A"] = ("U1.3",)
        nets["FLOATING"] = ("U2.1",)
    elif fault == "wrong-output":
        nets["RAIL_A"] = ()
        nets["OTHER_RAIL"] = ("U1.2",)
    elif fault == "wrong-symbol":
        symbols["U1"] = "Synthetic:Switch"
    elif fault == "wrong-part-id":
        components["U1"] = components["U1"].model_copy(update={"part_id": "WRONG-PART"})
    elif fault == "missing-pin":
        pin_numbers["U2"] = ("2", "3")
    elif fault == "dnp":
        dnp = ("U2",)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def power_sequence_output_cycle_map(*, cycle: bool) -> PowerSequenceMap:
    def endpoint(
        reference: str,
        pin: str,
        net: str,
        part_id: str,
    ) -> PowerSequenceEndpointRequirement:
        return PowerSequenceEndpointRequirement(
            reference=reference,
            pin=f"{reference}.{pin}",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net=net,
            part_id=part_id,
        )

    stages = (
        PowerSequenceStageRequirement(
            id="rail-a",
            output=endpoint("U1", "2", "RAIL_A", "SYNTH-REG-A"),
            power_good=endpoint("U1", "3", "GOOD_A", "SYNTH-REG-A"),
            enable=endpoint("U1", "1", "RAIL_B" if cycle else "CONTROL_ON", "SYNTH-REG-A"),
            enable_control="netlist" if cycle else "external",
            basis="Synthetic source identifies rail A stage endpoints",
        ),
        PowerSequenceStageRequirement(
            id="rail-b",
            output=endpoint("U2", "2", "RAIL_B", "SYNTH-REG-B"),
            power_good=endpoint("U2", "3", "GOOD_B", "SYNTH-REG-B"),
            enable=endpoint("U2", "1", "RAIL_A", "SYNTH-REG-B"),
            enable_control="netlist",
            basis="Synthetic source identifies rail B stage endpoints",
        ),
        PowerSequenceStageRequirement(
            id="rail-c",
            output=endpoint("U3", "2", "RAIL_C", "SYNTH-REG-C"),
            power_good=endpoint("U3", "3", "GOOD_C", "SYNTH-REG-C"),
            enable=endpoint("U3", "1", "GOOD_B", "SYNTH-REG-C"),
            enable_control="netlist",
            basis="Synthetic source identifies rail C stage endpoints",
        ),
    )
    return PowerSequenceMap(
        basis="Synthetic source page 6, mapped stage endpoint table",
        stages=stages,
        dependencies=(
            PowerSequenceDependencyRequirement(
                id="rail-b-before-rail-c",
                predecessor_stage="rail-b",
                successor_stage="rail-c",
                signal_net="GOOD_B",
                basis="Synthetic source requires rail B power-good to enable rail C",
            ),
        ),
    )


def power_sequence_output_cycle_netlist(*, cycle: bool) -> NetlistContract:
    components = {
        reference: ComponentContract(
            value=f"Synthetic regulator {suffix}",
            footprint="Synthetic:SOT23-5",
            part_id=f"SYNTH-REG-{suffix}",
        )
        for reference, suffix in (("U1", "A"), ("U2", "B"), ("U3", "C"))
    }
    return NetlistContract(
        components=components,
        nets={
            "RAIL_A": ("U1.2", "U2.1"),
            "RAIL_B": ("U1.1", "U2.2") if cycle else ("U2.2",),
            "GOOD_A": ("U1.3",),
            "GOOD_B": ("U2.3", "U3.1"),
            "RAIL_C": ("U3.2",),
            "GOOD_C": ("U3.3",),
            "CONTROL_ON": () if cycle else ("U1.1",),
        },
        component_symbols={reference: "Synthetic:Regulator" for reference in components},
        component_pin_numbers={reference: ("1", "2", "3") for reference in components},
    )


def lint_report(
    netlist: NetlistContract,
    sequence_map: PowerSequenceMap | None = None,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-power-sequence",
        observed=netlist,
        netlist_sha256=hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest(),
    )
    return evaluate(
        "synthetic-power-sequence",
        coach,
        DesignLintPolicy(
            power_sequence_map=sequence_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )


class PowerSequenceTests(unittest.TestCase):
    def test_explicit_power_good_to_enable_map_passes_including_firmware_control(self) -> None:
        sequence_map = power_sequence_map(firmware_enable=True)
        report = lint_report(power_sequence_netlist(), sequence_map)
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertNotIn(RULE_ID, {item.rule_id for item in report.findings})
        run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
        self.assertEqual(run.status, "EVALUATED")
        self.assertEqual(
            run.requirement_count, len(sequence_map.stages) + len(sequence_map.dependencies)
        )
        self.assertEqual(run.finding_count, 0)
        self.assertEqual(run.netlist_sha256, report.netlist_sha256)
        self.assertEqual(power_sequence_mismatches(sequence_map, power_sequence_netlist()), ())
        self.assertFalse(power_sequence_graph_has_cycle(sequence_map))

    def test_missing_net_identity_inventory_part_and_dnp_faults_are_reported(self) -> None:
        cases = (
            ("open-enable", "U2.1 is assigned to FLOATING", "rail-b"),
            ("wrong-output", "U1.2 is assigned to OTHER_RAIL", "rail-a"),
            ("wrong-symbol", "U1 symbol is Synthetic:Switch", "rail-a"),
            ("wrong-part-id", "U1 PART_ID is WRONG-PART", "rail-a"),
            ("missing-pin", "U2.1 is absent from the native pin inventory", "rail-b"),
            ("dnp", "U2 is marked DNP", "rail-b"),
        )
        for fault, expected_issue, expected_stage in cases:
            with self.subTest(fault=fault):
                report = lint_report(power_sequence_netlist(fault=fault), power_sequence_map())
                self.assertEqual(report.status, "REVIEW")
                run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
                self.assertEqual(run.status, "EVALUATED")
                self.assertEqual(run.finding_count, 1)
                finding = next(item for item in report.findings if item.rule_id == RULE_ID)
                self.assertTrue(
                    any(expected_issue in issue for issue in finding.evidence["issues"]),
                    finding.evidence["issues"],
                )
                self.assertEqual(
                    finding.evidence["sequence_map_basis"],
                    ("Synthetic source page 4, startup dependency table",),
                )
                if expected_stage == "rail-b":
                    self.assertIn("enable: U2.1 on GOOD_A", finding.evidence["expected_endpoints"])
                self.assertEqual(
                    finding.evidence["dependencies"],
                    ("rail-a-before-rail-b: rail-a → rail-b on GOOD_A",),
                )
                self.assertTrue(finding.evidence["map_sha256"])

    def test_cycle_in_explicit_requirement_is_reported(self) -> None:
        sequence_map = power_sequence_map(cycle=True)
        report = lint_report(power_sequence_netlist(cycle=True), sequence_map)
        finding = next(item for item in report.findings if item.rule_id == RULE_ID)
        self.assertTrue(any("graph is cyclic" in issue for issue in finding.evidence["issues"]))
        self.assertTrue(power_sequence_graph_has_cycle(sequence_map))

    def test_exact_mapped_output_to_enable_cycle_is_reported_with_acyclic_requirement_graph(
        self,
    ) -> None:
        sequence_map = power_sequence_output_cycle_map(cycle=True)
        observed = power_sequence_output_cycle_netlist(cycle=True)
        self.assertFalse(power_sequence_graph_has_cycle(sequence_map))
        self.assertEqual(power_sequence_mismatches(sequence_map, observed), ())
        cycles = power_sequence_observed_enable_cycles(sequence_map, observed)
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0].stage_ids, ("rail-a", "rail-b"))
        self.assertEqual(
            cycles[0].edges,
            (
                "rail-a output U1.2 on RAIL_A → rail-b enable U2.1",
                "rail-b output U2.2 on RAIL_B → rail-a enable U1.1",
            ),
        )

        report = lint_report(observed, sequence_map)
        self.assertEqual(report.status, "REVIEW")
        finding = next(item for item in report.findings if item.rule_id == RULE_ID)
        self.assertEqual(
            finding.evidence["declared_dependency_cycle"],
            ("false",),
        )
        self.assertEqual(
            finding.evidence["observed_output_to_enable_cycle_stages"],
            ("rail-a, rail-b",),
        )
        self.assertEqual(
            finding.evidence["observed_output_to_enable_cycle_edges"],
            cycles[0].edges,
        )

        dnp_stage = observed.model_copy(update={"dnp_components": ("U2",)})
        self.assertFalse(power_sequence_observed_enable_cycles(sequence_map, dnp_stage))
        wrong_enable_nets = dict(observed.nets)
        wrong_enable_nets["RAIL_A"] = ("U1.2",)
        wrong_enable_nets["UNEXPECTED"] = ("U2.1",)
        mismapped_stage = observed.model_copy(update={"nets": wrong_enable_nets})
        self.assertFalse(power_sequence_observed_enable_cycles(sequence_map, mismapped_stage))

        reordered = observed.model_copy(
            update={
                "nets": dict(reversed(tuple(observed.nets.items()))),
                "components": dict(reversed(tuple(observed.components.items()))),
                "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(observed.component_pin_numbers.items()))
                ),
            }
        )
        reordered_finding = next(
            item
            for item in lint_report(reordered, sequence_map).findings
            if item.rule_id == RULE_ID
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (finding.fingerprint, finding.evidence),
        )

        valid_map = power_sequence_output_cycle_map(cycle=False)
        valid_netlist = power_sequence_output_cycle_netlist(cycle=False)
        self.assertFalse(power_sequence_observed_enable_cycles(valid_map, valid_netlist))
        self.assertNotIn(
            RULE_ID,
            {item.rule_id for item in lint_report(valid_netlist, valid_map).findings},
        )

    def test_unconfigured_map_does_not_infer_requirements_from_pin_names(self) -> None:
        named_pins = power_sequence_netlist().model_copy(
            update={
                "pin_functions": {"U1.3": "PG", "U2.1": "EN"},
                "pin_electrical_types": {"U1.3": "output", "U2.1": "input"},
            }
        )
        report = lint_report(named_pins)
        self.assertNotIn(RULE_ID, {item.rule_id for item in report.findings})
        run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
        self.assertEqual(run.status, "NOT_CONFIGURED")
        self.assertEqual(run.finding_count, 0)

    def test_rule_supports_review_block_off_and_exact_ignore(self) -> None:
        faulty = power_sequence_netlist(fault="open-enable")
        sequence_map = power_sequence_map()
        blocked = lint_report(
            faulty,
            sequence_map,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="Synthetic release policy requires the mapped sequence topology",
            ),
        )
        self.assertEqual(blocked.status, "FAIL")
        finding = next(
            item for item in lint_report(faulty, sequence_map).findings if item.rule_id == RULE_ID
        )
        ignored = lint_report(
            faulty,
            sequence_map,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic approved alternate sequence is covered elsewhere",
            ),
        )
        self.assertEqual(
            next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition,
            "IGNORED",
        )
        disabled = lint_report(
            faulty,
            sequence_map,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="Synthetic alternate variant has a separate sequence contract",
            ),
        )
        self.assertEqual(
            next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition,
            "RULE_OFF",
        )
        disabled_run = next(item for item in disabled.mapped_check_runs if item.rule_id == RULE_ID)
        self.assertEqual((disabled_run.status, disabled_run.mode), ("EVALUATED", "off"))
        self.assertEqual(disabled_run.finding_count, 1)

    def test_netlist_order_is_stable_and_repair_clears_finding(self) -> None:
        sequence_map = power_sequence_map()
        faulty = power_sequence_netlist(fault="open-enable")
        report = lint_report(faulty, sequence_map)
        original = next(item for item in report.findings if item.rule_id == RULE_ID)
        reordered = faulty.model_copy(
            update={
                "nets": dict(reversed(tuple(faulty.nets.items()))),
                "components": dict(reversed(tuple(faulty.components.items()))),
                "component_symbols": dict(reversed(tuple(faulty.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(faulty.component_pin_numbers.items()))
                ),
            }
        )
        reordered_finding = next(
            item
            for item in lint_report(reordered, sequence_map).findings
            if item.rule_id == RULE_ID
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original.fingerprint, original.evidence),
        )

        unrelated = faulty.model_copy(
            update={
                "components": {
                    **faulty.components,
                    "R9": ComponentContract(value="10k", footprint="Synthetic:R_0603"),
                },
                "nets": {
                    **faulty.nets,
                    "UNRELATED_A": ("R9.1",),
                    "UNRELATED_B": ("R9.2",),
                },
                "component_symbols": {**faulty.component_symbols, "R9": "Device:R"},
                "component_pin_numbers": {
                    **faulty.component_pin_numbers,
                    "R9": ("1", "2"),
                },
            }
        )
        unrelated_report = lint_report(unrelated, sequence_map)
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
            reason="Synthetic review accepts this explicit rail-sequence exception",
        )
        for candidate in (faulty, unrelated):
            ignored_report = lint_report(candidate, sequence_map, ignore=exact_ignore)
            ignored_finding = next(
                item for item in ignored_report.findings if item.rule_id == RULE_ID
            )
            self.assertEqual(ignored_finding.fingerprint, original.fingerprint)
            self.assertEqual(ignored_finding.disposition, "IGNORED")

        self.assertNotIn(
            RULE_ID,
            {item.rule_id for item in lint_report(power_sequence_netlist(), sequence_map).findings},
        )

    def test_map_rejects_unresolved_or_inconsistent_dependencies(self) -> None:
        raw = power_sequence_map().model_dump(mode="python")
        raw["dependencies"][0]["successor_stage"] = "unknown-stage"
        with self.assertRaisesRegex(ValidationError, "name declared stages"):
            PowerSequenceMap.model_validate(raw)

        raw = power_sequence_map().model_dump(mode="python")
        raw["dependencies"][0]["signal_net"] = "WRONG_NET"
        with self.assertRaisesRegex(ValidationError, "match its power-good endpoint"):
            PowerSequenceMap.model_validate(raw)

        raw = power_sequence_map().model_dump(mode="python")
        raw["stages"][1]["enable_control"] = "external"
        raw["stages"][1]["enable"] = None
        with self.assertRaisesRegex(ValidationError, "requires a mapped enable endpoint"):
            PowerSequenceMap.model_validate(raw)


if __name__ == "__main__":
    unittest.main()
