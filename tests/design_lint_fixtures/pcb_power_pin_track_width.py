"""Synthetic native netlist and width-map controls for power-pin scope review."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.native_report_parsing import read_netlist
from kicad_tooling.hwrepo.pcb_track_width_models import (
    PcbTrackWidthMap,
    PcbTrackWidthRequirement,
)

NETLIST_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/design_lint/switching-regulator-loop-map-native/netlist.xml"
)


def native_power_netlist():
    """Read the tooling-owned native export fixture with two power-bearing nets."""
    return read_netlist(NETLIST_FIXTURE)


def power_track_width_map(*nets: str) -> PcbTrackWidthMap:
    """Build authored map coverage controls without implying a rated width."""
    return PcbTrackWidthMap(
        basis="Synthetic width-map coverage control",
        requirements=tuple(
            PcbTrackWidthRequirement(
                id=f"width-scope-{index}",
                basis="Synthetic control only; not an ampacity requirement",
                net=net,
                minimum_width_um=250,
            )
            for index, net in enumerate(nets, start=1)
        ),
    )
