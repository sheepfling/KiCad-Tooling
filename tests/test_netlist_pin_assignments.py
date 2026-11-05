"""Regressions for shared deterministic reverse pin/net projection."""

from __future__ import annotations

from collections.abc import MutableMapping
from types import MappingProxyType
from typing import cast, get_type_hints

import pytest

from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.netlist_pin_assignments import (
    NetlistPinNetAssignmentsByPin,
    NetlistPinNetIndex,
    netlist_pin_inventory_contains,
    netlist_pin_net_assignments,
    netlist_pin_net_index,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint]


def test_pin_net_index_api_uses_its_named_read_only_contract() -> None:
    assert get_type_hints(netlist_pin_net_index)["return"] == NetlistPinNetIndex


def test_index_casefolds_pins_and_preserves_all_exact_net_assignments() -> None:
    observed = NetlistContract(
        components={},
        nets={"z_NET": ("U1.1",), "A_NET": ("u1.1", "J1.1")},
    )

    index = netlist_pin_net_index(observed)
    assert index == {
        "u1.1": {"A_NET", "z_NET"},
        "j1.1": {"A_NET"},
    }
    assert isinstance(index["u1.1"], frozenset)
    with pytest.raises(TypeError):
        index["u2.1"] = frozenset({"OTHER_NET"})  # type: ignore[index]
    with pytest.raises(AttributeError):
        index["u1.1"].add("OTHER_NET")  # type: ignore[attr-defined]


def test_occurrence_index_preserves_duplicate_assignments_and_native_order() -> None:
    observed = NetlistContract(
        components={},
        nets={"z_NET": ("U1.1",), "A_NET": ("u1.1", "U1.1")},
    )

    assignments = netlist_pin_net_assignments(observed)
    assert get_type_hints(netlist_pin_net_assignments)["return"] == NetlistPinNetAssignmentsByPin
    assert isinstance(assignments, MappingProxyType)
    assert assignments == {"u1.1": ("z_NET", "A_NET", "A_NET")}
    with pytest.raises(TypeError):
        cast(MutableMapping[str, tuple[str, ...]], assignments)["u2.1"] = ("OTHER_NET",)


def test_inventory_lookup_distinguishes_missing_inventory_from_missing_pin() -> None:
    observed = NetlistContract(
        components={},
        nets={},
        component_pin_numbers={"U1": ("1", "2")},
    )

    assert netlist_pin_inventory_contains(observed, "u1.2") is True
    assert netlist_pin_inventory_contains(observed, "U1.3") is False
    assert netlist_pin_inventory_contains(observed, "U1") is False
    assert netlist_pin_inventory_contains(observed, "J1.1") is None
