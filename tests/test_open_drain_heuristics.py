"""Synthetic open-collector and open-emitter bias heuristic controls."""

from __future__ import annotations

import unittest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate, fingerprint, rule_catalog
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.open_drain_heuristics import open_output_bias_gaps
from tests.test_design_lint import coach


def signal_netlist(
    *,
    output_type: str = "open_collector",
    output_function: str = "ALERT_N",
    input_function: str = "ALERT_N",
    resistor_net: str | None = None,
    dnp: tuple[str, ...] = (),
    output_net: str = "ALERT_N",
) -> NetlistContract:
    components = {
        "U1": ComponentContract(value="Synthetic open output", footprint="Synthetic:Output"),
        "U2": ComponentContract(value="Synthetic input", footprint="Synthetic:Input"),
        "R1": ComponentContract(value="10k", footprint="Synthetic:Resistor"),
    }
    nets: dict[str, tuple[str, ...]] = {
        output_net: ("U1.1", "U2.1"),
        "+3V3": (),
        "GND": (),
    }
    pin_functions = {
        "U1.1": output_function,
        "U2.1": input_function,
        "R1.1": "1",
        "R1.2": "2",
    }
    pin_types = {
        "U1.1": output_type,
        "U2.1": "input",
        "R1.1": "passive",
        "R1.2": "passive",
    }
    if resistor_net is not None:
        nets[output_net] = (*nets[output_net], "R1.1")
        nets[resistor_net] = (*nets[resistor_net], "R1.2")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:OpenOutput",
            "U2": "Synthetic:Input",
            "R1": "Device:R",
        },
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers={"U1": ("1",), "U2": ("1",), "R1": ("1", "2")},
    )


