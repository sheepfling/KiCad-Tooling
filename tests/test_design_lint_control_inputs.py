"""Focused synthetic regressions for the control inputs lint theme."""

from __future__ import annotations

import unittest

import pytest

from kicad_tooling.hwrepo.control_input_bias import control_input_bias_heuristic_coverage
from kicad_tooling.hwrepo.design_lint import (
    evaluate,
    text_report,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures import (
    coach,
    control_input_pins,
    with_control_resistor,
)
from tests.test_control_inputs import control_netlist, control_requirement

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]


class DesignLintControlInputTests(unittest.TestCase):
    def test_connected_control_input_without_visible_bias_is_review_only_and_configurable(
        self,
    ) -> None:
        source = control_input_pins(connected=True, visible_bias=False)
        report = evaluate("synthetic-control-bias", coach(source), DesignLintPolicy())
        rule_id = "control.connected_control_input_without_visible_bias"
        findings = [item for item in report.findings if item.rule_id == rule_id]

        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(
            {item.evidence["net"][0] for item in findings},
            {"RESET_LINE", "ENABLE_LINE", "ENABLE_A", "BOOT_STRAP"},
        )
        self.assertTrue(all(item.mode == "review" for item in findings))
        self.assertTrue(all(item.evidence["output_capable_peers"] == () for item in findings))
        self.assertTrue(
            all(
                "does not establish that a resistor is required" in item.message
                for item in findings
            )
        )

        blocked = evaluate(
            "synthetic-control-bias",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=rule_id,
                        mode="block",
                        reason="This project requires explicit control-input bias review",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        disabled = evaluate(
            "synthetic-control-bias",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=rule_id,
                        mode="off",
                        reason="Reviewed internal bias covers these controls",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertTrue(all(item.disposition == "RULE_OFF" for item in disabled.findings))

        ignored = evaluate(
            "synthetic-control-bias",
            coach(source),
            DesignLintPolicy(
                ignores=tuple(
                    DesignLintIgnore(
                        rule_id=item.rule_id,
                        fingerprint=item.fingerprint,
                        reason="Reviewed off-board bias for this control net",
                    )
                    for item in findings
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertTrue(all(item.disposition == "IGNORED" for item in ignored.findings))

    def test_connected_control_bias_prompt_checks_assignments_and_valid_controls(self) -> None:
        rule_id = "control.connected_control_input_without_visible_bias"
        locally_biased = evaluate(
            "synthetic-control-bias",
            coach(control_input_pins(connected=True)),
            DesignLintPolicy(),
        )
        self.assertNotIn(rule_id, {item.rule_id for item in locally_biased.findings})

        pull_down = with_control_resistor(
            control_input_pins(connected=True, visible_bias=False),
            signal_net="RESET_LINE",
            rail_net="GND",
        )
        pull_down_report = evaluate("synthetic-control-bias", coach(pull_down), DesignLintPolicy())
        self.assertNotIn(
            "RESET_LINE",
            {
                item.evidence["net"][0]
                for item in pull_down_report.findings
                if item.rule_id == rule_id
            },
        )

        dnp_bias = with_control_resistor(
            control_input_pins(connected=True, visible_bias=False),
            signal_net="RESET_LINE",
            rail_net="+3V3",
        ).model_copy(update={"dnp_components": ("R1",)})
        dnp_bias_report = evaluate("synthetic-control-bias", coach(dnp_bias), DesignLintPolicy())
        self.assertIn(
            "RESET_LINE",
            {
                item.evidence["net"][0]
                for item in dnp_bias_report.findings
                if item.rule_id == rule_id
            },
        )

        unrecognized_rail = with_control_resistor(
            control_input_pins(connected=True, visible_bias=False),
            signal_net="RESET_LINE",
            rail_net="CUSTOM_BIAS",
        )
        unrecognized_rail_report = evaluate(
            "synthetic-control-bias", coach(unrecognized_rail), DesignLintPolicy()
        )
        self.assertIn(
            "RESET_LINE",
            {
                item.evidence["net"][0]
                for item in unrecognized_rail_report.findings
                if item.rule_id == rule_id
            },
        )

        dnp = evaluate(
            "synthetic-control-bias",
            coach(control_input_pins(connected=True, dnp=True, visible_bias=False)),
            DesignLintPolicy(),
        )
        self.assertNotIn(rule_id, {item.rule_id for item in dnp.findings})

        source = control_input_pins(connected=True, visible_bias=False)
        with_driver = source.model_copy(
            update={
                "components": {
                    **source.components,
                    "U2": ComponentContract(value="Synthetic supervisor", footprint=""),
                },
                "component_symbols": {
                    **source.component_symbols,
                    "U2": "Synthetic:Supervisor",
                },
                "component_pin_numbers": {
                    **source.component_pin_numbers,
                    "U2": ("1",),
                },
                "pin_functions": {**source.pin_functions, "U2.1": "RESET_OUT"},
                "pin_electrical_types": {**source.pin_electrical_types, "U2.1": "open_collector"},
                "nets": {
                    **source.nets,
                    "RESET_LINE": (*source.nets["RESET_LINE"], "U2.1"),
                },
            }
        )
        driver_report = evaluate("synthetic-control-bias", coach(with_driver), DesignLintPolicy())
        reset_finding = next(
            item
            for item in driver_report.findings
            if item.rule_id == rule_id and item.evidence["net"] == ("RESET_LINE",)
        )
        self.assertEqual(
            reset_finding.evidence["output_capable_peers"], ("U2.1: RESET_OUT (open_collector)",)
        )

    def test_connected_control_bias_prompt_uses_exact_source_bound_contract_decisions(self) -> None:
        rule_id = "control.connected_control_input_without_visible_bias"
        source = control_netlist(fault="missing-resistor")
        for bias_mode in ("internal", "external", "not_required"):
            with self.subTest(bias_mode=bias_mode):
                coverage = control_input_bias_heuristic_coverage(
                    source,
                    netlist_sha256="a" * 64,
                    source_path="projects/synthetic/electrical.json",
                    source_sha256="b" * 64,
                    state="required",
                    spec=control_requirement(bias_mode=bias_mode),
                )
                self.assertEqual(coverage.status, "COMPLETE")
                self.assertEqual(len(coverage.entries), 1)
                self.assertEqual(coverage.entries[0].status, "COVERED")
                report = evaluate(
                    "synthetic-control-bias",
                    coach(source),
                    DesignLintPolicy(),
                    control_input_bias_coverage=coverage,
                )
                self.assertNotIn(rule_id, {item.rule_id for item in report.findings})
                self.assertEqual(report.control_input_bias_coverage, coverage)
                rendered = text_report(report)
                self.assertIn("Control-input bias heuristic coverage: COMPLETE", rendered)
                failed_summary = report.model_copy(update={"native_status": "FAIL"})
                self.assertIn(
                    "Validation summary status: FAIL",
                    text_report(failed_summary),
                )
                self.assertIn(f"bias={bias_mode}", rendered)
                self.assertIn("projects/synthetic/electrical.json", rendered)

        local_missing = control_input_bias_heuristic_coverage(
            source,
            netlist_sha256="a" * 64,
            source_path="projects/synthetic/electrical.json",
            source_sha256="b" * 64,
            state="required",
            spec=control_requirement(bias_mode="local"),
        )
        self.assertEqual(local_missing.status, "OPEN")
        self.assertTrue(any("bias:" in issue for issue in local_missing.entries[0].issues))
        local_report = evaluate(
            "synthetic-control-bias",
            coach(source),
            DesignLintPolicy(),
            control_input_bias_coverage=local_missing,
        )
        self.assertIn(rule_id, {item.rule_id for item in local_report.findings})

        no_bias_with_extra_output = control_netlist(fault="missing-resistor")
        no_bias_with_extra_output = no_bias_with_extra_output.model_copy(
            update={
                "components": {
                    **no_bias_with_extra_output.components,
                    "U4": ComponentContract(
                        value="Synthetic unreviewed driver", footprint="Package_SO:SOIC-8"
                    ),
                },
                "component_symbols": {
                    **no_bias_with_extra_output.component_symbols,
                    "U4": "Synthetic:PushPullOutput",
                },
                "component_pin_numbers": {
                    **no_bias_with_extra_output.component_pin_numbers,
                    "U4": ("1",),
                },
                "pin_functions": {
                    **no_bias_with_extra_output.pin_functions,
                    "U4.1": "RESET_N",
                },
                "pin_electrical_types": {
                    **no_bias_with_extra_output.pin_electrical_types,
                    "U4.1": "output",
                },
                "nets": {
                    **no_bias_with_extra_output.nets,
                    "RESET_N": (*no_bias_with_extra_output.nets["RESET_N"], "U4.1"),
                },
            }
        )
        undisclosed_driver = control_input_bias_heuristic_coverage(
            no_bias_with_extra_output,
            netlist_sha256="a" * 64,
            source_path="projects/synthetic/electrical.json",
            source_sha256="b" * 64,
            state="required",
            spec=control_requirement(bias_mode="external"),
        )
        self.assertEqual(undisclosed_driver.status, "OPEN")
        self.assertTrue(any("drivers:" in issue for issue in undisclosed_driver.entries[0].issues))
        driver_report = evaluate(
            "synthetic-control-bias",
            coach(no_bias_with_extra_output),
            DesignLintPolicy(),
            control_input_bias_coverage=undisclosed_driver,
        )
        self.assertIn(rule_id, {item.rule_id for item in driver_report.findings})

        partial_source = source.model_copy(
            update={
                "nets": {
                    **source.nets,
                    "RESET_N": (*source.nets["RESET_N"], "U1.8"),
                },
                "pin_functions": {
                    **source.pin_functions,
                    "U1.8": "RST#",
                },
                "pin_electrical_types": {
                    **source.pin_electrical_types,
                    "U1.8": "input",
                },
                "component_pin_numbers": {
                    **source.component_pin_numbers,
                    "U1": (*source.component_pin_numbers["U1"], "8"),
                },
            }
        )
        partial_coverage = control_input_bias_heuristic_coverage(
            partial_source,
            netlist_sha256="a" * 64,
            source_path="projects/synthetic/electrical.json",
            source_sha256="b" * 64,
            state="required",
            spec=control_requirement(bias_mode="external"),
        )
        self.assertEqual(partial_coverage.status, "OPEN")
        self.assertIn("U1.8", partial_coverage.entries[0].control_pins)
        self.assertIsNone(partial_coverage.entries[0].signal_id)
        partial_report = evaluate(
            "synthetic-control-bias",
            coach(partial_source),
            DesignLintPolicy(),
            control_input_bias_coverage=partial_coverage,
        )
        self.assertIn(rule_id, {item.rule_id for item in partial_report.findings})

    def test_connected_control_bias_finding_is_order_stable_and_direct_resistor_clears_it(
        self,
    ) -> None:
        source = control_input_pins(connected=True, visible_bias=False)
        original = evaluate("synthetic-control-bias", coach(source), DesignLintPolicy())
        rule_id = "control.connected_control_input_without_visible_bias"
        original_findings = {
            item.evidence["net"][0]: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered = evaluate("synthetic-control-bias", coach(reordered_source), DesignLintPolicy())
        reordered_findings = {
            item.evidence["net"][0]: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired = with_control_resistor(
            source,
            signal_net="RESET_LINE",
            rail_net="+3V3",
        )
        repaired_report = evaluate("synthetic-control-bias", coach(repaired), DesignLintPolicy())
        repaired_findings = {
            item.evidence["net"][0]: (item.fingerprint, item.evidence)
            for item in repaired_report.findings
            if item.rule_id == rule_id
        }
        expected = dict(original_findings)
        del expected["RESET_LINE"]
        self.assertEqual(repaired_findings, expected)

    def test_control_input_candidates_are_order_stable_and_each_assignment_clears_one(self) -> None:
        base = control_input_pins()
        source = base.model_copy(
            update={
                "nets": {
                    "GPIO_CONTROL": ("U1.4",),
                    "RESET_OUTPUT": ("U1.7",),
                }
            }
        )
        original = evaluate("synthetic-control-inputs", coach(source), DesignLintPolicy())
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
                "unconnected_nets": dict(reversed(tuple(source.unconnected_nets.items()))),
            }
        )
        reordered = evaluate(
            "synthetic-control-inputs", coach(reordered_source), DesignLintPolicy()
        )

        rule_id = "control.unconnected_control_input"
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 9)
        self.assertEqual(reordered_findings, original_findings)

        for subject, finding in original_findings.items():
            pin = subject.split(":", maxsplit=1)[0]
            remaining_unconnected: dict[str, tuple[str, ...]] = {}
            found_unconnected_pin = False
            for net_name, pins in source.unconnected_nets.items():
                remaining = tuple(candidate for candidate in pins if candidate != pin)
                found_unconnected_pin |= len(remaining) != len(pins)
                if remaining:
                    remaining_unconnected[net_name] = remaining
            self.assertTrue(found_unconnected_pin, pin)
            assigned = source.model_copy(
                update={
                    "nets": {
                        **source.nets,
                        f"ASSIGNED_{pin.replace('.', '_')}": (pin,),
                    },
                    "unconnected_nets": remaining_unconnected,
                }
            )
            assigned_report = evaluate(
                "synthetic-control-inputs", coach(assigned), DesignLintPolicy()
            )
            remaining_findings = {
                item.subject: (item.fingerprint, item.evidence)
                for item in assigned_report.findings
                if item.rule_id == rule_id
            }
            expected = dict(original_findings)
            del expected[subject]
            self.assertEqual(remaining_findings, expected, finding)
