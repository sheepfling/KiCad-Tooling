"""Compare schematic and PCB footprint population flags."""

from __future__ import annotations

from dataclasses import dataclass

from .models import NetlistContract
from .pcb_component_inventory_models import PcbPopulationMismatch
from .pcb_connectivity_observations import PcbFootprintPlacementObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot


@dataclass(frozen=True, slots=True)
class PcbVariantPopulationSource:
    """Parsed source records from paired exports of one exact named variant."""

    variant: str
    netlist: NetlistContract
    board_references: tuple[str, ...]
    fitted_board_references: tuple[str, ...]


def compare_schematic_pcb_population(
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
    variants: tuple[PcbVariantPopulationSource, ...] = (),
) -> tuple[PcbPopulationMismatch, ...]:
    """Review base and same-name variant DNP states for comparable CAD records."""
    if snapshot.schema_version not in {"12", "13", "14"}:
        raise ValueError(
            "PCB population comparison requires native footprint snapshot schema 12, 13, or 14"
        )

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
    variant_keys = [source.variant.casefold() for source in variants]
    if len(variant_keys) != len(set(variant_keys)):
        raise ValueError("Named PCB population variants must be unique case-insensitively")
    for source in variants:
        mismatches.extend(compare_variant_population_source(source))
    return tuple(
        sorted(
            mismatches,
            key=lambda item: (
                item.variant.casefold() if item.variant is not None else "",
                item.reference.casefold(),
            ),
        )
    )


def compare_variant_population_source(
    source: PcbVariantPopulationSource,
) -> tuple[PcbPopulationMismatch, ...]:
    """Compare a same-name schematic netlist and native PCB population export."""
    if not source.variant.strip():
        raise ValueError("Named PCB population variant cannot be blank")
    schematic_components: dict[str, tuple[str, str]] = {}
    for reference, component in source.netlist.components.items():
        key = reference.casefold()
        if key in schematic_components:
            raise ValueError(
                f"Variant {source.variant!r} netlist has duplicate case-insensitive references"
            )
        schematic_components[key] = (reference, component.footprint.strip())

    board_references = _unique_reference_set(source.board_references, source.variant, "board")
    fitted_references = _unique_reference_set(
        source.fitted_board_references, source.variant, "fitted board"
    )
    if not fitted_references <= board_references:
        raise ValueError(
            f"Variant {source.variant!r} fitted board inventory contains a missing reference"
        )
    schematic_dnp = {reference.casefold() for reference in source.netlist.dnp_components}
    mismatches: list[PcbPopulationMismatch] = []
    for key in sorted(board_references & schematic_components.keys()):
        reference, assigned_footprint = schematic_components[key]
        if not assigned_footprint:
            continue
        schematic_is_dnp = key in schematic_dnp
        board_is_dnp = key not in fitted_references
        if schematic_is_dnp != board_is_dnp:
            mismatches.append(
                PcbPopulationMismatch(
                    reference=reference,
                    schematic_dnp=schematic_is_dnp,
                    board_dnp=board_is_dnp,
                    variant=source.variant,
                )
            )
    return tuple(mismatches)


def _unique_reference_set(references: tuple[str, ...], variant: str, source: str) -> set[str]:
    keys = [reference.casefold() for reference in references]
    if any(not reference.strip() for reference in references) or len(keys) != len(set(keys)):
        raise ValueError(
            f"Variant {variant!r} {source} inventory has blank or duplicate references"
        )
    return set(keys)
