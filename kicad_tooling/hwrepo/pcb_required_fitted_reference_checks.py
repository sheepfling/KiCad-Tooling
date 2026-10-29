"""Compare required fitted PCB references with exact native source evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import TypeVar

from .models import ComponentContract, NetlistContract
from .pcb_component_population import PcbVariantPopulationSource
from .pcb_connectivity_observations import PcbFootprintPlacementObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_required_fitted_reference_models import (
    PcbRequiredFittedReference,
    PcbRequiredFittedReferenceMap,
    PcbRequiredFittedReferenceMismatch,
    PcbRequiredFittedReferenceVariant,
    PcbRequiredFittedReferenceViolation,
)

ValueT = TypeVar("ValueT")


def compare_required_fitted_references(
    requirements: PcbRequiredFittedReferenceMap,
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
    variants: tuple[PcbVariantPopulationSource, ...] = (),
) -> tuple[PcbRequiredFittedReferenceMismatch, ...]:
    """Compare base and named-variant requirements with source-bound native evidence."""
    if snapshot.schema_version not in {"12", "13", "14"}:
        raise ValueError("Required fitted PCB references need snapshot schema 12, 13, or 14")

    schematic = _unique_casefolded(
        netlist.components,
        error="Native netlist has duplicate case-insensitive component references",
    )
    board = _unique_casefolded(
        {item.reference: item for item in snapshot.footprints},
        error="Native PCB has duplicate case-insensitive footprint references",
    )
    symbols: dict[str, str] = {}
    ambiguous_symbols: set[str] = set()
    for reference, symbol in netlist.component_symbols.items():
        key = reference.casefold()
        if key in symbols:
            ambiguous_symbols.add(key)
        symbols[key] = symbol

    schematic_dnp = {reference.casefold() for reference in netlist.dnp_components}
    mismatches: list[PcbRequiredFittedReferenceMismatch] = []
    mismatches.extend(
        _compare_requirements(
            requirements.requirements,
            schematic,
            board,
            symbols,
            ambiguous_symbols,
            schematic_dnp,
        )
    )
    variant_sources = _unique_variants(variants)
    for variant_requirement in requirements.variants:
        source = variant_sources.get(variant_requirement.variant.casefold())
        if source is None:
            raise ValueError(
                f"Required fitted-reference variant {variant_requirement.variant!r} "
                "has no complete source-bound native export"
            )
        variant_schematic = _unique_casefolded(
            source.netlist.components,
            error=f"Variant {source.variant!r} has duplicate case-insensitive schematic references",
        )
        variant_symbols: dict[str, str] = {}
        variant_ambiguous_symbols: set[str] = set()
        for reference, symbol in source.netlist.component_symbols.items():
            key = reference.casefold()
            if key in variant_symbols:
                variant_ambiguous_symbols.add(key)
            variant_symbols[key] = symbol
        variant_dnp = {reference.casefold() for reference in source.netlist.dnp_components}
        variant_board = _unique_reference_set(
            source.board_references, source.variant, "board"
        )
        variant_fitted = _unique_reference_set(
            source.fitted_board_references, source.variant, "fitted board"
        )
        if not variant_fitted <= variant_board:
            raise ValueError(
                f"Variant {source.variant!r} fitted board inventory contains a missing reference"
            )
        mismatches.extend(
            _compare_variant_requirements(
                variant_requirement,
                variant_schematic,
                variant_symbols,
                variant_ambiguous_symbols,
                variant_dnp,
                variant_board,
                variant_fitted,
                board,
            )
        )

    return tuple(
        sorted(
            mismatches,
            key=lambda item: (
                "" if item.variant is None else item.variant.casefold(),
                item.reference.casefold(),
            ),
        )
    )


def _compare_requirements(
    requirements: tuple[PcbRequiredFittedReference, ...],
    schematic: Mapping[str, ComponentContract],
    board: Mapping[str, PcbFootprintPlacementObservation],
    symbols: Mapping[str, str],
    ambiguous_symbols: set[str],
    schematic_dnp: set[str],
) -> list[PcbRequiredFittedReferenceMismatch]:
    mismatches: list[PcbRequiredFittedReferenceMismatch] = []
    for requirement in requirements:
        key = requirement.reference.casefold()
        component = schematic.get(key)
        footprint = board.get(key)
        observed_symbol = symbols.get(key)
        violations: list[PcbRequiredFittedReferenceViolation] = []

        if component is None:
            violations.append("schematic_reference_missing")
        else:
            if key in schematic_dnp:
                violations.append("schematic_component_dnp")
            assigned_footprint = component.footprint.strip()
            if not assigned_footprint:
                violations.append("schematic_footprint_unassigned")
            elif assigned_footprint != requirement.footprint:
                violations.append("schematic_footprint_mismatch")
            if requirement.symbol is not None:
                if observed_symbol is None or key in ambiguous_symbols:
                    violations.append("schematic_symbol_missing")
                elif observed_symbol != requirement.symbol:
                    violations.append("schematic_symbol_mismatch")
            if requirement.part_id is not None and component.part_id != requirement.part_id:
                violations.append("schematic_part_id_mismatch")

        if footprint is None:
            violations.append("board_footprint_missing")
        else:
            if footprint.dnp:
                violations.append("board_footprint_dnp")
            if footprint.footprint.strip() != requirement.footprint:
                violations.append("board_footprint_mismatch")

        if violations:
            mismatches.append(
                PcbRequiredFittedReferenceMismatch(
                    reference=requirement.reference,
                    basis=requirement.basis,
                    expected_footprint=requirement.footprint,
                    expected_symbol=requirement.symbol,
                    observed_symbol=observed_symbol,
                    expected_part_id=requirement.part_id,
                    observed_part_id=None if component is None else component.part_id,
                    schematic_footprint=None if component is None else component.footprint,
                    board_footprint=None if footprint is None else footprint.footprint,
                    schematic_dnp=None if component is None else key in schematic_dnp,
                    board_dnp=None if footprint is None else footprint.dnp,
                    violations=tuple(violations),
                )
            )

    return mismatches


def _compare_variant_requirements(
    variant_requirements: PcbRequiredFittedReferenceVariant,
    schematic: Mapping[str, ComponentContract],
    symbols: Mapping[str, str],
    ambiguous_symbols: set[str],
    schematic_dnp: set[str],
    board_references: set[str],
    fitted_board_references: set[str],
    base_board: Mapping[str, PcbFootprintPlacementObservation],
) -> list[PcbRequiredFittedReferenceMismatch]:
    mismatches: list[PcbRequiredFittedReferenceMismatch] = []
    for requirement in variant_requirements.requirements:
        key = requirement.reference.casefold()
        component = schematic.get(key)
        base_footprint = base_board.get(key)
        variant_symbol = symbols.get(key)
        violations: list[PcbRequiredFittedReferenceViolation] = []
        if component is None:
            violations.append("schematic_reference_missing")
        else:
            if key in schematic_dnp:
                violations.append("schematic_component_dnp")
            footprint = component.footprint.strip()
            if not footprint:
                violations.append("schematic_footprint_unassigned")
            elif footprint != requirement.footprint:
                violations.append("schematic_footprint_mismatch")
            if requirement.symbol is not None:
                if variant_symbol is None or key in ambiguous_symbols:
                    violations.append("schematic_symbol_missing")
                elif variant_symbol != requirement.symbol:
                    violations.append("schematic_symbol_mismatch")
            if requirement.part_id is not None and component.part_id != requirement.part_id:
                violations.append("schematic_part_id_mismatch")
        if base_footprint is None or key not in board_references:
            violations.append("board_footprint_missing")
            board_footprint = None if base_footprint is None else base_footprint.footprint
        else:
            board_footprint = base_footprint.footprint
            if board_footprint.strip() != requirement.footprint:
                violations.append("board_footprint_mismatch")
            if key not in fitted_board_references:
                violations.append("board_footprint_dnp")
        if violations:
            mismatches.append(
                PcbRequiredFittedReferenceMismatch(
                    reference=requirement.reference,
                    variant=variant_requirements.variant,
                    basis=requirement.basis,
                    expected_footprint=requirement.footprint,
                    expected_symbol=requirement.symbol,
                    observed_symbol=(
                        None if key in ambiguous_symbols else variant_symbol
                    ),
                    expected_part_id=requirement.part_id,
                    observed_part_id=None if component is None else component.part_id,
                    schematic_footprint=None if component is None else component.footprint,
                    board_footprint=board_footprint,
                    schematic_dnp=None if component is None else key in schematic_dnp,
                    board_dnp=(None if key not in board_references else key not in fitted_board_references),
                    violations=tuple(violations),
                )
            )
    return mismatches


def _unique_variants(
    variants: tuple[PcbVariantPopulationSource, ...],
) -> dict[str, PcbVariantPopulationSource]:
    indexed: dict[str, PcbVariantPopulationSource] = {}
    for source in variants:
        key = source.variant.casefold()
        if key in indexed:
            raise ValueError("Named PCB population variants must be unique case-insensitively")
        indexed[key] = source
    return indexed


def _unique_reference_set(references: tuple[str, ...], variant: str, source: str) -> set[str]:
    normalized = {reference.casefold() for reference in references}
    if any(not reference.strip() for reference in references) or len(normalized) != len(references):
        raise ValueError(
            f"Variant {variant!r} has duplicate case-insensitive {source} references"
        )
    return normalized


def required_fitted_reference_map_sha256(requirements: PcbRequiredFittedReferenceMap) -> str:
    """Hash a map independent of requirement ordering for stable exact-ignore evidence."""
    payload = {
        "schema_version": requirements.schema_version,
        "basis": requirements.basis,
        "requirements": [
            item.model_dump(mode="json")
            for item in sorted(
                requirements.requirements, key=lambda item: item.reference.casefold()
            )
        ],
    }
    if requirements.variants:
        payload["variants"] = [
            {
                "variant": variant.variant,
                "requirements": [
                    item.model_dump(mode="json")
                    for item in sorted(
                        variant.requirements,
                        key=lambda item: item.reference.casefold(),
                    )
                ],
            }
            for variant in sorted(
                requirements.variants, key=lambda item: item.variant.casefold()
            )
        ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unique_casefolded(items: Mapping[str, ValueT], *, error: str) -> dict[str, ValueT]:
    """Index native references without silently choosing a case-insensitive duplicate."""
    indexed: dict[str, ValueT] = {}
    for reference, item in items.items():
        key = reference.casefold()
        if key in indexed:
            raise ValueError(error)
        indexed[key] = item
    return indexed
