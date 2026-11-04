"""Keep complete connector peer pin inventories named and read-only."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import cast

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_groups import (
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
