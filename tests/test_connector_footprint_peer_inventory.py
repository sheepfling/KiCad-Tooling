"""Keep complete connector peer pin inventories named and read-only."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import cast

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_groups import (
    complete_connector_footprint_peer_pin_inventories,
    complete_connector_footprint_peer_pin_inventory,
)
from tests.connector_footprint_peer_support import peer_metadata_divergence_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.architecture,
]


def test_complete_inventory_names_shared_and_native_pin_numbers() -> None:
    inventory = complete_connector_footprint_peer_pin_inventory(
        peer_metadata_divergence_netlist(),
        ("J1", "J2"),
    )

    assert inventory is not None
    assert inventory.pin_numbers == ("1", "2")
    assert inventory.displayed_numbers_by_reference == {
        "j1": {"1": "1", "2": "2"},
        "j2": {"1": "1", "2": "2"},
    }


def test_inventory_display_number_views_cannot_be_mutated() -> None:
    inventory = complete_connector_footprint_peer_pin_inventory(
        peer_metadata_divergence_netlist(),
        ("J1", "J2"),
    )

    assert inventory is not None
    displayed = cast(
        MutableMapping[str, MutableMapping[str, str]],
        inventory.displayed_numbers_by_reference,
    )
    with pytest.raises(TypeError):
        displayed["j1"]["1"] = "changed"
    with pytest.raises(TypeError):
        displayed["j3"] = {"1": "1"}


def test_complete_inventories_preserve_a_peer_pin_difference() -> None:
    observed = peer_metadata_divergence_netlist().model_copy(
        update={
            "component_pin_numbers": {
                "J1": ("1", "2"),
                "J2": ("1", "2", "3"),
            },
            "pin_functions": {
                **peer_metadata_divergence_netlist().pin_functions,
                "J2.3": "VBUS",
            },
            "pin_electrical_types": {
                **peer_metadata_divergence_netlist().pin_electrical_types,
                "J2.3": "power_in",
            },
        }
    )

    inventories = complete_connector_footprint_peer_pin_inventories(observed, ("J1", "J2"))

    assert inventories is not None
    assert inventories.displayed_numbers_by_reference == {
        "j1": {"1": "1", "2": "2"},
        "j2": {"1": "1", "2": "2", "3": "3"},
    }
    assert complete_connector_footprint_peer_pin_inventory(observed, ("J1", "J2")) is None


def test_complete_inventories_reject_observed_pins_missing_from_the_inventory() -> None:
    observed = peer_metadata_divergence_netlist().model_copy(
        update={
            "component_pin_numbers": {"J1": ("1", "2"), "J2": ("1", "2")},
            "pin_functions": {
                **peer_metadata_divergence_netlist().pin_functions,
                "J2.3": "VBUS",
            },
        }
    )

    assert complete_connector_footprint_peer_pin_inventories(observed, ("J1", "J2")) is None
