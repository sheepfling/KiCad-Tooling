"""Synthetic regressions for authored adjustable-regulator feedback checks."""

from __future__ import annotations

import hashlib
import unittest

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PowerConnectivityAnalysis,
    PowerConnectivityRailRequirement,
    PowerLoadConnectivityRequirement,
    PowerPinEndpointRequirement,
    PowerSourceGroupRequirement,
    RegulatorDividerResistorRequirement,
    RegulatorFeedbackMap,
    RegulatorFeedbackRequirement,
)
from kicad_tooling.hwrepo.power_connectivity import power_connectivity_checks

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]


def regulator_feedback_map() -> RegulatorFeedbackMap:
    return RegulatorFeedbackMap(
        basis="Synthetic regulator data sheet and reviewed divider topology",
        regulators=(
            RegulatorFeedbackRequirement(
                id="main-rail",
                regulator_reference="U1",
                expected_regulator_value="SYNTH-ADJ",
                expected_regulator_symbol="Synthetic:AdjustableRegulator",
                expected_regulator_footprint="Synthetic:SOIC-8",
                output_pin="U1.1",
                expected_output_pin_function="OUT",
                feedback_pin="U1.2",
                expected_feedback_pin_function="FB",
                output_net="REG_OUT",
                reference_net="GND",
                upper_resistor=RegulatorDividerResistorRequirement(
                    reference="R1",
                    expected_symbol="Device:R",
                    expected_footprint="Synthetic:0603",
                    feedback_pin="R1.2",
                    rail_pin="R1.1",
                    minimum_nominal_resistance_ohms=178200.0,
                    maximum_nominal_resistance_ohms=181800.0,
                ),
                lower_resistor=RegulatorDividerResistorRequirement(
                    reference="R2",
                    expected_symbol="Device:R",
                    expected_footprint="Synthetic:0603",
                    feedback_pin="R2.1",
                    rail_pin="R2.2",
                    minimum_nominal_resistance_ohms=32670.0,
                    maximum_nominal_resistance_ohms=33330.0,
                ),
                minimum_feedback_reference_voltage_v=0.792,
                maximum_feedback_reference_voltage_v=0.808,
                minimum_target_output_voltage_v=5.1,
                maximum_target_output_voltage_v=5.22,
                basis="Synthetic datasheet reference limits and output requirement",
            ),
        ),
    )


