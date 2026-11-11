"""Validate pair reference-via evidence against its enclosing lint source set."""

from __future__ import annotations

from collections.abc import Mapping

from .model_primitives import Digest, RepositoryPath
from .pcb_board_source_binding import pcb_board_source_matches
from .pcb_differential_pair_reference_via_models import (
    PcbDifferentialPairReferenceViaReport,
)
from .source_inventory_fingerprint import source_inventory_sha256


def validate_pcb_reference_via_source(
    report: PcbDifferentialPairReferenceViaReport | None,
    *,
    source_hashes: Mapping[RepositoryPath, Digest],
    netlist_sha256: Digest | None,
) -> None:
    """Reject measured heuristic evidence from another netlist or source inventory."""
    if report is None or report.status not in {"COMPLETE", "INCOMPLETE"}:
        return
    if report.netlist_sha256 != netlist_sha256:
        raise ValueError("Pair reference-via evidence must use this report's native netlist")
    if report.source_inventory_sha256 != source_inventory_sha256(source_hashes):
        raise ValueError(
            "Pair reference-via evidence must use this report's current source inventory"
        )
    if not pcb_board_source_matches(report.board_path, report.board_sha256, source_hashes):
        raise ValueError("Pair reference-via evidence must use this report's current PCB source")
