"""Compare schematic and native PCB component value fields."""

from __future__ import annotations

from .models import NetlistContract
from .pcb_component_inventory_models import PcbComponentValueMismatch
from .pcb_component_population import PcbVariantPopulationSource
from .pcb_connectivity_observations import PcbFootprintPlacementObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot


def compare_schematic_pcb_values(
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
    variants: tuple[PcbVariantPopulationSource, ...] = (),
) -> tuple[PcbComponentValueMismatch, ...]:
    """Compare exact base and named-variant values for components fitted in both CAD sources."""
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
    variant_names = [item.variant.casefold() for item in variants]
    if len(variant_names) != len(set(variant_names)):
        raise ValueError("Named PCB value variants must be unique case-insensitively")
    for source in variants:
        if not source.variant.strip():
            raise ValueError("Named PCB value variant cannot be blank")
        if source.board_values is None:
            raise ValueError(f"Variant {source.variant!r} native PCB value export is unavailable")
        board_keys = [reference.casefold() for reference in source.board_references]
        fitted_keys = [reference.casefold() for reference in source.fitted_board_references]
        if len(board_keys) != len(set(board_keys)) or len(fitted_keys) != len(set(fitted_keys)):
            raise ValueError(f"Variant {source.variant!r} board inventory has duplicate references")
        board_references = set(board_keys)
        fitted_references = set(fitted_keys)
        if not fitted_references <= board_references:
            raise ValueError(
                f"Variant {source.variant!r} fitted board inventory contains a missing reference"
            )
        variant_components: dict[str, tuple[str, str]] = {}
        for reference, component in source.netlist.components.items():
            key = reference.casefold()
            if key in variant_components:
                raise ValueError(
                    f"Variant {source.variant!r} netlist has duplicate case-insensitive references"
                )
            variant_components[key] = (reference, component.footprint.strip())
        schematic_dnp = {reference.casefold() for reference in source.netlist.dnp_components}
        board_values: dict[str, tuple[str, str]] = {}
        for reference, value in source.board_values.items():
            key = reference.casefold()
            if key in board_values:
                raise ValueError(
                    f"Variant {source.variant!r} board has duplicate case-insensitive values"
                )
            board_values[key] = (reference, value.strip())
        if set(board_values) != board_references:
            raise ValueError(
                f"Variant {source.variant!r} PCB value inventory does not match its position inventory"
            )
        for key in sorted(board_references & fitted_references & variant_components.keys()):
            reference, assigned_footprint = variant_components[key]
            if not assigned_footprint or key in schematic_dnp:
                continue
            board_value = board_values.get(key)
            if board_value is None:
                raise ValueError(
                    f"Variant {source.variant!r} PCB value is missing for fitted {reference}"
                )
            schematic_value = source.netlist.components[reference].value.strip()
            if schematic_value != board_value[1]:
                mismatches.append(
                    PcbComponentValueMismatch(
                        reference=reference,
                        schematic_value=schematic_value,
                        board_value=board_value[1],
                        variant=source.variant,
                    )
                )
    return tuple(
        sorted(
            mismatches,
            key=lambda item: (
                item.variant.casefold() if item.variant is not None else "",
                item.reference.casefold(),
            ),
        )
    )
