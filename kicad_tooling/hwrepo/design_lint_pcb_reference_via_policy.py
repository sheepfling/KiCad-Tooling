"""Source and project-map policy for pair reference-via heuristic evidence."""

from __future__ import annotations

from typing import Literal

from .design_lint_pcb_coverage_common import map_sha256
from .pcb_board_source_binding import pcb_board_source_matches
from .pcb_differential_pair_reference_via_models import (
    PcbDifferentialPairReferenceViaReport,
)
from .pcb_signal_path_rule_models import PcbSignalPathRuleMap
from .source_inventory_fingerprint import source_inventory_sha256
from .source_state_models import SourceHashInventory

ReferenceViaMode = Literal["review", "block", "off"]


def configured_reference_via_bundle_ids(
    requirements: PcbSignalPathRuleMap | None,
) -> tuple[str, ...]:
    """Return explicitly configured bundle IDs in stable order."""
    if requirements is None:
        return ()
    return tuple(
        item.id
        for item in sorted(requirements.bundles, key=lambda item: item.id.casefold())
        if item.reference_net is not None and item.max_reference_via_distance_nm is not None
    )


def normalize_reference_via_stitching_policy(
    coverage: PcbDifferentialPairReferenceViaReport | None,
    *,
    requirements: PcbSignalPathRuleMap | None,
    mode: ReferenceViaMode,
    source_hashes: SourceHashInventory,
) -> PcbDifferentialPairReferenceViaReport:
    """Reject absent, stale, or wrongly mapped evidence for configured pair review."""
    bundle_ids = configured_reference_via_bundle_ids(requirements)
    if not bundle_ids or requirements is None:
        return PcbDifferentialPairReferenceViaReport()
    requirement_hash = map_sha256(requirements)
    if mode == "off":
        return PcbDifferentialPairReferenceViaReport(
            status="DISABLED",
            mode=mode,
            map_sha256=requirement_hash,
            configured_bundle_ids=bundle_ids,
        )
    issue: str | None = None
    if coverage is None or coverage.status in {"NOT_REQUESTED", "DISABLED"}:
        issue = "Source-bound native pair-route and via evidence was not supplied"
    elif coverage.map_sha256 != requirement_hash:
        issue = "Reference-via evidence does not bind the current project-authored pair map"
    elif coverage.status in {"COMPLETE", "INCOMPLETE"} and (
        coverage.source_inventory_sha256 != source_inventory_sha256(source_hashes)
        or not pcb_board_source_matches(
            coverage.board_path,
            coverage.board_sha256,
            source_hashes,
        )
    ):
        issue = "Reference-via evidence differs from the current project source inventory"
    elif coverage.status == "BLOCKED":
        return coverage.model_copy(update={"mode": mode})
    else:
        return coverage.model_copy(update={"mode": mode})
    return PcbDifferentialPairReferenceViaReport(
        status="BLOCKED",
        mode=mode,
        map_sha256=requirement_hash,
        configured_bundle_ids=bundle_ids,
        issue=issue,
    )
