"""Deterministic PCB references absent from the source-bound schematic."""

from __future__ import annotations

from .models import NetlistContract
from .pcb_board_only_footprint_models import PcbBoardOnlyFootprint
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot


def board_only_pcb_footprints(
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbBoardOnlyFootprint, ...]:
    """Return native PCB footprint references with no case-insensitive netlist match."""
    if snapshot.schema_version not in {"12", "13", "14", "15"}:
        raise ValueError("Board-only PCB footprint review requires snapshot schema 12, 13, or 14")

    schematic_references = {reference.casefold() for reference in netlist.components}
    if len(schematic_references) != len(netlist.components):
        raise ValueError("Native netlist has duplicate case-insensitive component references")

    board_references: set[str] = set()
    board_only: list[PcbBoardOnlyFootprint] = []
    for footprint in snapshot.footprints:
        key = footprint.reference.casefold()
        if key in board_references:
            raise ValueError("Native PCB has duplicate case-insensitive footprint references")
        board_references.add(key)
        if key not in schematic_references:
            board_only.append(
                PcbBoardOnlyFootprint(
                    reference=footprint.reference,
                    footprint=footprint.footprint,
                )
            )

    return tuple(sorted(board_only, key=lambda item: item.reference.casefold()))
