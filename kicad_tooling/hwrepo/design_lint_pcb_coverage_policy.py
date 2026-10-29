"""Normalize mapped PCB coverage states and source identities."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .design_lint_policy_models import DesignLintPolicy
from .pcb_board_source_binding import pcb_board_source_matches
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageReport,
    PcbDifferentialPairRuleMap,
)
from .pcb_drc_source_evidence import drc_coverage_matches_sources
from .pcb_protection_path_models import PcbProtectionPathCoverageReport, PcbProtectionPathMap
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport, PcbReferencePlaneMap
from .pcb_switching_loop_models import PcbSwitchingLoopCoverageReport, PcbSwitchingLoopMap


@dataclass(frozen=True, slots=True)
class PcbMappedCoveragePolicyState:
    """Coverage reports and selected modes for mapped PCB checks."""

    differential_pair: PcbDifferentialPairRuleCoverageReport | None
    switching_loop: PcbSwitchingLoopCoverageReport | None
    reference_plane: PcbReferencePlaneCoverageReport
    protection_path: PcbProtectionPathCoverageReport
    differential_pair_map: PcbDifferentialPairRuleMap | None
    differential_pair_mode: Literal["review", "block", "off"]
    differential_pair_map_sha256: str | None
    switching_loop_map: PcbSwitchingLoopMap | None
    switching_loop_mode: Literal["review", "block", "off"]


def normalize_pcb_mapped_coverage_policy(
    policy: DesignLintPolicy,
    *,
    source_hashes: Mapping[str, str],
    pcb_differential_pair_coverage: PcbDifferentialPairRuleCoverageReport | None,
    pcb_switching_loop_coverage: PcbSwitchingLoopCoverageReport | None,
    pcb_reference_plane_coverage: PcbReferencePlaneCoverageReport | None,
    pcb_protection_path_coverage: PcbProtectionPathCoverageReport | None,
) -> PcbMappedCoveragePolicyState:
    """Apply modes and map identity to the remaining PCB coverage reports."""
    pair_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.differential_pair_rule_coverage"),
        None,
    )

    pair_mode: Literal["review", "block", "off"] = (
        "review" if pair_override is None else pair_override.mode
    )

    pair_map = policy.pcb_differential_pair_rule_map

    pair_map_sha256 = (
        hashlib.sha256(pair_map.model_dump_json().encode("utf-8")).hexdigest()
        if pair_map is not None
        else None
    )

    if pair_mode == "off":
        pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
            status="DISABLED",
            mode="off",
            map_sha256=pair_map_sha256,
        )
    elif (
        pair_map is None
        and pcb_differential_pair_coverage is not None
        and pcb_differential_pair_coverage.status in {"COMPLETE", "INCOMPLETE"}
    ):
        pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
            status="BLOCKED",
            issue="Differential-pair coverage has no current project-authored map",
        )
    elif pair_map is not None and pcb_differential_pair_coverage is None:
        pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
            status="BLOCKED",
            mode=pair_mode,
            map_sha256=pair_map_sha256,
            issue="Source-bound native DRC evidence was not supplied for the differential-pair map",
        )
    elif pair_map is not None and pcb_differential_pair_coverage is not None:
        if pcb_differential_pair_coverage.status in {"NOT_REQUESTED", "DISABLED"} or (
            pcb_differential_pair_coverage.status in {"COMPLETE", "INCOMPLETE"}
            and pcb_differential_pair_coverage.map_sha256 != pair_map_sha256
        ):
            pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
                status="BLOCKED",
                mode=pair_mode,
                map_sha256=pair_map_sha256,
                issue="Differential-pair coverage does not bind the current project-authored map",
            )
        elif pcb_differential_pair_coverage.status in {"COMPLETE", "INCOMPLETE"} and not (
            drc_coverage_matches_sources(pcb_differential_pair_coverage, source_hashes)
        ):
            pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
                status="BLOCKED",
                mode=pair_mode,
                map_sha256=pair_map_sha256,
                issue="Differential-pair coverage differs from the current native source inventory",
            )
        else:
            pcb_differential_pair_coverage = pcb_differential_pair_coverage.model_copy(
                update={"mode": pair_mode}
            )

    loop_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.switching_loop_geometry"),
        None,
    )

    loop_mode: Literal["review", "block", "off"] = (
        "review" if loop_override is None else loop_override.mode
    )

    loop_map = policy.pcb_switching_loop_map
    loop_map_sha256 = (
        hashlib.sha256(loop_map.model_dump_json().encode("utf-8")).hexdigest()
        if loop_map is not None
        else None
    )

    if loop_mode == "off":
        pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
            status="DISABLED",
            mode="off",
            map_sha256=loop_map_sha256,
        )
    elif (
        loop_map is None
        and pcb_switching_loop_coverage is not None
        and (pcb_switching_loop_coverage.status in {"COMPLETE", "INCOMPLETE"})
    ):
        pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
            status="BLOCKED",
            issue="Switching-loop coverage has no current project-authored map",
        )
    elif loop_map is None:
        pcb_switching_loop_coverage = (
            pcb_switching_loop_coverage or PcbSwitchingLoopCoverageReport()
        )
    elif pcb_switching_loop_coverage is None:
        pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
            status="BLOCKED",
            mode=loop_mode,
            map_sha256=loop_map_sha256,
            issue="Source-bound native PCB geometry was not supplied for the switching-loop map",
        )
    elif pcb_switching_loop_coverage.status in {"NOT_REQUESTED", "DISABLED"} or (
        pcb_switching_loop_coverage.status in {"COMPLETE", "INCOMPLETE"}
        and pcb_switching_loop_coverage.map_sha256 != loop_map_sha256
    ):
        pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
            status="BLOCKED",
            mode=loop_mode,
            map_sha256=loop_map_sha256,
            issue="Switching-loop coverage does not bind the current project-authored map",
        )
    elif pcb_switching_loop_coverage.status in {"COMPLETE", "INCOMPLETE"} and not (
        pcb_board_source_matches(
            pcb_switching_loop_coverage.board_path,
            pcb_switching_loop_coverage.board_sha256,
            source_hashes,
        )
    ):
        pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
            status="BLOCKED",
            mode=loop_mode,
            map_sha256=loop_map_sha256,
            issue="Switching-loop coverage differs from the current PCB source",
        )
    else:
        pcb_switching_loop_coverage = pcb_switching_loop_coverage.model_copy(
            update={"mode": loop_mode}
        )

    reference_plane_map: PcbReferencePlaneMap | None = policy.pcb_reference_plane_map

    reference_plane_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.reference_plane_coverage"),
        None,
    )

    reference_plane_mode: Literal["review", "block", "off"] = (
        "review" if reference_plane_override is None else reference_plane_override.mode
    )

    reference_plane_map_sha256 = (
        hashlib.sha256(reference_plane_map.model_dump_json().encode("utf-8")).hexdigest()
        if reference_plane_map is not None
        else None
    )

    if reference_plane_mode == "off":
        pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport(
            status="DISABLED", mode="off", map_sha256=reference_plane_map_sha256
        )
    elif (
        reference_plane_map is None
        and pcb_reference_plane_coverage is not None
        and (pcb_reference_plane_coverage.status in {"COMPLETE", "INCOMPLETE"})
    ):
        pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport(
            status="BLOCKED", issue="Reference-plane coverage has no current project-authored map"
        )
    elif reference_plane_map is None:
        pcb_reference_plane_coverage = (
            pcb_reference_plane_coverage or PcbReferencePlaneCoverageReport()
        )
    elif pcb_reference_plane_coverage is None:
        pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport(
            status="BLOCKED",
            mode=reference_plane_mode,
            map_sha256=reference_plane_map_sha256,
            issue="Source-bound native PCB geometry was not supplied for the reference-plane map",
        )
    elif pcb_reference_plane_coverage.status in {"NOT_REQUESTED", "DISABLED"} or (
        pcb_reference_plane_coverage.status in {"COMPLETE", "INCOMPLETE"}
        and pcb_reference_plane_coverage.map_sha256 != reference_plane_map_sha256
    ):
        pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport(
            status="BLOCKED",
            mode=reference_plane_mode,
            map_sha256=reference_plane_map_sha256,
            issue="Reference-plane coverage does not bind the current project-authored map",
        )
    elif pcb_reference_plane_coverage.status in {"COMPLETE", "INCOMPLETE"} and not (
        pcb_board_source_matches(
            pcb_reference_plane_coverage.board_path,
            pcb_reference_plane_coverage.board_sha256,
            source_hashes,
        )
    ):
        pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport(
            status="BLOCKED",
            mode=reference_plane_mode,
            map_sha256=reference_plane_map_sha256,
            issue="Reference-plane coverage differs from the current PCB source",
        )
    else:
        pcb_reference_plane_coverage = pcb_reference_plane_coverage.model_copy(
            update={"mode": reference_plane_mode}
        )

    protection_path_map: PcbProtectionPathMap | None = policy.pcb_protection_path_map

    protection_path_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.protection_entry_path"),
        None,
    )

    protection_path_mode: Literal["review", "block", "off"] = (
        "review" if protection_path_override is None else protection_path_override.mode
    )

    protection_path_map_sha256 = (
        hashlib.sha256(protection_path_map.model_dump_json().encode("utf-8")).hexdigest()
        if protection_path_map is not None
        else None
    )

    if protection_path_mode == "off":
        pcb_protection_path_coverage = PcbProtectionPathCoverageReport(
            status="DISABLED", mode="off", map_sha256=protection_path_map_sha256
        )
    elif (
        protection_path_map is None
        and pcb_protection_path_coverage is not None
        and (pcb_protection_path_coverage.status in {"COMPLETE", "INCOMPLETE"})
    ):
        pcb_protection_path_coverage = PcbProtectionPathCoverageReport(
            status="BLOCKED", issue="Protection-path coverage has no current project-authored map"
        )
    elif protection_path_map is None:
        pcb_protection_path_coverage = (
            pcb_protection_path_coverage or PcbProtectionPathCoverageReport()
        )
    elif pcb_protection_path_coverage is None:
        pcb_protection_path_coverage = PcbProtectionPathCoverageReport(
            status="BLOCKED",
            mode=protection_path_mode,
            map_sha256=protection_path_map_sha256,
            issue="Source-bound native PCB geometry was not supplied for the protection path map",
        )
    elif pcb_protection_path_coverage.status in {"NOT_REQUESTED", "DISABLED"} or (
        pcb_protection_path_coverage.status in {"COMPLETE", "INCOMPLETE"}
        and pcb_protection_path_coverage.map_sha256 != protection_path_map_sha256
    ):
        pcb_protection_path_coverage = PcbProtectionPathCoverageReport(
            status="BLOCKED",
            mode=protection_path_mode,
            map_sha256=protection_path_map_sha256,
            issue="Protection-path coverage does not bind the current project-authored map",
        )
    elif pcb_protection_path_coverage.status in {"COMPLETE", "INCOMPLETE"} and not (
        pcb_board_source_matches(
            pcb_protection_path_coverage.board_path,
            pcb_protection_path_coverage.board_sha256,
            source_hashes,
        )
    ):
        pcb_protection_path_coverage = PcbProtectionPathCoverageReport(
            status="BLOCKED",
            mode=protection_path_mode,
            map_sha256=protection_path_map_sha256,
            issue="Protection-path coverage differs from the current PCB source",
        )
    else:
        pcb_protection_path_coverage = pcb_protection_path_coverage.model_copy(
            update={"mode": protection_path_mode}
        )
    return PcbMappedCoveragePolicyState(
        differential_pair=pcb_differential_pair_coverage,
        switching_loop=pcb_switching_loop_coverage,
        reference_plane=pcb_reference_plane_coverage,
        protection_path=pcb_protection_path_coverage,
        differential_pair_map=pair_map,
        differential_pair_mode=pair_mode,
        differential_pair_map_sha256=pair_map_sha256,
        switching_loop_map=loop_map,
        switching_loop_mode=loop_mode,
    )
