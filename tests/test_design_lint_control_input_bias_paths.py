"""Series-resistor topology controls for connected control-input review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import ComponentContract, DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures import coach, control_input_pins, with_control_resistor

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
]

RULE_ID = "control.connected_control_input_without_visible_bias"


def _candidate_nets(netlist: NetlistContract) -> set[str]:
    report = evaluate("synthetic-control-bias-path", coach(netlist), DesignLintPolicy())
    return {item.evidence["net"][0] for item in report.findings if item.rule_id == RULE_ID}


def _series_bias(
    netlist: NetlistContract, rail_net: str, *, second_value: str = "10k"
) -> NetlistContract:
    first = with_control_resistor(
        netlist,
        signal_net="RESET_LINE",
        rail_net="RESET_BIAS_MID",
        reference="R20",
    )
    return with_control_resistor(
        first,
        signal_net="RESET_BIAS_MID",
        rail_net=rail_net,
        reference="R21",
        value=second_value,
    )


@pytest.mark.parametrize("rail_net", ("+3V3", "GND"))
def test_unbranched_fitted_resistor_chain_clears_control_bias_prompt(rail_net: str) -> None:
    base = control_input_pins(connected=True, visible_bias=False)
    assert "RESET_LINE" in _candidate_nets(base)

    chain = _series_bias(base, rail_net)
    assert "RESET_LINE" not in _candidate_nets(chain)

    dnp = chain.model_copy(update={"dnp_components": ("R21",)})
    assert "RESET_LINE" in _candidate_nets(dnp)

    zero_ohm = _series_bias(base, rail_net, second_value="0")
    assert "RESET_LINE" in _candidate_nets(zero_ohm)

    branched = chain.model_copy(
        update={
            "components": {
                **chain.components,
                "TP1": ComponentContract(value="Synthetic test point", footprint=""),
            },
            "component_symbols": {
                **chain.component_symbols,
                "TP1": "Connector:TestPoint",
            },
            "component_pin_numbers": {
                **chain.component_pin_numbers,
                "TP1": ("1",),
            },
            "pin_functions": {**chain.pin_functions, "TP1.1": "TP"},
            "pin_electrical_types": {**chain.pin_electrical_types, "TP1.1": "passive"},
            "nets": {
                **chain.nets,
                "RESET_BIAS_MID": (*chain.nets["RESET_BIAS_MID"], "TP1.1"),
            },
        }
    )
    assert "RESET_LINE" in _candidate_nets(branched)
