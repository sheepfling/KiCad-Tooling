"""Compare schematic and PCB footprint population flags."""

from __future__ import annotations

from .models import NetlistContract
from .pcb_component_inventory_models import PcbPopulationMismatch
from .pcb_connectivity_observations import PcbFootprintPlacementObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot


def compare_schematic_pcb_population(
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbPopulationMismatch, ...]:
    """Review DNP differences for footprint-assigned components present on both sources."""
    if snapshot.schema_version != "12":
        raise ValueError("PCB population comparison requires native footprint snapshot schema 12")

    schematic_components: dict[str, tuple[str, str]] = {}
    for reference, component in netlist.components.items():
        key = reference.casefold()
        if key in schematic_components:
            raise ValueError("Native netlist has duplicate case-insensitive component references")
        schematic_components[key] = (reference, component.footprint.strip())

    board_footprints: dict[str, PcbFootprintPlacementObservation] = {}
    for footprint in snapshot.footprints:
        key = footprint.reference.casefold()
        if key in board_footprints:
            raise ValueError("Native PCB has duplicate case-insensitive footprint references")
        board_footprints[key] = footprint

    schematic_dnp = {reference.casefold() for reference in netlist.dnp_components}
    mismatches: list[PcbPopulationMismatch] = []
    for key, (reference, assigned_footprint) in schematic_components.items():
        if not assigned_footprint:
            continue
        placed = board_footprints.get(key)
        if placed is None:
            continue
        schematic_is_dnp = key in schematic_dnp
        if schematic_is_dnp != placed.dnp:
            mismatches.append(
                PcbPopulationMismatch(
                    reference=reference,
                    schematic_dnp=schematic_is_dnp,
                    board_dnp=placed.dnp,
                )
            )
    return tuple(sorted(mismatches, key=lambda item: item.reference.casefold()))
