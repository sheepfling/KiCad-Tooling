"""Synthetic regressions for authored crystal load-network checks."""

from __future__ import annotations

import hashlib
import unittest
from decimal import localcontext

from kicad_tooling.hwrepo.crystal_networks import parse_capacitance_pf
from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    CrystalLoadCapRequirement,
    CrystalNetworkMap,
    CrystalNetworkRequirement,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)


def crystal_map(*, reverse_resonator_pins: bool = False) -> CrystalNetworkMap:
    return CrystalNetworkMap(
        basis="Synthetic oscillator datasheet load range and reviewed schematic pin map",
        networks=(
            CrystalNetworkRequirement(
                oscillator_reference="U1",
                expected_oscillator_value="Synthetic MCU",
                expected_oscillator_symbol="Synthetic:Oscillator",
                expected_oscillator_footprint="Synthetic:SOIC-8",
                oscillator_input_pin="U1.1",
                oscillator_output_pin="U1.2",
                resonator_reference="Y1",
                expected_resonator_value="Synthetic 16 MHz crystal",
                expected_resonator_symbol="Device:Crystal",
                expected_resonator_footprint="Synthetic:Crystal-3225",
                resonator_input_pin="Y1.2" if reverse_resonator_pins else "Y1.1",
                resonator_output_pin="Y1.1" if reverse_resonator_pins else "Y1.2",
                load_capacitors=(
                    CrystalLoadCapRequirement(
                        reference="C1",
                        expected_symbol="Device:C",
                        expected_footprint="Synthetic:0603",
                        signal_pin="C1.1",
                        reference_pin="C1.2",
                        minimum_nominal_capacitance_pf=15.0,
                        maximum_nominal_capacitance_pf=47.0,
                    ),
                    CrystalLoadCapRequirement(
                        reference="C2",
                        expected_symbol="Device:C",
                        expected_footprint="Synthetic:0603",
                        signal_pin="C2.1",
                        reference_pin="C2.2",
                        minimum_nominal_capacitance_pf=15.0,
                        maximum_nominal_capacitance_pf=47.0,
                    ),
                ),
                reference_net="GND",
                minimum_target_load_pf=10.0,
                maximum_target_load_pf=12.0,
                minimum_stray_capacitance_pf=1.0,
                maximum_stray_capacitance_pf=3.0,
                basis="Synthetic authored requirements; nominal values only",
            ),
        ),
    )


def crystal_netlist(
    *,
    c1_value: str = "18pF",
    c2_value: str = "18pF",
    reverse_resonator_pins: bool = False,
    fault: str | None = None,
) -> NetlistContract:
    components = {
        "U1": ComponentContract(value="Synthetic MCU", footprint="Synthetic:SOIC-8"),
        "Y1": ComponentContract(
            value="Synthetic 16 MHz crystal", footprint="Synthetic:Crystal-3225"
        ),
        "C1": ComponentContract(value=c1_value, footprint="Synthetic:0603"),
        "C2": ComponentContract(value=c2_value, footprint="Synthetic:0603"),
    }
    symbols = {
        "U1": "Synthetic:Oscillator",
        "Y1": "Device:Crystal",
        "C1": "Device:C",
        "C2": "Device:C",
    }
    nets: dict[str, tuple[str, ...]] = {"GND": ("C1.2", "C2.2")}
    input_resonator_pin, output_resonator_pin = (
        ("Y1.2", "Y1.1") if reverse_resonator_pins else ("Y1.1", "Y1.2")
    )
    nets["OSC_IN"] = ("U1.1", input_resonator_pin, "C1.1")
    nets["OSC_OUT"] = ("U1.2", output_resonator_pin, "C2.1")
    dnp: tuple[str, ...] = ()
    if fault == "wrong-capacitor-node":
        nets["OSC_IN"] = (*nets["OSC_IN"], "C2.1")
        nets["OSC_OUT"] = tuple(pin for pin in nets["OSC_OUT"] if pin != "C2.1")
    elif fault == "open-capacitor":
        nets["OSC_OUT"] = tuple(pin for pin in nets["OSC_OUT"] if pin != "C2.1")
    elif fault == "wrong-symbol":
        symbols["U1"] = "Synthetic:DifferentDevice"
    elif fault == "wrong-value":
        components["U1"] = ComponentContract(
            value="Synthetic different MCU", footprint="Synthetic:SOIC-8"
        )
    elif fault == "dnp-capacitor":
        dnp = ("C2",)
    elif fault == "missing-resonator":
        components.pop("Y1")
        symbols.pop("Y1")
        nets["OSC_IN"] = tuple(pin for pin in nets["OSC_IN"] if pin != input_resonator_pin)
        nets["OSC_OUT"] = tuple(pin for pin in nets["OSC_OUT"] if pin != output_resonator_pin)
    elif fault == "unknown-capacitance":
        components["C1"] = ComponentContract(value="Cload", footprint="Synthetic:0603")
    elif fault == "cap-value-outside-authored-range":
        components["C1"] = ComponentContract(value="10pF", footprint="Synthetic:0603")
    elif fault == "extra-load-capacitor":
        components["C3"] = ComponentContract(value="4pF", footprint="Synthetic:0603")
        symbols["C3"] = "Device:C"
        nets["OSC_IN"] = (*nets["OSC_IN"], "C3.1")
        nets["GND"] = (*nets["GND"], "C3.2")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers={
            "U1": ("1", "2", "3", "4", "5", "6", "7", "8"),
            "Y1": ("1", "2"),
            "C1": ("1", "2"),
            "C2": ("1", "2"),
            **({"C3": ("1", "2")} if fault == "extra-load-capacitor" else {}),
        },
    )


