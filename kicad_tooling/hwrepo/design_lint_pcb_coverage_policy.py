"""Normalize configured PCB coverage states and source-map bindings."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from .models import (
    DesignLintPolicy,
    PcbKeepoutCoverageReport,
    PcbProtectionPathCoverageReport,
    PcbProtectionPathMap,
)
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageReport,
    PcbDifferentialPairRuleMap,
    PcbSignalPathRuleCoverageReport,
)
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport, PcbReferencePlaneMap
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
    PcbSwitchingLoopMap,
)


@dataclass(frozen=True)
class PcbInputCoveragePolicyState:
    """Coverage reports for source-bound signal, keepout, and antenna maps."""

    signal_path: PcbSignalPathRuleCoverageReport
    keepout: PcbKeepoutCoverageReport
    rf_antenna: PcbRfModuleAntennaCoverageReport


@dataclass(frozen=True)
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


def normalize_pcb_input_coverage_policy(
    policy: DesignLintPolicy,
    *,
    pcb_signal_path_coverage: PcbSignalPathRuleCoverageReport | None,
    pcb_keepout_coverage: PcbKeepoutCoverageReport | None,
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport | None,
) -> PcbInputCoveragePolicyState:
    """Apply modes and map identity to signal-path, keepout, and antenna coverage."""
    signal_path_map = policy.pcb_signal_path_rule_map

    signal_path_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.signal_path_rule_coverage"),
        None,
    )

    signal_path_mode: Literal["review", "block", "off"] = (
        "review" if signal_path_override is None else signal_path_override.mode
    )

    signal_path_map_sha256 = (
        hashlib.sha256(signal_path_map.model_dump_json().encode("utf-8")).hexdigest()
        if signal_path_map is not None
        else None
    )

    if signal_path_map is None:
        pcb_signal_path_coverage = pcb_signal_path_coverage or PcbSignalPathRuleCoverageReport()
    elif signal_path_mode == "off":
        pcb_signal_path_coverage = PcbSignalPathRuleCoverageReport(
            status="DISABLED", mode="off", map_sha256=signal_path_map_sha256
        )
    elif pcb_signal_path_coverage is None:
        pcb_signal_path_coverage = PcbSignalPathRuleCoverageReport(
            status="BLOCKED",
            mode=signal_path_mode,
            map_sha256=signal_path_map_sha256,
            issue="Source-bound native PCB and DRC evidence was not supplied for the signal-path map",
        )
    elif (
        pcb_signal_path_coverage.map_sha256 != signal_path_map_sha256
        or pcb_signal_path_coverage.status == "NOT_REQUESTED"
    ):
        pcb_signal_path_coverage = PcbSignalPathRuleCoverageReport(
            status="BLOCKED",
            mode=signal_path_mode,
            map_sha256=signal_path_map_sha256,
            issue="Signal-path coverage does not bind the current project-authored map",
        )
    else:
        pcb_signal_path_coverage = pcb_signal_path_coverage.model_copy(
            update={"mode": signal_path_mode}
        )

    keepout_map = policy.pcb_keepout_map

    keepout_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.keepout_intent_coverage"),
        None,
    )

    keepout_mode: Literal["review", "block", "off"] = (
        "review" if keepout_override is None else keepout_override.mode
    )

    keepout_map_sha256 = (
        hashlib.sha256(keepout_map.model_dump_json().encode("utf-8")).hexdigest()
        if keepout_map is not None
        else None
    )

    if keepout_map is None:
        pcb_keepout_coverage = pcb_keepout_coverage or PcbKeepoutCoverageReport()
    elif keepout_mode == "off":
        pcb_keepout_coverage = PcbKeepoutCoverageReport(
            status="DISABLED", mode="off", map_sha256=keepout_map_sha256
        )
    elif pcb_keepout_coverage is None:
        pcb_keepout_coverage = PcbKeepoutCoverageReport(
            status="BLOCKED",
            mode=keepout_mode,
            map_sha256=keepout_map_sha256,
            issue="Source-bound native PCB geometry was not supplied for the keepout map",
        )
    elif pcb_keepout_coverage.map_sha256 != keepout_map_sha256 or pcb_keepout_coverage.status in {
        "NOT_REQUESTED",
        "DISABLED",
    }:
        pcb_keepout_coverage = PcbKeepoutCoverageReport(
            status="BLOCKED",
            mode=keepout_mode,
            map_sha256=keepout_map_sha256,
            issue="Keepout coverage does not bind the current project-authored map",
        )
    else:
        pcb_keepout_coverage = pcb_keepout_coverage.model_copy(update={"mode": keepout_mode})

    rf_antenna_map = policy.pcb_rf_module_antenna_map

    rf_antenna_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.rf_module_antenna_keepout_coverage"),
        None,
    )

    rf_antenna_mode: Literal["review", "block", "off"] = (
        "review" if rf_antenna_override is None else rf_antenna_override.mode
    )

    rf_antenna_map_sha256 = (
        hashlib.sha256(rf_antenna_map.model_dump_json().encode("utf-8")).hexdigest()
        if rf_antenna_map is not None
        else None
    )

    if rf_antenna_map is None:
        pcb_rf_module_antenna_coverage = (
            pcb_rf_module_antenna_coverage or PcbRfModuleAntennaCoverageReport()
        )
    elif rf_antenna_mode == "off":
        pcb_rf_module_antenna_coverage = PcbRfModuleAntennaCoverageReport(
            status="DISABLED", mode="off", map_sha256=rf_antenna_map_sha256
        )
    elif pcb_rf_module_antenna_coverage is None:
        pcb_rf_module_antenna_coverage = PcbRfModuleAntennaCoverageReport(
            status="BLOCKED",
            mode=rf_antenna_mode,
            map_sha256=rf_antenna_map_sha256,
            issue="Source-bound native PCB geometry was not supplied for the RF module map",
        )
    elif (
        pcb_rf_module_antenna_coverage.map_sha256 != rf_antenna_map_sha256
        or pcb_rf_module_antenna_coverage.status in {"NOT_REQUESTED", "DISABLED"}
    ):
        pcb_rf_module_antenna_coverage = PcbRfModuleAntennaCoverageReport(
            status="BLOCKED",
            mode=rf_antenna_mode,
            map_sha256=rf_antenna_map_sha256,
            issue="RF module coverage does not bind the current project-authored map",
        )
    else:
        pcb_rf_module_antenna_coverage = pcb_rf_module_antenna_coverage.model_copy(
            update={"mode": rf_antenna_mode}
        )
    return PcbInputCoveragePolicyState(
        signal_path=pcb_signal_path_coverage,
        keepout=pcb_keepout_coverage,
        rf_antenna=pcb_rf_module_antenna_coverage,
    )


def normalize_pcb_mapped_coverage_policy(
    policy: DesignLintPolicy,
    *,
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

    if pair_map is not None and pair_mode == "off":
        pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
            status="DISABLED",
            mode="off",
            map_sha256=pair_map_sha256,
        )

    loop_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.switching_loop_geometry"),
        None,
    )

    loop_mode: Literal["review", "block", "off"] = (
        "review" if loop_override is None else loop_override.mode
    )

    loop_map = policy.pcb_switching_loop_map

    if loop_map is not None and loop_mode == "off":
        pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
            status="DISABLED",
            mode="off",
            map_sha256=hashlib.sha256(loop_map.model_dump_json().encode("utf-8")).hexdigest(),
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

    if pcb_reference_plane_coverage is None:
        if reference_plane_map is None:
            pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport()
        elif reference_plane_mode == "off":
            pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport(
                status="DISABLED",
                mode="off",
                map_sha256=reference_plane_map_sha256,
            )
        else:
            pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport(
                status="BLOCKED",
                mode=reference_plane_mode,
                map_sha256=reference_plane_map_sha256,
                issue="Source-bound native PCB geometry was not supplied for the reference-plane map",
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

    if pcb_protection_path_coverage is None:
        if protection_path_map is None:
            pcb_protection_path_coverage = PcbProtectionPathCoverageReport()
        elif protection_path_mode == "off":
            pcb_protection_path_coverage = PcbProtectionPathCoverageReport(
                status="DISABLED",
                mode=protection_path_mode,
                map_sha256=protection_path_map_sha256,
            )
        else:
            pcb_protection_path_coverage = PcbProtectionPathCoverageReport(
                status="BLOCKED",
                mode=protection_path_mode,
                map_sha256=protection_path_map_sha256,
                issue="Source-bound native PCB geometry was not supplied for the protection path map",
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
