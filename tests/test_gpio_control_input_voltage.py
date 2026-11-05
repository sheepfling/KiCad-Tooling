"""Review direct GPIO drives into control pins across named supply rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate, fingerprint
from kicad_tooling.hwrepo.digital_peer_voltage_models import (
    DigitalLogicInputLimits,
    DigitalLogicOutputLimits,
    DigitalPeerPinRequirement,
    DigitalPeerVoltageAnalysis,
    DigitalPeerVoltageLink,
)
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.power_gpio_control_voltage import (
    gpio_to_control_input_voltage_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.gpio_control_voltage import gpio_control_voltage_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
]

RULE_ID = "power.gpio_to_control_input_voltage_review"


def _finding(source: NetlistContract):
    return next(item for item in candidates(source) if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("output_function", "input_function"),
    (
        pytest.param("GPIO0", "EN", id="numbered-gpio-to-enable"),
        pytest.param("PA0", "RESET_N", id="port-pin-to-reset"),
        pytest.param("IO2", "BOOT0", id="io-pin-to-boot-strap"),
    ),
)
def test_higher_named_gpio_rail_to_control_input_requests_review(
    output_function: str, input_function: str
) -> None:
    source = gpio_control_voltage_netlist(
        output_function=output_function,
        input_function=input_function,
    )

    finding = _finding(source)

    assert finding.subject == "U1.1 -> U2.1: GPIO-to-control voltage-domain review"
    assert finding.evidence == {
        "signal_net": ("CONTROL_SIGNAL",),
        "GPIO_output": (f"U1.1: {output_function} (Synthetic:MCU)",),
        "control_input": (f"U2.1: {input_function} (Synthetic:Regulator)",),
        "output_supply_label": ("+5V: 5 V",),
        "input_supply_label": ("+3V3: 3.3 V",),
    }
    assert "do not establish" in finding.message
    assert "does not require level translation" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "source",
    (
        pytest.param(
            gpio_control_voltage_netlist(output_rail="+3V3", input_rail="+3V3"), id="same-rail"
        ),
        pytest.param(
            gpio_control_voltage_netlist(output_rail="+3V3", input_rail="+5V"),
            id="lower-source-rail",
        ),
        pytest.param(gpio_control_voltage_netlist(dnp=("U2",)), id="dnp-receiver"),
        pytest.param(gpio_control_voltage_netlist(dnp=("U1",)), id="dnp-driver"),
        pytest.param(gpio_control_voltage_netlist(output_type="tri_state"), id="tri-state-driver"),
        pytest.param(
            gpio_control_voltage_netlist(input_type="bidirectional"), id="ambiguous-input-direction"
        ),
        pytest.param(gpio_control_voltage_netlist(output_function="SCK"), id="non-gpio-output"),
        pytest.param(gpio_control_voltage_netlist(input_function="GPIO0"), id="non-control-input"),
        pytest.param(
            gpio_control_voltage_netlist(input_function="BOOTSTRAP"), id="power-stage-bootstrap"
        ),
        pytest.param(
            gpio_control_voltage_netlist(missing_pin_type="U2.3"), id="incomplete-type-inventory"
        ),
        pytest.param(
            gpio_control_voltage_netlist(extra_input_supply=True), id="multiple-input-supplies"
        ),
        pytest.param(
            gpio_control_voltage_netlist(signal_net="+5V"), id="voltage-net-is-not-signal"
        ),
        pytest.param(
            gpio_control_voltage_netlist(signal_net="GND_CONTROL"), id="return-net-is-not-signal"
        ),
    ),
)
def test_incomplete_or_intentional_cases_remain_quiet(source: NetlistContract) -> None:
    assert RULE_ID not in {item.rule_id for item in candidates(source)}


def _exact_voltage_map() -> DigitalPeerVoltageAnalysis:
    return DigitalPeerVoltageAnalysis(
        basis="Synthetic reviewed GPIO-to-control limits",
        links=(
            DigitalPeerVoltageLink(
                id="gpio-enable",
                basis="Synthetic component data sheets with full operating conditions",
                driver=DigitalPeerPinRequirement(
                    reference="U1",
                    symbol="Synthetic:MCU",
                    footprint="Package:MCU",
                    pin="U1.1",
                    net="CONTROL_SIGNAL",
                ),
                receiver=DigitalPeerPinRequirement(
                    reference="U2",
                    symbol="Synthetic:Regulator",
                    footprint="Package:LDO",
                    pin="U2.1",
                    net="CONTROL_SIGNAL",
                ),
                output_limits=DigitalLogicOutputLimits(
                    low_minimum_v=0,
                    low_maximum_v=0.4,
                    high_minimum_v=2.2,
                    high_maximum_v=3.3,
                    source="Synthetic MCU data sheet, Table 1",
                    conditions="VDD=5 V, specified load",
                ),
                input_limits=DigitalLogicInputLimits(
                    absolute_minimum_v=-0.3,
                    low_maximum_v=0.8,
                    high_minimum_v=2.0,
                    absolute_maximum_v=5.5,
                    source="Synthetic regulator data sheet, Table 2",
                    conditions="VIN=3.3 V, full temperature range",
                ),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_exact_voltage_map_suppresses_only_current_gpio_link() -> None:
    source = gpio_control_voltage_netlist()
    exact_map = _exact_voltage_map()
    stale_link = exact_map.links[0].model_copy(
        update={"receiver": exact_map.links[0].receiver.model_copy(update={"pin": "U2.9"})}
    )
    stale_map = exact_map.model_copy(update={"links": (stale_link,)})
    partial_link = exact_map.links[0].model_copy(update={"input_limits": None})
    partial_map = exact_map.model_copy(update={"links": (partial_link,)})

    assert not gpio_to_control_input_voltage_candidates(source, exact_map)
    assert gpio_to_control_input_voltage_candidates(source, partial_map)
    assert gpio_to_control_input_voltage_candidates(source, stale_map)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_policy_can_block_turn_off_or_ignore_exact_finding() -> None:
    source = gpio_control_voltage_netlist()
    default = evaluate("gpio-control-voltage", coach(source), DesignLintPolicy())
    finding = next(item for item in default.findings if item.rule_id == RULE_ID)
    blocked = evaluate(
        "gpio-control-voltage",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Review direct GPIO levels against control-pin limits",
                ),
            )
        ),
    )
    disabled = evaluate(
        "gpio-control-voltage",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="This project has reviewed GPIO compatibility elsewhere",
                ),
            )
        ),
    )
    ignored = evaluate(
        "gpio-control-voltage",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic exact-fingerprint review disposition",
                ),
            )
        ),
    )

    assert default.status == "REVIEW"
    assert blocked.status == "FAIL"
    assert any(item.mode == "block" for item in blocked.findings if item.rule_id == RULE_ID)
    assert any(
        item.disposition == "RULE_OFF" for item in disabled.findings if item.rule_id == RULE_ID
    )
    assert any(
        item.disposition == "IGNORED" for item in ignored.findings if item.rule_id == RULE_ID
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_gpio_voltage_fingerprint_is_stable_under_mapping_reordering() -> None:
    source = gpio_control_voltage_netlist()
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

    first = _finding(source)
    second = _finding(reordered)

    assert (fingerprint(second), second.evidence) == (fingerprint(first), first.evidence)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_lower_voltage_gpio_control_remains_a_valid_review_control() -> None:
    source = gpio_control_voltage_netlist(output_rail="+3V3", input_rail="+5V")

    assert RULE_ID not in {item.rule_id for item in candidates(source)}
