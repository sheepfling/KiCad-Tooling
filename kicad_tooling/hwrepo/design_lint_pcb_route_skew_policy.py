"""Policy and source-binding checks for measured PCB route-skew evidence."""

from __future__ import annotations

from typing import Literal

from .design_lint_pcb_coverage_common import map_sha256
from .pcb_board_source_binding import pcb_board_source_matches
from .pcb_differential_pair_skew_models import PcbDifferentialPairRouteSkewReport
from .pcb_signal_path_rule_models import PcbSignalPathRuleMap
from .source_inventory_fingerprint import source_inventory_sha256
from .source_state_models import SourceHashInventory

RouteSkewMode = Literal["review", "block", "off"]


def normalize_pcb_route_skew_policy(
    coverage: PcbDifferentialPairRouteSkewReport | None,
    *,
    requirements: PcbSignalPathRuleMap | None,
    mode: RouteSkewMode,
    source_hashes: SourceHashInventory,
) -> PcbDifferentialPairRouteSkewReport:
    """Reject missing, stale, or wrongly mapped native route measurements."""
    requested = requirements is not None and any(
        item.max_skew is not None for item in requirements.bundles
    )
    requirement_hash = map_sha256(requirements) if requirements is not None else None
    if not requested:
        if coverage is not None and coverage.status in {"COMPLETE", "INCOMPLETE"}:
            return PcbDifferentialPairRouteSkewReport(
                status="BLOCKED",
                mode=mode,
                map_sha256=requirement_hash,
                issue="Route-skew evidence has no current project-authored bundle map",
            )
        return PcbDifferentialPairRouteSkewReport(map_sha256=requirement_hash)
    if mode == "off":
        return PcbDifferentialPairRouteSkewReport(
            status="DISABLED", mode=mode, map_sha256=requirement_hash
        )
    if coverage is None or coverage.status in {"NOT_REQUESTED", "DISABLED"}:
        issue = "Source-bound native PCB route measurements were not supplied for this pair map"
    elif coverage.map_sha256 != requirement_hash:
        issue = "Route-skew evidence does not bind the current project-authored pair map"
    elif coverage.status in {"COMPLETE", "INCOMPLETE"} and (
        coverage.source_inventory_sha256 != source_inventory_sha256(source_hashes)
        or not pcb_board_source_matches(
            coverage.board_path,
            coverage.board_sha256,
            source_hashes,
        )
    ):
        issue = "Route-skew evidence differs from the current project source inventory"
    elif coverage.status == "BLOCKED":
        return coverage.model_copy(update={"mode": mode})
    else:
        return coverage.model_copy(update={"mode": mode})
    return PcbDifferentialPairRouteSkewReport(
        status="BLOCKED",
        mode=mode,
        map_sha256=requirement_hash,
        issue=issue,
    )