class OpenDrainBiasHeuristicTests(unittest.TestCase):
    def test_open_collector_signal_without_visible_pullup_is_review_candidate(self) -> None:
        observed = signal_netlist()

        gaps = open_output_bias_gaps(observed)
        findings = candidates(observed, rule_catalog())

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].net, "ALERT_N")
        self.assertEqual(gaps[0].bias, "pull_up")
        self.assertEqual(gaps[0].output_pins, ("U1.1",))
        self.assertEqual(gaps[0].input_pins, ("U2.1",))
        finding = next(
            item
            for item in findings
            if item.rule_id == "signal.open_collector_input_without_visible_bias"
        )
        self.assertIn("does not establish that a resistor is required", finding.message)

    def test_rule_policy_can_review_block_disable_and_exactly_ignore_candidate(self) -> None:
        observed = signal_netlist()
        candidate = next(
            item
            for item in candidates(observed, rule_catalog())
            if item.rule_id == "signal.open_collector_input_without_visible_bias"
        )
        baseline = evaluate("synthetic-open-drain", coach(observed), DesignLintPolicy())
        blocked = evaluate(
            "synthetic-open-drain",
            coach(observed),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="signal.open_collector_input_without_visible_bias",
                        mode="block",
                        reason="Synthetic reviewed project policy promotes this hint.",
                    ),
                )
            ),
        )
        disabled = evaluate(
            "synthetic-open-drain",
            coach(observed),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="signal.open_collector_input_without_visible_bias",
                        mode="off",
                        reason="Synthetic reviewed project policy disables this hint.",
                    ),
                )
            ),
        )
        ignored = evaluate(
            "synthetic-open-drain",
            coach(observed),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id="signal.open_collector_input_without_visible_bias",
                        fingerprint=fingerprint(candidate),
                        reason="Synthetic board uses an internally biased receiver.",
                    ),
                )
            ),
        )

        self.assertEqual(baseline.findings[0].mode, "review")
        self.assertEqual(baseline.findings[0].disposition, "OPEN")
        self.assertEqual(blocked.status, "FAIL")
        self.assertEqual(blocked.findings[0].mode, "block")
        self.assertEqual(disabled.findings[0].disposition, "RULE_OFF")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")

    def test_open_emitter_has_an_independent_policy_and_ignore_identity(self) -> None:
        observed = signal_netlist(output_type="open_emitter")
        candidate = next(
            item
            for item in candidates(observed, rule_catalog())
            if item.rule_id == "signal.open_emitter_input_without_visible_bias"
        )
        report = evaluate("synthetic-open-emitter", coach(observed), DesignLintPolicy())
        blocked = evaluate(
            "synthetic-open-emitter",
            coach(observed),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="signal.open_emitter_input_without_visible_bias",
                        mode="block",
                        reason="Synthetic project policy promotes the open-emitter prompt.",
                    ),
                )
            ),
        )
        ignored = evaluate(
            "synthetic-open-emitter",
            coach(observed),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id="signal.open_emitter_input_without_visible_bias",
                        fingerprint=fingerprint(candidate),
                        reason="Synthetic receiver has a documented internal pull-down.",
                    ),
                )
            ),
        )

        self.assertEqual(
            report.findings[0].rule_id, "signal.open_emitter_input_without_visible_bias"
        )
        self.assertEqual(report.findings[0].mode, "review")
        self.assertEqual(blocked.status, "FAIL")
        self.assertEqual(blocked.findings[0].mode, "block")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")

    def test_expected_bias_polarity_clears_only_matching_open_output(self) -> None:
        collector_with_pullup = signal_netlist(resistor_net="+3V3")
        collector_with_pulldown = signal_netlist(resistor_net="GND")
        emitter_without_pulldown = signal_netlist(output_type="open_emitter")
        emitter_with_pulldown = signal_netlist(output_type="open_emitter", resistor_net="GND")

        self.assertEqual(open_output_bias_gaps(collector_with_pullup), ())
        collector_gap = open_output_bias_gaps(collector_with_pulldown)
        self.assertEqual(len(collector_gap), 1)
        self.assertEqual(collector_gap[0].visible_resistors, ("R1 (10000 Ω): ALERT_N ↔ GND",))
        self.assertEqual(
            open_output_bias_gaps(emitter_without_pulldown)[0].bias,
            "pull_down",
        )
        self.assertEqual(open_output_bias_gaps(emitter_with_pulldown), ())
        collector_findings = candidates(collector_with_pulldown, rule_catalog())
        emitter_findings = candidates(emitter_without_pulldown, rule_catalog())
        self.assertIn(
            "signal.open_collector_input_without_visible_bias",
            {item.rule_id for item in collector_findings},
        )
        self.assertIn(
            "signal.open_emitter_input_without_visible_bias",
            {item.rule_id for item in emitter_findings},
        )

    def test_specialized_buses_and_dnp_outputs_stay_with_existing_rules(self) -> None:
        i2c = signal_netlist(output_function="SDA", input_function="I2C_SDA", output_net="I2C_SDA")
        reset = signal_netlist(output_function="RESET_N", input_function="RESET_N")
        chip_select = signal_netlist(output_function="CS_N", input_function="CS_N")
        dnp_output = signal_netlist(dnp=("U1",))
        no_receiver = signal_netlist().model_copy(
            update={"nets": {"ALERT_N": ("U1.1",), "+3V3": (), "GND": ()}}
        )

        self.assertEqual(open_output_bias_gaps(i2c), ())
        self.assertEqual(open_output_bias_gaps(reset), ())
        self.assertEqual(open_output_bias_gaps(chip_select), ())
        self.assertEqual(open_output_bias_gaps(dnp_output), ())
        self.assertEqual(open_output_bias_gaps(no_receiver), ())

    def test_net_order_does_not_change_open_output_bias_rule_identity(self) -> None:
        for output_type, expected_rule in (
            ("open_collector", "signal.open_collector_input_without_visible_bias"),
            ("open_emitter", "signal.open_emitter_input_without_visible_bias"),
        ):
            with self.subTest(output_type=output_type):
                observed = signal_netlist(output_type=output_type)
                reversed_nets = observed.model_copy(
                    update={"nets": dict(reversed(tuple(observed.nets.items())))}
                )
                findings = candidates(observed, rule_catalog())
                reversed_findings = candidates(reversed_nets, rule_catalog())
                self.assertEqual(
                    tuple(item.rule_id for item in findings),
                    tuple(item.rule_id for item in reversed_findings),
                )
                self.assertEqual(tuple(item.rule_id for item in findings), (expected_rule,))


if __name__ == "__main__":
    unittest.main()
