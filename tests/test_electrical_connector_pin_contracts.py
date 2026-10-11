"""Pytest coverage for authored connector-pin relationships."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.connector_pins import similar_connector_pin_groups
from kicad_tooling.hwrepo.electrical import pin_relationship_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    NetlistContract,
    PinConnectivityAnalysis,
    PinRelationshipRule,
)
from kicad_tooling.validate import read_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]

FIXTURES = Path(__file__).parent / "fixtures" / "design_lint" / "connector-power-pin-assignment"


def test_repeated_connector_power_pin_missing_from_net_requires_review() -> None:
    observed = read_netlist(FIXTURES / "netlist.xml")

    assert observed.unconnected_nets == {"unconnected-(J3-PWR-Pad1)": ("J3.1",)}
    assert observed.pin_functions["J3.1"] == "PWR"
    groups = similar_connector_pin_groups(observed)
    assert len(groups) == 1
    assert groups[0].function == "PWR"
    assert groups[0].pins["J3.1"] == ()

    requirement = PinConnectivityAnalysis(
        basis="Approved synthetic three-port power pinout",
        rules=(
            PinRelationshipRule(
                id="port-power",
                basis="All three connector power pins share the approved rail",
                topology="common_net",
                pins=("J1.1", "J2.1", "J3.1"),
                net="+5V",
            ),
        ),
    )
    assert pin_relationship_checks(requirement, observed)[0].status == "FAIL"

    connected = observed.model_copy(
        update={"nets": {**observed.nets, "+5V": ("J1.1", "J2.1", "J3.1")}}
    )
    assert not similar_connector_pin_groups(connected)
    assert pin_relationship_checks(requirement, connected)[0].status == "PASS"

    wrong_rail = connected.model_copy(
        update={"nets": {"+12V": connected.nets["+5V"], "GND": connected.nets["GND"]}}
    )
    assert pin_relationship_checks(requirement, wrong_rail)[0].status == "FAIL"

    unused = PinConnectivityAnalysis(
        basis="Synthetic connector pin disposition",
        rules=(
            PinRelationshipRule(
                id="unpopulated-power",
                basis="J3.1 is intentionally unused on this approved variant",
                topology="unconnected",
                pins=("J3.1",),
            ),
        ),
    )
    assert pin_relationship_checks(unused, observed)[0].status == "PASS"
    assert pin_relationship_checks(unused, connected)[0].status == "FAIL"


def test_same_connector_power_labels_can_require_separate_nets() -> None:
    observed = NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic port", footprint="")
            for reference in ("J1", "J2")
        },
        nets={"PORT1_PWR": ("J1.1",), "PORT2_PWR": ("J2.1",)},
        component_symbols={"J1": "Synthetic:Port", "J2": "Synthetic:Port"},
        pin_functions={"J1.1": "PWR", "J2.1": "PWR"},
    )
    assert len(similar_connector_pin_groups(observed)) == 1

    separate = PinConnectivityAnalysis(
        basis="Approved independently switched outputs",
        rules=(
            PinRelationshipRule(
                id="independent-power",
                basis="Each connector has an independent output",
                topology="separate_nets",
                pins=("J1.1", "J2.1"),
            ),
        ),
    )
    assert pin_relationship_checks(separate, observed)[0].status == "PASS"
    tied = observed.model_copy(update={"nets": {"PORT1_PWR": ("J1.1", "J2.1")}})
    assert pin_relationship_checks(separate, tied)[0].status == "FAIL"

    with pytest.raises(ValueError):
        PinRelationshipRule(
            id="invalid",
            basis="Contradictory rule",
            topology="separate_nets",
            pins=("J1.1", "J2.1"),
            net="+5V",
        )


def test_pin_relationship_can_require_an_intentionally_unconnected_pin() -> None:
    observed = NetlistContract(
        components={"J1": ComponentContract(value="Synthetic port", footprint="")},
        nets={"SIGNAL": ("J1.1",)},
        component_pin_numbers={"J1": ("1", "2")},
    )
    requirement = PinConnectivityAnalysis(
        basis="Approved synthetic connector pin disposition",
        rules=(
            PinRelationshipRule(
                id="reserved-pin",
                basis="Pin 2 is intentionally unused on this assembly",
                topology="unconnected",
                pins=("J1.2",),
            ),
        ),
    )
    assert pin_relationship_checks(requirement, observed)[0].status == "PASS"

    newly_connected = observed.model_copy(
        update={"nets": {**observed.nets, "SIGNAL": ("J1.1", "J1.2")}}
    )
    changed = pin_relationship_checks(requirement, newly_connected)[0]
    assert changed.status == "FAIL"
    assert "J1.2" in changed.detail

    stale_pin = requirement.model_copy(
        update={"rules": (requirement.rules[0].model_copy(update={"pins": ("J1.3",)}),)}
    )
    stale = pin_relationship_checks(stale_pin, observed)[0]
    assert stale.status == "FAIL"
    assert "unknown symbol pins=['J1.3']" in stale.detail

    with pytest.raises(ValueError):
        PinRelationshipRule(
            id="single-common-pin",
            basis="A common relationship requires multiple pins",
            topology="common_net",
            pins=("J1.1",),
        )
    with pytest.raises(ValueError):
        PinRelationshipRule(
            id="unused-with-net",
            basis="An unused pin cannot have a required net",
            topology="unconnected",
            pins=("J1.2",),
            net="GND",
        )
