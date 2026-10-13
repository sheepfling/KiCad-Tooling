"""Compare required fitted PCB references with exact native source evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import TypeVar

from .models import NetlistContract
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_required_fitted_reference_models import (
    PcbRequiredFittedReferenceMap,
    PcbRequiredFittedReferenceMismatch,
    PcbRequiredFittedReferenceViolation,
)

ValueT = TypeVar("ValueT")


def compare_required_fitted_references(
    requirements: PcbRequiredFittedReferenceMap,
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbRequiredFittedReferenceMismatch, ...]:
    """Return project-required references that are missing, DNP, or misidentified."""
    if snapshot.schema_version not in {"12", "13"}:
        raise ValueError("Required fitted PCB references need snapshot schema 12 or 13")

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
    for requirement in requirements.requirements:
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

    return tuple(sorted(mismatches, key=lambda item: item.reference.casefold()))


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
