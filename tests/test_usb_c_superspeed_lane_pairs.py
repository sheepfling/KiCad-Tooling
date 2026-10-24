"""Regressions for lane-indexed USB-C SuperSpeed complementary pairs."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, fingerprint
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures.usb_c_superspeed_lanes import (
    usb_c_superspeed_lane_fault_netlist,
    usb_c_superspeed_lane_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.complementary_pair_assignment"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_lane_indexed_usb_c_pair_same_net_is_reviewed() -> None:
    findings = tuple(
        item for item in candidates(usb_c_superspeed_lane_fault_netlist()) if item.rule_id == RULE_ID
    )

    assert len(findings) == 1
    assert findings[0].subject == "J1: USB SuperSpeed TX lane 1 pair"
    assert findings[0].evidence == {
        "positive_pins": ("J1.1",),
        "negative_pins": ("J1.2",),
        "positive_nets": ("USB_TX1_SHORT",),
        "negative_nets": ("USB_TX1_SHORT",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_lane_indexed_usb_c_pairs_remain_separate_by_lane_and_direction() -> None:
    control = usb_c_superspeed_lane_netlist()

    assert not any(item.rule_id == RULE_ID for item in candidates(control))

    open_lane = usb_c_superspeed_lane_netlist(open_pin="J1.4")
    findings = tuple(item for item in candidates(open_lane) if item.rule_id == RULE_ID)
    assert len(findings) == 1
    assert findings[0].subject == "J1: USB SuperSpeed TX lane 2 pair"
    assert findings[0].evidence["negative_pins"] == ("J1.4",)
    assert findings[0].evidence["negative_nets"] == ()

    assert not any(
        item.rule_id == RULE_ID for item in candidates(usb_c_superspeed_lane_netlist(dnp=True))
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_lane_names_and_unknown_usb_c_lane_are_not_classified() -> None:
    generic = NetlistContract(
        components={},
        nets={"TX1P": ("J1.1",), "TX1N": ("J1.2",)},
        component_symbols={"J1": "Connector:USB_C_Receptacle_24P"},
        pin_functions={"J1.1": "TX1+", "J1.2": "TX1−"},
    )
    unknown_lane = usb_c_superspeed_lane_netlist().model_copy(
        update={
            "pin_functions": {
                pin: function.replace("1", "3").replace("2", "3")
                for pin, function in usb_c_superspeed_lane_netlist().pin_functions.items()
            }
        }
    )

    assert not any(item.rule_id == RULE_ID for item in candidates(generic))
    assert not any(item.rule_id == RULE_ID for item in candidates(unknown_lane))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_lane_indexed_usb_c_pair_is_order_stable_and_assignment_repair_clears_it() -> None:
    source = usb_c_superspeed_lane_fault_netlist()
    expected = tuple(
        (item.subject, fingerprint(item), item.evidence)
        for item in candidates(source)
        if item.rule_id == RULE_ID
    )
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": {
                "J1": tuple(reversed(source.component_pin_numbers["J1"]))
            },
        }
    )
    actual = tuple(
        (item.subject, fingerprint(item), item.evidence)
        for item in candidates(reordered)
        if item.rule_id == RULE_ID
    )

    assert actual == expected
    assert not any(
        item.rule_id == RULE_ID for item in candidates(usb_c_superspeed_lane_netlist())
    )