def regulator_netlist(
    *,
    fault: str | None = None,
    with_compensation_capacitor: bool = False,
) -> NetlistContract:
    components = {
        "J1": ComponentContract(value="Synthetic input", footprint="Synthetic:Conn2"),
        "U1": ComponentContract(value="SYNTH-ADJ", footprint="Synthetic:SOIC-8"),
        "R1": ComponentContract(value="180k", footprint="Synthetic:0603"),
        "R2": ComponentContract(value="33k", footprint="Synthetic:0603"),
    }
    symbols = {
        "J1": "Synthetic:InputConnector",
        "U1": "Synthetic:AdjustableRegulator",
        "R1": "Device:R",
        "R2": "Device:R",
    }
    pin_functions = {
        "U1.1": "OUT",
        "U1.2": "FB",
        "R1.1": "passive",
        "R1.2": "passive",
        "R2.1": "passive",
        "R2.2": "passive",
    }
    nets: dict[str, tuple[str, ...]] = {
        "VIN": ("J1.1", "U1.3"),
        "REG_OUT": ("U1.1", "R1.1", "J1.2"),
        "FB": ("U1.2", "R1.2", "R2.1"),
        "GND": ("R2.2", "U1.4"),
    }
    dnp: tuple[str, ...] = ()
    if fault == "wrong-output-net":
        nets["REG_OUT"] = tuple(pin for pin in nets["REG_OUT"] if pin != "U1.1")
        nets["OTHER_OUT"] = ("U1.1",)
    elif fault == "split-feedback-node":
        nets["FB"] = tuple(pin for pin in nets["FB"] if pin != "R2.1")
        nets["FB2"] = ("R2.1",)
    elif fault == "wrong-reference-net":
        nets["GND"] = tuple(pin for pin in nets["GND"] if pin != "R2.2")
        nets["OTHER_GND"] = ("R2.2",)
    elif fault == "missing-feedback-pin":
        nets["FB"] = tuple(pin for pin in nets["FB"] if pin != "U1.2")
    elif fault == "wrong-regulator-value":
        components["U1"] = ComponentContract(value="SYNTH-ADJ-ALT", footprint="Synthetic:SOIC-8")
    elif fault == "wrong-regulator-footprint":
        components["U1"] = ComponentContract(value="SYNTH-ADJ", footprint="Synthetic:QFN-8")
    elif fault == "wrong-feedback-function":
        pin_functions["U1.2"] = "VOUT"
    elif fault == "upper-resistor-outside-range":
        components["R1"] = ComponentContract(value="220k", footprint="Synthetic:0603")
    elif fault == "unsupported-resistor-value":
        components["R1"] = ComponentContract(value="Rtop", footprint="Synthetic:0603")
    elif fault == "dnp-lower-resistor":
        dnp = ("R2",)
    elif fault == "unmapped-feedback-resistor":
        components["R3"] = ComponentContract(value="1M", footprint="Synthetic:0603")
        symbols["R3"] = "Device:R"
        nets["FB"] = (*nets["FB"], "R3.1")
        nets["GND"] = (*nets["GND"], "R3.2")
    if with_compensation_capacitor:
        components["C1"] = ComponentContract(value="100pF", footprint="Synthetic:0603")
        symbols["C1"] = "Device:C"
        nets["REG_OUT"] = (*nets["REG_OUT"], "C1.1")
        nets["FB"] = (*nets["FB"], "C1.2")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=pin_functions,
        component_pin_numbers={
            "J1": ("1", "2"),
            "U1": tuple(str(number) for number in range(1, 9)),
            "R1": ("1", "2"),
            "R2": ("1", "2"),
            **({"R3": ("1", "2")} if fault == "unmapped-feedback-resistor" else {}),
            **({"C1": ("1", "2")} if with_compensation_capacitor else {}),
        },
    )


def report(
    netlist: NetlistContract,
    feedback_map: RegulatorFeedbackMap | None = None,
    *,
    override: DesignLintRuleOverride | None = None,
    netlist_sha256: str = "d" * 64,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-regulator",
        observed=netlist,
        netlist_sha256=netlist_sha256,
    )
    return evaluate(
        "synthetic-regulator",
        coach,
        DesignLintPolicy(
            regulator_feedback_map=feedback_map,
            rules=() if override is None else (override,),
        ),
    )


