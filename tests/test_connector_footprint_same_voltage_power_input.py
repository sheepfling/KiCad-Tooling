"""Review unanchored connector power inputs with matching voltage labels."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.connector_footprint_peer_support import lint_report, peer_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.footprint_same_voltage_power_input_unanchored"


def _netlist(
    *,
    first_net: str = "+3V3",
    second_net: str = "3.3V",
    function: str = "VBUS",
    electrical_type: str = "power_in",
    anchor: tuple[str | None, str | None] = ("PORT_A", "PORT_B"),
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
    incomplete_inventory: bool = False,
) -> NetlistContract:
    return peer_netlist(
        assignments=(anchor, (first_net, second_net)),
        functions=("UART_TX", function),
        electrical_types=("output", electrical_type),
        dnp=dnp,
        part_id=part_id,
        incomplete_inventory=incomplete_inventory,
    )


def _enabled_report(source: NetlistContract):
    return lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic fixture explicitly enables the heuristic.",
                ),
            )
        ),
    )


def test_unanchored_peer_power_inputs_with_equal_voltage_labels_are_reviewed() -> None:
    source = _netlist()
    report = lint_report(source)
    off_finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert off_finding.disposition == "RULE_OFF"

    reviewed = _enabled_report(source)
    finding = next(item for item in reviewed.findings if item.rule_id == RULE_ID)
    assert finding.disposition == "OPEN"
    assert finding.evidence["nominal_voltage_v"] == ("3.3",)
    assert finding.evidence["assignments"] == ("J1.2=+3V3", "J2.2=3.3V")
    assert "do not prove these domains should be joined" in finding.message


def test_different_voltages_common_net_and_ineligible_pin_roles_are_controls() -> None:
    controls = (
        _netlist(second_net="5V"),
        _netlist(first_net="+3V3", second_net="+3V3"),
        _netlist(anchor=("COMMON", "COMMON")),
        _netlist(electrical_type="passive"),
        _netlist(function="GND"),
        _netlist(dnp=("J2",)),
        _netlist(part_id="SYNTHETIC-POWER-PEER-001"),
        _netlist(incomplete_inventory=True),
        _netlist(second_net="UNKNOWN_RAIL"),
    )
    for source in controls:
        assert RULE_ID not in {item.rule_id for item in _enabled_report(source).findings}


def test_equal_voltage_peer_prompt_is_stable_under_mapping_order() -> None:
    source = _netlist()
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
    first = next(item for item in _enabled_report(source).findings if item.rule_id == RULE_ID)
    second = next(item for item in _enabled_report(reordered).findings if item.rule_id == RULE_ID)
    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
