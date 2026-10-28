"""Tests for grouping native PCB pads by their copper connectivity evidence."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.pcb_connectivity_observations import PcbPadConnectivityObservation
from kicad_tooling.hwrepo.pcb_pad_union_find import PcbPadUnionFind

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def pad(reference: str, connected_pads: tuple[str, ...]) -> PcbPadConnectivityObservation:
    return PcbPadConnectivityObservation(
        pad=reference,
        net="N1",
        footprint="Test:Footprint",
        dnp=False,
        connected_pads=connected_pads,
        connected_zones=(),
        connected_islands=(),
    )


def test_union_find_groups_transitive_pad_connections_case_insensitively() -> None:
    groups = PcbPadUnionFind(
        (
            pad("J1.1", ("J1.1", "U1.1")),
            pad("U1.1", ("U1.1", "R1.1")),
            pad("R1.1", ("R1.1",)),
            pad("C1.1", ("C1.1",)),
        )
    )

    assert groups.find("j1.1") == groups.find("R1.1")
    assert groups.find("U1.1") != groups.find("C1.1")
    assert groups.find("missing.1") == ""


def test_connected_group_identity_is_stable_when_native_pad_order_changes() -> None:
    pads = (
        pad("J1.1", ("J1.1", "U1.1")),
        pad("U1.1", ("U1.1", "R1.1")),
        pad("R1.1", ("R1.1",)),
        pad("C1.1", ("C1.1",)),
    )

    forward = PcbPadUnionFind(pads)
    reversed_records = PcbPadUnionFind(tuple(reversed(pads)))

    assert forward.find("J1.1") == reversed_records.find("J1.1") == "j1.1"
    assert forward.find("R1.1") == reversed_records.find("R1.1") == "j1.1"
    assert forward.find("C1.1") == reversed_records.find("C1.1") == "c1.1"
