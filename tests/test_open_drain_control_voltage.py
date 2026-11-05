"""Open-collector control pull-up voltage review regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate, fingerprint
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.open_drain_control_voltage import (
    open_drain_control_voltage_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.power_lint]

RULE_ID = "power.open_drain_control_input_pullup_voltage_review"


def _findings(source: NetlistContract):
    return tuple(item for item in candidates(source) if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_collector_control_pullup_to_different_supply_requests_review() -> None:
    (finding,) = _findings(open_drain_control_voltage_netlist())

    assert finding.subject == (
        "U1.1 -> U2.1 on RESET_SIGNAL: open-collector pull-up voltage-domain review"
    )
    assert finding.evidence == {
        "signal_net": ("RESET_SIGNAL",),
        "open_collector_output": ("U1.1: GPIO0 (Synthetic:MCU)",),
        "control_input": ("U2.1: RESET_N (Synthetic:Receiver)",),
        "pullup_paths": ("R1 (10000 Ω): RESET_SIGNAL ↔ +5V",),
        "pullup_rail_label": ("+5V: 5 V",),
        "driver_supply_label": ("+3V3: 3.3 V",),
        "receiver_supply_label": ("+3V3: 3.3 V",),
        "pullup_label_relations": (
            "pullup_higher_than_driver",
            "pullup_higher_than_receiver",
        ),
    }
    assert "absolute maximum" in finding.message
    assert "do not establish actual voltage" in finding.message
    assert "does not require level translation" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_pullup_voltage_review_adds_detection_over_existing_bias_checks() -> None:
    existing_bias_rule_ids = {
        "control.connected_control_input_without_visible_bias",
        "signal.open_collector_input_without_visible_bias",
        "power.gpio_to_control_input_voltage_review",
    }
    fault_candidates = candidates(open_drain_control_voltage_netlist())
    control_candidates = candidates(
        open_drain_control_voltage_netlist(
            pullup_rail="+3V3", driver_rail="+3V3", receiver_rail="+3V3"
        )
    )
    fault_rule_ids = {item.rule_id for item in fault_candidates}
    control_rule_ids = {item.rule_id for item in control_candidates}

    assert existing_bias_rule_ids.isdisjoint(fault_rule_ids)
    assert RULE_ID in fault_rule_ids
    assert existing_bias_rule_ids.isdisjoint(control_rule_ids)
    assert RULE_ID not in control_rule_ids


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("pullup_rail", "driver_rail", "receiver_rail", "relation"),
    (
        pytest.param("+3V3", "+5V", "+5V", "pullup_lower_than_driver", id="lower-pullup"),
        pytest.param("+3V3", "+3V3", "+5V", "pullup_lower_than_receiver", id="differs-from-one"),
    ),
)
def test_pullup_rail_label_is_compared_to_each_endpoint_supply(
    pullup_rail: str,
    driver_rail: str,
    receiver_rail: str,
    relation: str,
) -> None:
    source = open_drain_control_voltage_netlist(
        pullup_rail=pullup_rail,
        driver_rail=driver_rail,
        receiver_rail=receiver_rail,
    )

    (finding,) = _findings(source)

    assert relation in finding.evidence["pullup_label_relations"]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_visible_pullups_to_one_rail_keep_the_review() -> None:
    source = open_drain_control_voltage_netlist(extra_pullup_rail="+5V")

    (finding,) = _findings(source)

    assert finding.evidence["pullup_paths"] == (
        "R1 (10000 Ω): RESET_SIGNAL ↔ +5V",
        "R2 (10000 Ω): RESET_SIGNAL ↔ +5V",
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "source",
    (
        pytest.param(
            open_drain_control_voltage_netlist(
                pullup_rail="+3V3", driver_rail="+3V3", receiver_rail="+3V3"
            ),
            id="same-voltage-labels",
        ),
        pytest.param(open_drain_control_voltage_netlist(resistor_dnp=True), id="dnp-pullup"),
        pytest.param(
            open_drain_control_voltage_netlist(extra_pullup_rail="+1V8"),
            id="ambiguous-multiple-pullup-rails",
        ),
        pytest.param(
            open_drain_control_voltage_netlist(driver_type="open_emitter"),
            id="open-emitter-is-not-open-collector",
        ),
        pytest.param(
            open_drain_control_voltage_netlist(receiver_function="GPIO0"),
            id="non-control-input",
        ),
        pytest.param(
            open_drain_control_voltage_netlist(receiver_type="bidirectional"),
            id="ambiguous-receiver-direction",
        ),
        pytest.param(
            open_drain_control_voltage_netlist(missing_pin_type="U2.3"),
            id="incomplete-native-pin-types",
        ),
        pytest.param(
            open_drain_control_voltage_netlist(pullup_rail="PULLUP"),
            id="unparsed-pullup-label",
        ),
    ),
)
def test_equal_or_ambiguous_cases_remain_quiet(source: NetlistContract) -> None:
    assert not _findings(source)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_policy_can_block_disable_or_ignore_exact_finding() -> None:
    source = open_drain_control_voltage_netlist()
    (finding,) = _findings(source)

    report = evaluate("open-drain-control", coach(source), DesignLintPolicy())
    blocked = evaluate(
        "open-drain-control",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Project-reviewed pull-up bounds require this prompt",
                ),
            ),
        ),
    )
    disabled = evaluate(
        "open-drain-control",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Project documents a separate voltage review",
                ),
            ),
        ),
    )
    ignored = evaluate(
        "open-drain-control",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint(finding),
                    reason="Exact synthetic finding disposition",
                ),
            ),
        ),
    )

    assert report.status == "REVIEW"
    assert blocked.status == "FAIL"
    assert any(item.mode == "block" for item in blocked.findings if item.rule_id == RULE_ID)
    assert any(
        item.disposition == "RULE_OFF" for item in disabled.findings if item.rule_id == RULE_ID
    )
    assert any(
        item.disposition == "IGNORED" for item in ignored.findings if item.rule_id == RULE_ID
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_drain_control_fingerprint_is_stable_under_mapping_reordering() -> None:
    source = open_drain_control_voltage_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )

    (first,) = _findings(source)
    (second,) = _findings(reordered)

    assert (fingerprint(second), second.evidence) == (fingerprint(first), first.evidence)
