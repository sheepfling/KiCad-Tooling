"""Compare schematic and native PCB component value fields."""

from __future__ import annotations

from .models import NetlistContract
from .pcb_component_inventory_models import PcbComponentValueMismatch
from .pcb_connectivity_observations import PcbFootprintPlacementObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot


def compare_schematic_pcb_values(
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbComponentValueMismatch, ...]:
    """Review exact value-text differences for components fitted in both CAD sources."""
    if snapshot.schema_version not in {"13", "14", "15"}:
        raise ValueError(
            "PCB component value comparison requires native snapshot schema 13 or later"
        )

    board_footprints: dict[str, PcbFootprintPlacementObservation] = {}
    for footprint in snapshot.footprints:
        key = footprint.reference.casefold()
        if key in board_footprints:
            raise ValueError("Native PCB has duplicate case-insensitive footprint references")
        if footprint.value is None:
            raise ValueError("Native PCB snapshot schema 13 or later lacks a footprint value field")
        board_footprints[key] = footprint

    schematic_references: set[str] = set()
    dnp_references = {reference.casefold() for reference in netlist.dnp_components}
    mismatches: list[PcbComponentValueMismatch] = []
    for reference, component in netlist.components.items():
        key = reference.casefold()
        if key in schematic_references:
            raise ValueError("Native netlist has duplicate case-insensitive component references")
        schematic_references.add(key)
        if not component.footprint.strip() or key in dnp_references:
            continue
        placed = board_footprints.get(key)
        if placed is None or placed.dnp:
            continue
        schematic_value = component.value.strip()
        board_value = (placed.value or "").strip()
        if schematic_value != board_value:
            mismatches.append(
                PcbComponentValueMismatch(
                    reference=reference,
                    schematic_value=schematic_value,
                    board_value=board_value,
                )
            )
    return tuple(sorted(mismatches, key=lambda item: item.reference.casefold()))
