"""Synthetic open-collector and open-emitter bias heuristic controls."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate, fingerprint, rule_catalog
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.open_drain_heuristics import open_output_bias_gaps
from tests.design_lint_fixtures import coach

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
]


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


def series_bias_netlist(
    *,
    output_type: str = "open_collector",
    rail: str = "+3V3",
    branch: bool = False,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    observed = signal_netlist(output_type=output_type)
    components = dict(observed.components)
    components["R1"] = ComponentContract(value="4.7k", footprint="Synthetic:Resistor")
    components["R2"] = ComponentContract(value="10k", footprint="Synthetic:Resistor")
    nets = {
        "ALERT_N": ("U1.1", "U2.1", "R1.1"),
        "BIAS_MID": ("R1.2", "R2.1"),
        rail: ("R2.2",),
    }
    pin_functions = dict(observed.pin_functions)
    pin_functions.update({"R2.1": "1", "R2.2": "2"})
    pin_types = dict(observed.pin_electrical_types)
    pin_types.update({"R2.1": "passive", "R2.2": "passive"})
    pin_numbers = dict(observed.component_pin_numbers)
    pin_numbers["R2"] = ("1", "2")
    symbols = dict(observed.component_symbols)
    symbols["R2"] = "Device:R"
    if branch:
        components["U3"] = ComponentContract(value="Synthetic branch", footprint="Synthetic:Probe")
        nets["BIAS_MID"] = (*nets["BIAS_MID"], "U3.1")
        pin_functions["U3.1"] = "BIAS_BRANCH"
        pin_types["U3.1"] = "input"
        pin_numbers["U3"] = ("1",)
        symbols["U3"] = "Synthetic:Input"
    return observed.model_copy(
        update={
            "components": components,
            "nets": nets,
            "dnp_components": dnp,
            "component_symbols": symbols,
            "pin_functions": pin_functions,
            "pin_electrical_types": pin_types,
            "component_pin_numbers": pin_numbers,
        }
    )


def test_open_collector_signal_without_visible_pullup_is_review_candidate() -> None:
    observed = signal_netlist()

    gaps = open_output_bias_gaps(observed)
    findings = candidates(observed, rule_catalog())

    assert len(gaps) == 1
    assert gaps[0].net == "ALERT_N"
    assert gaps[0].bias == "pull_up"
    assert gaps[0].output_pins == ("U1.1",)
    assert gaps[0].input_pins == ("U2.1",)
    finding = next(
        item
        for item in findings
        if item.rule_id == "signal.open_collector_input_without_visible_bias"
    )
    assert "does not establish that a resistor is required" in finding.message


def test_rule_policy_can_review_block_disable_and_exactly_ignore_candidate() -> None:
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

    assert baseline.findings[0].mode == "review"
    assert baseline.findings[0].disposition == "OPEN"
    assert blocked.status == "FAIL"
    assert blocked.findings[0].mode == "block"
    assert disabled.findings[0].disposition == "RULE_OFF"
    assert ignored.findings[0].disposition == "IGNORED"


def test_open_emitter_has_an_independent_policy_and_ignore_identity() -> None:
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

    assert report.findings[0].rule_id == "signal.open_emitter_input_without_visible_bias"
    assert report.findings[0].mode == "review"
    assert blocked.status == "FAIL"
    assert blocked.findings[0].mode == "block"
    assert ignored.findings[0].disposition == "IGNORED"


def test_expected_bias_polarity_clears_only_matching_open_output() -> None:
    collector_with_pullup = signal_netlist(resistor_net="+3V3")
    collector_with_pulldown = signal_netlist(resistor_net="GND")
    emitter_without_pulldown = signal_netlist(output_type="open_emitter")
    emitter_with_pulldown = signal_netlist(output_type="open_emitter", resistor_net="GND")

    assert open_output_bias_gaps(collector_with_pullup) == ()
    collector_gap = open_output_bias_gaps(collector_with_pulldown)
    assert len(collector_gap) == 1
    assert collector_gap[0].visible_resistors == ("R1 (10000 Ω): ALERT_N ↔ GND",)
    assert open_output_bias_gaps(emitter_without_pulldown)[0].bias == "pull_down"
    assert open_output_bias_gaps(emitter_with_pulldown) == ()
    collector_findings = candidates(collector_with_pulldown, rule_catalog())
    emitter_findings = candidates(emitter_without_pulldown, rule_catalog())
    assert "signal.open_collector_input_without_visible_bias" in {
        item.rule_id for item in collector_findings
    }
    assert "signal.open_emitter_input_without_visible_bias" in {
        item.rule_id for item in emitter_findings
    }


@pytest.mark.parametrize(
    ("output_type", "rail", "rule_id"),
    (
        ("open_collector", "+3V3", "signal.open_collector_input_without_visible_bias"),
        ("open_emitter", "GND", "signal.open_emitter_input_without_visible_bias"),
    ),
)
def test_unbranched_series_bias_path_satisfies_visible_bias_review(
    output_type: str, rail: str, rule_id: str
) -> None:
    observed = series_bias_netlist(output_type=output_type, rail=rail)

    assert open_output_bias_gaps(observed) == ()
    assert rule_id not in {item.rule_id for item in candidates(observed, rule_catalog())}


@pytest.mark.parametrize(
    ("output_type", "rail", "expected_bias"),
    (
        ("open_collector", "+3V3", "pull_up"),
        ("open_emitter", "GND", "pull_down"),
    ),
)
def test_branched_or_unfitted_series_bias_path_remains_a_review_candidate(
    output_type: str, rail: str, expected_bias: str
) -> None:
    branched = series_bias_netlist(output_type=output_type, rail=rail, branch=True)
    unfitted = series_bias_netlist(output_type=output_type, rail=rail, dnp=("R2",))

    assert open_output_bias_gaps(branched)[0].bias == expected_bias
    assert open_output_bias_gaps(unfitted)[0].bias == expected_bias


@pytest.mark.parametrize(
    ("output_type", "rail", "expected_bias"),
    (
        ("open_collector", "GND", "pull_up"),
        ("open_emitter", "+3V3", "pull_down"),
    ),
)
def test_series_resistor_path_does_not_satisfy_the_opposite_bias_polarity(
    output_type: str, rail: str, expected_bias: str
) -> None:
    observed = series_bias_netlist(output_type=output_type, rail=rail)

    gaps = open_output_bias_gaps(observed)

    assert len(gaps) == 1
    assert gaps[0].bias == expected_bias


def test_specialized_buses_and_dnp_outputs_stay_with_existing_rules() -> None:
    i2c = signal_netlist(output_function="SDA", input_function="I2C_SDA", output_net="I2C_SDA")
    reset = signal_netlist(output_function="RESET_N", input_function="RESET_N")
    chip_select = signal_netlist(output_function="CS_N", input_function="CS_N")
    dnp_output = signal_netlist(dnp=("U1",))
    no_receiver = signal_netlist().model_copy(
        update={"nets": {"ALERT_N": ("U1.1",), "+3V3": (), "GND": ()}}
    )

    assert open_output_bias_gaps(i2c) == ()
    assert open_output_bias_gaps(reset) == ()
    assert open_output_bias_gaps(chip_select) == ()
    assert open_output_bias_gaps(dnp_output) == ()
    assert open_output_bias_gaps(no_receiver) == ()


@pytest.mark.parametrize(
    ("output_type", "expected_rule"),
    (
        ("open_collector", "signal.open_collector_input_without_visible_bias"),
        ("open_emitter", "signal.open_emitter_input_without_visible_bias"),
    ),
)
def test_net_order_does_not_change_open_output_bias_rule_identity(
    output_type: str, expected_rule: str
) -> None:
    observed = signal_netlist(output_type=output_type)
    reversed_nets = observed.model_copy(
        update={"nets": dict(reversed(tuple(observed.nets.items())))}
    )
    findings = candidates(observed, rule_catalog())
    reversed_findings = candidates(reversed_nets, rule_catalog())
    assert tuple(item.rule_id for item in findings) == tuple(
        item.rule_id for item in reversed_findings
    )
    assert tuple(item.rule_id for item in findings) == (expected_rule,)

    rail = "GND" if output_type == "open_emitter" else "+3V3"
    series = series_bias_netlist(output_type=output_type, rail=rail)
    reordered_series = series.model_copy(
        update={"nets": dict(reversed(tuple(series.nets.items())))}
    )
    assert open_output_bias_gaps(series) == open_output_bias_gaps(reordered_series) == ()
