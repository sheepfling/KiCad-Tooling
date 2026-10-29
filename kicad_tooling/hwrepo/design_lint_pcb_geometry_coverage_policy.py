"""Normalize source-bound PCB geometry coverage and project map policy."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .design_lint_policy_models import DesignLintPolicy
from .pcb_board_source_binding import pcb_board_source_matches
from .pcb_drc_models import PcbSignalPathRuleCoverageReport
from .pcb_drc_source_evidence import drc_coverage_matches_sources
from .pcb_keepout_models import PcbKeepoutCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport


@dataclass(frozen=True, slots=True)
class PcbInputCoveragePolicyState:
    """Coverage reports for source-bound signal, keepout, and antenna maps."""

    signal_path: PcbSignalPathRuleCoverageReport
    keepout: PcbKeepoutCoverageReport
    rf_antenna: PcbRfModuleAntennaCoverageReport
    touch_pad_clearance: PcbTouchPadClearanceCoverageReport


def normalize_pcb_input_coverage_policy(
    policy: DesignLintPolicy,
    *,
    source_hashes: Mapping[str, str],
    pcb_signal_path_coverage: PcbSignalPathRuleCoverageReport | None,
    pcb_keepout_coverage: PcbKeepoutCoverageReport | None,
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport | None,
    pcb_touch_pad_clearance_coverage: PcbTouchPadClearanceCoverageReport | None,
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

    if signal_path_mode == "off":
        pcb_signal_path_coverage = PcbSignalPathRuleCoverageReport(
            status="DISABLED", mode="off", map_sha256=signal_path_map_sha256
        )
    elif (
        signal_path_map is None
        and pcb_signal_path_coverage is not None
        and pcb_signal_path_coverage.status in {"COMPLETE", "INCOMPLETE"}
    ):
        pcb_signal_path_coverage = PcbSignalPathRuleCoverageReport(
            status="BLOCKED", issue="Signal-path coverage has no current project-authored map"
        )
    elif signal_path_map is None:
        pcb_signal_path_coverage = pcb_signal_path_coverage or PcbSignalPathRuleCoverageReport()
    elif pcb_signal_path_coverage is None:
        pcb_signal_path_coverage = PcbSignalPathRuleCoverageReport(
            status="BLOCKED",
            mode=signal_path_mode,
            map_sha256=signal_path_map_sha256,
            issue="Source-bound native PCB and DRC evidence was not supplied for the signal-path map",
        )
    elif pcb_signal_path_coverage.status in {"NOT_REQUESTED", "DISABLED"} or (
        pcb_signal_path_coverage.status in {"COMPLETE", "INCOMPLETE"}
        and pcb_signal_path_coverage.map_sha256 != signal_path_map_sha256
    ):
        pcb_signal_path_coverage = PcbSignalPathRuleCoverageReport(
            status="BLOCKED",
            mode=signal_path_mode,
            map_sha256=signal_path_map_sha256,
            issue="Signal-path coverage does not bind the current project-authored map",
        )
    elif pcb_signal_path_coverage.status in {"COMPLETE", "INCOMPLETE"} and not (
        drc_coverage_matches_sources(pcb_signal_path_coverage, source_hashes)
    ):
        pcb_signal_path_coverage = PcbSignalPathRuleCoverageReport(
            status="BLOCKED",
            mode=signal_path_mode,
            map_sha256=signal_path_map_sha256,
            issue="Signal-path coverage differs from the current native source inventory",
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

    if keepout_mode == "off":
        pcb_keepout_coverage = PcbKeepoutCoverageReport(
            status="DISABLED", mode="off", map_sha256=keepout_map_sha256
        )
    elif (
        keepout_map is None
        and pcb_keepout_coverage is not None
        and pcb_keepout_coverage.status in {"COMPLETE", "INCOMPLETE"}
    ):
        pcb_keepout_coverage = PcbKeepoutCoverageReport(
            status="BLOCKED", issue="Keepout coverage has no current project-authored map"
        )
    elif keepout_map is None:
        pcb_keepout_coverage = pcb_keepout_coverage or PcbKeepoutCoverageReport()
    elif pcb_keepout_coverage is None:
        pcb_keepout_coverage = PcbKeepoutCoverageReport(
            status="BLOCKED",
            mode=keepout_mode,
            map_sha256=keepout_map_sha256,
            issue="Source-bound native PCB geometry was not supplied for the keepout map",
        )
    elif pcb_keepout_coverage.status in {"NOT_REQUESTED", "DISABLED"} or (
        pcb_keepout_coverage.status in {"COMPLETE", "INCOMPLETE"}
        and pcb_keepout_coverage.map_sha256 != keepout_map_sha256
    ):
        pcb_keepout_coverage = PcbKeepoutCoverageReport(
            status="BLOCKED",
            mode=keepout_mode,
            map_sha256=keepout_map_sha256,
            issue="Keepout coverage does not bind the current project-authored map",
        )
    elif pcb_keepout_coverage.status in {"COMPLETE", "INCOMPLETE"} and not (
        pcb_board_source_matches(
            pcb_keepout_coverage.board_path,
            pcb_keepout_coverage.board_sha256,
            source_hashes,
        )
    ):
        pcb_keepout_coverage = PcbKeepoutCoverageReport(
            status="BLOCKED",
            mode=keepout_mode,
            map_sha256=keepout_map_sha256,
            issue="Keepout coverage differs from the current PCB source",
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

    if rf_antenna_mode == "off":
        pcb_rf_module_antenna_coverage = PcbRfModuleAntennaCoverageReport(
            status="DISABLED", mode="off", map_sha256=rf_antenna_map_sha256
        )
    elif (
        rf_antenna_map is None
        and pcb_rf_module_antenna_coverage is not None
        and pcb_rf_module_antenna_coverage.status in {"COMPLETE", "INCOMPLETE"}
    ):
        pcb_rf_module_antenna_coverage = PcbRfModuleAntennaCoverageReport(
            status="BLOCKED", issue="RF module coverage has no current project-authored map"
        )
    elif rf_antenna_map is None:
        pcb_rf_module_antenna_coverage = (
            pcb_rf_module_antenna_coverage or PcbRfModuleAntennaCoverageReport()
        )
    elif pcb_rf_module_antenna_coverage is None:
        pcb_rf_module_antenna_coverage = PcbRfModuleAntennaCoverageReport(
            status="BLOCKED",
            mode=rf_antenna_mode,
            map_sha256=rf_antenna_map_sha256,
            issue="Source-bound native PCB geometry was not supplied for the RF module map",
        )
    elif pcb_rf_module_antenna_coverage.status in {"NOT_REQUESTED", "DISABLED"} or (
        pcb_rf_module_antenna_coverage.status in {"COMPLETE", "INCOMPLETE"}
        and pcb_rf_module_antenna_coverage.map_sha256 != rf_antenna_map_sha256
    ):
        pcb_rf_module_antenna_coverage = PcbRfModuleAntennaCoverageReport(
            status="BLOCKED",
            mode=rf_antenna_mode,
            map_sha256=rf_antenna_map_sha256,
            issue="RF module coverage does not bind the current project-authored map",
        )
    elif pcb_rf_module_antenna_coverage.status in {"COMPLETE", "INCOMPLETE"} and not (
        pcb_board_source_matches(
            pcb_rf_module_antenna_coverage.board_path,
            pcb_rf_module_antenna_coverage.board_sha256,
            source_hashes,
        )
    ):
        pcb_rf_module_antenna_coverage = PcbRfModuleAntennaCoverageReport(
            status="BLOCKED",
            mode=rf_antenna_mode,
            map_sha256=rf_antenna_map_sha256,
            issue="RF module coverage differs from the current PCB source",
        )
    else:
        pcb_rf_module_antenna_coverage = pcb_rf_module_antenna_coverage.model_copy(
            update={"mode": rf_antenna_mode}
        )
    touch_pad_clearance_map = policy.pcb_touch_pad_clearance_map
    touch_pad_clearance_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.touch_pad_reference_clearance"),
        None,
    )
    touch_pad_clearance_mode: Literal["review", "block", "off"] = (
        "review" if touch_pad_clearance_override is None else touch_pad_clearance_override.mode
    )
    touch_pad_clearance_map_sha256 = (
        hashlib.sha256(touch_pad_clearance_map.model_dump_json().encode("utf-8")).hexdigest()
        if touch_pad_clearance_map is not None
        else None
    )
    if touch_pad_clearance_mode == "off":
        pcb_touch_pad_clearance_coverage = PcbTouchPadClearanceCoverageReport(
            status="DISABLED",
            mode="off",
            map_sha256=touch_pad_clearance_map_sha256,
        )
    elif (
        touch_pad_clearance_map is None
        and pcb_touch_pad_clearance_coverage is not None
        and pcb_touch_pad_clearance_coverage.status in {"COMPLETE", "INCOMPLETE"}
    ):
        pcb_touch_pad_clearance_coverage = PcbTouchPadClearanceCoverageReport(
            status="BLOCKED", issue="Touch-pad coverage has no current project-authored map"
        )
    elif touch_pad_clearance_map is None:
        pcb_touch_pad_clearance_coverage = (
            pcb_touch_pad_clearance_coverage or PcbTouchPadClearanceCoverageReport()
        )
    elif pcb_touch_pad_clearance_coverage is None:
        pcb_touch_pad_clearance_coverage = PcbTouchPadClearanceCoverageReport(
            status="BLOCKED",
            mode=touch_pad_clearance_mode,
            map_sha256=touch_pad_clearance_map_sha256,
            issue="Source-bound native PCB geometry was not supplied for the touch-pad clearance map",
        )
    elif pcb_touch_pad_clearance_coverage.status in {"NOT_REQUESTED", "DISABLED"} or (
        pcb_touch_pad_clearance_coverage.status in {"COMPLETE", "INCOMPLETE"}
        and pcb_touch_pad_clearance_coverage.map_sha256 != touch_pad_clearance_map_sha256
    ):
        pcb_touch_pad_clearance_coverage = PcbTouchPadClearanceCoverageReport(
            status="BLOCKED",
            mode=touch_pad_clearance_mode,
            map_sha256=touch_pad_clearance_map_sha256,
            issue="Touch-pad clearance coverage does not bind the current project-authored map",
        )
    elif pcb_touch_pad_clearance_coverage.status in {"COMPLETE", "INCOMPLETE"} and not (
        pcb_board_source_matches(
            pcb_touch_pad_clearance_coverage.board_path,
            pcb_touch_pad_clearance_coverage.board_sha256,
            source_hashes,
        )
    ):
        pcb_touch_pad_clearance_coverage = PcbTouchPadClearanceCoverageReport(
            status="BLOCKED",
            mode=touch_pad_clearance_mode,
            map_sha256=touch_pad_clearance_map_sha256,
            issue="Touch-pad clearance differs from the current PCB source",
        )
    else:
        pcb_touch_pad_clearance_coverage = pcb_touch_pad_clearance_coverage.model_copy(
            update={"mode": touch_pad_clearance_mode}
        )
    return PcbInputCoveragePolicyState(
        signal_path=pcb_signal_path_coverage,
        keepout=pcb_keepout_coverage,
        rf_antenna=pcb_rf_module_antenna_coverage,
        touch_pad_clearance=pcb_touch_pad_clearance_coverage,
    )