def report(
    netlist: NetlistContract,
    requirement_map: CrystalNetworkMap | None = None,
    *,
    override: DesignLintRuleOverride | None = None,
    netlist_sha256: str = "c" * 64,
):
    policy = DesignLintPolicy(
        crystal_network_map=requirement_map,
        rules=() if override is None else (override,),
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-crystal",
        observed=netlist,
        netlist_sha256=netlist_sha256,
    )
    return evaluate("synthetic-crystal", coach, policy)


class CrystalNetworkTests(unittest.TestCase):
    def test_exact_network_and_inclusive_target_boundaries_pass(self) -> None:
        with localcontext() as context:
            context.prec = 3
            result = report(crystal_netlist(), crystal_map())
        self.assertEqual(result.status, "PASS", result.issues)
        coverage = result.crystal_network_coverage
        self.assertEqual(coverage.status, "COMPLETE")
        self.assertEqual(coverage.netlist_sha256, "c" * 64)
        entry = coverage.entries[0]
        self.assertEqual(entry.status, "COMPLETE")
        self.assertEqual(entry.formula, "C1*C2/(C1+C2) + Cstray")
        self.assertAlmostEqual(entry.calculated_minimum_load_pf or 0, 10.0)
        self.assertAlmostEqual(entry.calculated_maximum_load_pf or 0, 12.0)
        self.assertFalse(
            any(
                item.rule_id == "oscillator.crystal_load_network_mismatch"
                for item in result.findings
            )
        )
        rendered = text_report(result)
        self.assertIn("Crystal load-network coverage: COMPLETE", rendered)
        self.assertIn("Formula: C1*C2/(C1+C2) + Cstray", rendered)
        self.assertIn("Calculated nominal load: 10–12 pF; target 10–12 pF", rendered)

    def test_wrong_node_assignment_is_reported(self) -> None:
        result = report(crystal_netlist(fault="wrong-capacitor-node"), crystal_map())
        self.assertEqual(result.status, "REVIEW")
        entry = result.crystal_network_coverage.entries[0]
        self.assertEqual(entry.status, "INCOMPLETE")
        self.assertTrue(any("do not span" in issue for issue in entry.issues))
        finding = next(
            item
            for item in result.findings
            if item.rule_id == "oscillator.crystal_load_network_mismatch"
        )
        self.assertTrue(any("C2.1" in item for item in finding.evidence["pin_nets"]))

    def test_nominal_load_outside_target_is_reported_and_can_block(self) -> None:
        result = report(
            crystal_netlist(c1_value="47pF", c2_value="47pF"),
            crystal_map(),
            override=DesignLintRuleOverride(
                rule_id="oscillator.crystal_load_network_mismatch",
                mode="block",
                reason="Synthetic release policy requires mapped oscillator review to pass",
            ),
        )
        self.assertEqual(result.status, "FAIL")
        entry = result.crystal_network_coverage.entries[0]
        self.assertEqual(entry.status, "OUT_OF_RANGE")
        self.assertAlmostEqual(entry.calculated_minimum_load_pf or 0, 24.5)
        self.assertAlmostEqual(entry.calculated_maximum_load_pf or 0, 26.5)
        finding = next(
            item
            for item in result.findings
            if item.rule_id == "oscillator.crystal_load_network_mismatch"
        )
        self.assertEqual(finding.mode, "block")
        self.assertIn("24.5–26.5 pF", finding.evidence["calculated_nominal_load_pf"][0])

    def test_load_mismatch_is_order_stable_and_corrected_values_clear_it(self) -> None:
        rule_id = "oscillator.crystal_load_network_mismatch"
        source = crystal_netlist(c1_value="47pF", c2_value="47pF")

        def lint(netlist: NetlistContract):
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return source_hash, report(
                netlist,
                crystal_map(),
                netlist_sha256=source_hash,
            )

        source_hash, original = lint(source)
        self.assertEqual(original.crystal_network_coverage.netlist_sha256, source_hash)
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
        self.assertEqual(reordered.crystal_network_coverage.netlist_sha256, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_hash, repaired = lint(crystal_netlist())
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_unmapped_load_capacitor_is_reported_for_review(self) -> None:
        result = report(crystal_netlist(fault="extra-load-capacitor"), crystal_map())
        entry = result.crystal_network_coverage.entries[0]
        self.assertEqual(entry.status, "INCOMPLETE")
        self.assertEqual(entry.extra_capacitor_references, ("C3",))
        self.assertEqual(
            entry.extra_capacitor_pin_nets["C3"],
            ("C3.1 -> OSC_IN", "C3.2 -> GND"),
        )
        finding = next(
            item
            for item in result.findings
            if item.rule_id == "oscillator.crystal_load_network_mismatch"
        )
        self.assertEqual(finding.evidence["potential_extra_load_capacitors"], ("C3",))
        self.assertEqual(
            finding.evidence["potential_extra_load_capacitor_pin_nets"],
            ("C3: C3.1 -> OSC_IN, C3.2 -> GND",),
        )
        self.assertEqual(result.status, "REVIEW")

    def test_reversed_resonator_pins_are_valid_when_explicitly_mapped(self) -> None:
        result = report(
            crystal_netlist(reverse_resonator_pins=True),
            crystal_map(reverse_resonator_pins=True),
        )
        self.assertEqual(result.crystal_network_coverage.entries[0].status, "COMPLETE")
        self.assertEqual(result.status, "PASS", result.issues)

    def test_missing_dnp_identity_and_unsupported_values_need_review(self) -> None:
        for fault in (
            "open-capacitor",
            "missing-resonator",
            "dnp-capacitor",
            "wrong-symbol",
            "wrong-value",
            "unknown-capacitance",
            "cap-value-outside-authored-range",
        ):
            with self.subTest(fault=fault):
                result = report(crystal_netlist(fault=fault), crystal_map())
                self.assertEqual(result.status, "REVIEW")
                self.assertEqual(result.crystal_network_coverage.entries[0].status, "INCOMPLETE")
                self.assertTrue(
                    any(
                        finding.rule_id == "oscillator.crystal_load_network_mismatch"
                        for finding in result.findings
                    )
                )
                if fault == "cap-value-outside-authored-range":
                    self.assertTrue(
                        any(
                            "reviewed range" in issue
                            for issue in result.crystal_network_coverage.entries[0].issues
                        )
                    )

    def test_unmapped_internal_oscillator_is_not_inferred(self) -> None:
        unlisted = NetlistContract(
            components={
                "U1": ComponentContract(value="MCU with internal oscillator", footprint="")
            },
            nets={"CLOCK": ("U1.1",)},
            component_symbols={"U1": "Synthetic:MCU"},
        )
        result = report(unlisted)
        self.assertEqual(result.crystal_network_coverage.status, "NOT_REQUESTED")
        self.assertFalse(
            any(
                item.rule_id == "oscillator.crystal_load_network_mismatch"
                for item in result.findings
            )
        )

    def test_capacitance_parser_accepts_explicit_units_only(self) -> None:
        self.assertEqual(parse_capacitance_pf("18 pF"), 18)
        self.assertEqual(parse_capacitance_pf("0.018 nF"), 18)
        self.assertEqual(parse_capacitance_pf("0.000018 uF"), 18)
        self.assertEqual(parse_capacitance_pf("18p"), 18)
        self.assertIsNone(parse_capacitance_pf("18"))
        self.assertIsNone(parse_capacitance_pf("Cload"))
        self.assertIsNone(parse_capacitance_pf(f"{'9' * 129}pF"))