def power_connectivity_requirement() -> PowerConnectivityAnalysis:
    return PowerConnectivityAnalysis(
        basis="Synthetic input source and regulator input membership",
        rails=(
            PowerConnectivityRailRequirement(
                id="input",
                basis="Synthetic regulator input supply",
                net="VIN",
                source_groups=(
                    PowerSourceGroupRequirement(
                        id="input-connector",
                        basis="Synthetic input connector",
                        selection="all",
                        endpoints=(
                            PowerPinEndpointRequirement(
                                id="connector-output",
                                reference="J1",
                                symbol="Synthetic:InputConnector",
                                footprint="Synthetic:Conn2",
                                pins=("J1.1",),
                            ),
                        ),
                    ),
                ),
                loads=(
                    PowerLoadConnectivityRequirement(
                        id="regulator-input",
                        basis="Synthetic regulator input pin",
                        endpoints=(
                            PowerPinEndpointRequirement(
                                id="input-pin",
                                reference="U1",
                                symbol="Synthetic:AdjustableRegulator",
                                footprint="Synthetic:SOIC-8",
                                pins=("U1.3",),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


class RegulatorFeedbackTests(unittest.TestCase):
    def test_project_map_rejects_reversed_ranges_and_duplicate_pins(self) -> None:
        reversed_range = regulator_feedback_map().model_dump(mode="python")
        reversed_range["regulators"][0]["upper_resistor"]["minimum_nominal_resistance_ohms"] = (
            200000.0
        )
        with self.assertRaisesRegex(ValidationError, "range is reversed"):
            RegulatorFeedbackMap.model_validate(reversed_range)

        duplicate_pin = regulator_feedback_map().model_dump(mode="python")
        duplicate_pin["regulators"][0]["expected_feedback_pin_function"] = "OUT"
        duplicate_pin["regulators"][0]["feedback_pin"] = "U1.1"
        with self.assertRaisesRegex(ValidationError, "pins must differ"):
            RegulatorFeedbackMap.model_validate(duplicate_pin)

    def test_exact_network_and_reference_bounds_pass(self) -> None:
        result = report(regulator_netlist(), regulator_feedback_map())
        self.assertEqual(result.status, "PASS", result.issues)
        coverage = result.regulator_feedback_coverage
        self.assertEqual(coverage.status, "COMPLETE")
        self.assertEqual(coverage.netlist_sha256, "d" * 64)
        entry = coverage.entries[0]
        self.assertEqual(entry.status, "COMPLETE")
        self.assertEqual(entry.feedback_net, "FB")
        self.assertEqual(entry.formula, "Vref*(1+Rupper/Rlower)")
        self.assertAlmostEqual(entry.calculated_output_minimum_v or 0, 5.112)
        self.assertAlmostEqual(entry.calculated_output_maximum_v or 0, 5.215272727272727)
        self.assertFalse(
            any(item.rule_id == "power.regulator_feedback_mismatch" for item in result.findings)
        )
        rendered = text_report(result)
        self.assertIn("Regulator feedback coverage: COMPLETE", rendered)
        self.assertIn("Formula: Vref*(1+Rupper/Rlower)", rendered)
        self.assertIn("Calculated nominal output: 5.112–5.21527 V; target 5.1–5.22 V", rendered)

    def test_non_finite_calculation_is_incomplete_instead_of_crashing(self) -> None:
        feedback_map = regulator_feedback_map()
        requirement = feedback_map.regulators[0].model_copy(
            update={
                "minimum_feedback_reference_voltage_v": 1.0e308,
                "maximum_feedback_reference_voltage_v": 1.0e308,
            }
        )
        feedback_map = feedback_map.model_copy(update={"regulators": (requirement,)})

        result = report(regulator_netlist(), feedback_map)

        entry = result.regulator_feedback_coverage.entries[0]
        self.assertEqual(entry.status, "INCOMPLETE")
        self.assertIsNone(entry.calculated_output_minimum_v)
        self.assertIsNone(entry.calculated_output_maximum_v)
        self.assertTrue(any("supported finite numeric range" in issue for issue in entry.issues))

    def test_divider_value_change_outside_target_is_reported_and_can_block(self) -> None:
        result = report(
            regulator_netlist(fault="upper-resistor-outside-range"), regulator_feedback_map()
        )
        self.assertEqual(result.status, "REVIEW")
        entry = result.regulator_feedback_coverage.entries[0]
        self.assertEqual(entry.status, "OUT_OF_RANGE")
        self.assertGreater(entry.calculated_output_minimum_v or 0, 5.22)
        finding = next(
            item for item in result.findings if item.rule_id == "power.regulator_feedback_mismatch"
        )
        self.assertIn("R1=220000 Ω", finding.evidence["nominal_resistance_ohms"])

        blocked = report(
            regulator_netlist(fault="upper-resistor-outside-range"),
            regulator_feedback_map(),
            override=DesignLintRuleOverride(
                rule_id="power.regulator_feedback_mismatch",
                mode="block",
                reason="Synthetic reviewed output range is a release requirement",
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

    def test_feedback_mismatch_is_order_stable_and_corrected_value_clears_it(self) -> None:
        rule_id = "power.regulator_feedback_mismatch"
        source = regulator_netlist(fault="upper-resistor-outside-range")

        def lint(netlist: NetlistContract):
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return source_hash, report(
                netlist,
                regulator_feedback_map(),
                netlist_sha256=source_hash,
            )

        source_hash, original = lint(source)
        self.assertEqual(original.regulator_feedback_coverage.netlist_sha256, source_hash)
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
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered_hash, reordered = lint(reordered_source)
        self.assertNotEqual(source_hash, reordered_hash)
        self.assertEqual(reordered.regulator_feedback_coverage.netlist_sha256, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_hash, repaired = lint(regulator_netlist())
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_wrong_output_or_feedback_net_is_reported(self) -> None:
        for fault in ("wrong-output-net", "split-feedback-node", "wrong-reference-net"):
            with self.subTest(fault=fault):
                result = report(regulator_netlist(fault=fault), regulator_feedback_map())
                self.assertEqual(result.status, "REVIEW")
                self.assertEqual(result.regulator_feedback_coverage.entries[0].status, "INCOMPLETE")
                self.assertIsNone(
                    result.regulator_feedback_coverage.entries[0].calculated_output_minimum_v
                )
                self.assertTrue(
                    any(
                        item.rule_id == "power.regulator_feedback_mismatch"
                        for item in result.findings
                    )
                )

    def test_stale_identity_missing_pin_dnp_and_unsupported_value_need_review(self) -> None:
        for fault in (
            "wrong-regulator-value",
            "wrong-regulator-footprint",
            "wrong-feedback-function",
            "missing-feedback-pin",
            "dnp-lower-resistor",
            "unsupported-resistor-value",
        ):
            with self.subTest(fault=fault):
                result = report(regulator_netlist(fault=fault), regulator_feedback_map())
                self.assertEqual(result.status, "REVIEW")
                self.assertEqual(result.regulator_feedback_coverage.entries[0].status, "INCOMPLETE")

    def test_unmapped_fitted_resistor_on_feedback_node_makes_coverage_incomplete(self) -> None:
        result = report(
            regulator_netlist(fault="unmapped-feedback-resistor"), regulator_feedback_map()
        )
        entry = result.regulator_feedback_coverage.entries[0]
        self.assertEqual(entry.status, "INCOMPLETE")
        self.assertTrue(
            any("unmapped fitted resistors" in issue.casefold() for issue in entry.issues)
        )
        self.assertIsNone(entry.calculated_output_minimum_v)

    def test_compensation_cap_does_not_change_nominal_dc_divider_check(self) -> None:
        result = report(
            regulator_netlist(with_compensation_capacitor=True), regulator_feedback_map()
        )
        self.assertEqual(result.regulator_feedback_coverage.entries[0].status, "COMPLETE")
        self.assertEqual(result.status, "PASS")

    def test_unmapped_fixed_output_regulator_is_not_inferred(self) -> None:
        fixed_output = NetlistContract(
            components={
                "U9": ComponentContract(value="SYNTH-FIXED-3V3", footprint="Synthetic:SOT-23-5")
            },
            nets={"3V3": ("U9.1",)},
            component_symbols={"U9": "Synthetic:FixedRegulator"},
        )
        result = report(fixed_output)
        self.assertEqual(result.regulator_feedback_coverage.status, "NOT_REQUESTED")
        self.assertFalse(
            any(item.rule_id == "power.regulator_feedback_mismatch" for item in result.findings)
        )

    def test_existing_power_connectivity_lane_does_not_see_divider_value_fault(self) -> None:
        connectivity = power_connectivity_requirement()
        check = power_connectivity_checks(
            connectivity, regulator_netlist(fault="upper-resistor-outside-range")
        )
        self.assertTrue(all(item.status == "PASS" for item in check))
        lint = report(
            regulator_netlist(fault="upper-resistor-outside-range"), regulator_feedback_map()
        )
        self.assertEqual(lint.regulator_feedback_coverage.entries[0].status, "OUT_OF_RANGE")


if __name__ == "__main__":
    unittest.main()
