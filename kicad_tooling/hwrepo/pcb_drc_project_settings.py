"""Typed extraction of the KiCad project settings used by PCB DRC review."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, JsonValue

from .contracts import parse_model_text

CORE_DRC_CHECK_IDS = frozenset(
    {
        "clearance",
        "copper_edge_clearance",
        "shorting_items",
        "tracks_crossing",
        "unconnected_items",
    }
)
DFM_ERROR_DEFAULT_DRC_CHECK_IDS = frozenset(
    {
        "annular_width",
        "courtyards_overlap",
        "drill_out_of_range",
        "hole_clearance",
        "hole_to_hole",
        "invalid_outline",
        "malformed_courtyard",
        "microvia_drill_out_of_range",
        "solder_mask_bridge",
        "track_angle",
        "track_on_post_machined_layer",
        "track_segment_length",
        "track_width",
    }
)
SIGNAL_INTEGRITY_ERROR_DEFAULT_DRC_CHECK_IDS = frozenset(
    {
        "diff_pair_gap_out_of_range",
        "diff_pair_uncoupled_length_too_long",
        "length_out_of_range",
        "skew_out_of_range",
        "too_many_vias",
    }
)
ELECTRICAL_ERROR_DEFAULT_DRC_CHECK_IDS = frozenset({"creepage", "starved_thermal"})
MISCELLANEOUS_ERROR_DEFAULT_DRC_CHECK_IDS = frozenset(
    {
        "footprint",
        "item_on_disabled_layer",
        "items_not_allowed",
        "npth_inside_courtyard",
        "pth_inside_courtyard",
        "text_on_edge_cuts",
        "through_hole_pad_without_hole",
        "unresolved_variable",
        "zones_intersect",
    }
)
WARNING_DEFAULT_DRC_CHECK_IDS = frozenset(
    {
        "connection_width",
        "copper_sliver",
        "duplicate_footprints",
        "extra_footprint",
        "hole_to_hole",
        "holes_co_located",
        "isolated_copper",
        "lib_footprint_issues",
        "lib_footprint_mismatch",
        "missing_footprint",
        "missing_tuning_profile",
        "mirrored_text_on_front_layer",
        "net_conflict",
        "nonmirrored_text_on_back_layer",
        "padstack",
        "footprint_symbol_field_mismatch",
        "footprint_symbol_mismatch",
        "silk_edge_clearance",
        "silk_overlap",
        "silk_over_copper",
        "text_height",
        "text_thickness",
        "track_dangling",
        "via_dangling",
    }
)
SUPPORTED_DRC_EXCLUSION_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class PcbDrcCheckSeverity:
    """One explicit KiCad check severity parsed from project settings."""

    check_id: str
    configured_severity: str


@dataclass(frozen=True, slots=True)
class PcbDrcRuleSeveritySetting:
    """One saved DRC severity-map key and its stable JSON value."""

    check_id: str
    configured_value_json: str


class _PcbDesignSettingsMeta(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    version: int | None = None


class _PcbDesignSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    meta: _PcbDesignSettingsMeta | None = None
    rule_severities: dict[str, JsonValue] | None = None
    drc_exclusions: list[str | tuple[str, ...]] | None = None


class _PcbProjectBoard(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    design_settings: _PcbDesignSettings | None = None


class _PcbProjectSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    board: _PcbProjectBoard | None = None


def _configured_drc_check_severities(
    document: str, check_ids: frozenset[str]
) -> tuple[PcbDrcCheckSeverity, ...]:
    project = parse_model_text(document, _PcbProjectSettings)
    if project.board is None or project.board.design_settings is None:
        return ()
    severities = project.board.design_settings.rule_severities or {}
    checks: list[PcbDrcCheckSeverity] = []
    for check_id in sorted(check_ids):
        if check_id not in severities:
            continue
        severity = severities[check_id]
        if not isinstance(severity, str):
            raise TypeError(
                "PCB DRC severity in board.design_settings.rule_severities "
                f"for {check_id!r} must be a string"
            )
        checks.append(PcbDrcCheckSeverity(check_id, severity))
    return tuple(checks)


def configured_pcb_drc_rule_severity_settings(
    document: str,
) -> tuple[PcbDrcRuleSeveritySetting, ...]:
    """Return saved DRC severity keys and values in deterministic key order."""
    project = parse_model_text(document, _PcbProjectSettings)
    if project.board is None or project.board.design_settings is None:
        return ()
    severities = project.board.design_settings.rule_severities or {}
    return tuple(
        PcbDrcRuleSeveritySetting(
            check_id=check_id,
            configured_value_json=json.dumps(
                severities[check_id], sort_keys=True, separators=(",", ":"), allow_nan=False
            ),
        )
        for check_id in sorted(severities)
    )


def configured_core_drc_check_severities(document: str) -> tuple[PcbDrcCheckSeverity, ...]:
    """Return explicit severities for the bounded core electrical DRC checks."""
    return _configured_drc_check_severities(document, CORE_DRC_CHECK_IDS)


def configured_dfm_drc_check_severities(document: str) -> tuple[PcbDrcCheckSeverity, ...]:
    """Return explicit severities for documented Error-default DFM checks."""
    return _configured_drc_check_severities(document, DFM_ERROR_DEFAULT_DRC_CHECK_IDS)


def configured_signal_integrity_drc_check_severities(
    document: str,
) -> tuple[PcbDrcCheckSeverity, ...]:
    """Return explicit severities for documented Error-default signal-integrity checks."""
    return _configured_drc_check_severities(document, SIGNAL_INTEGRITY_ERROR_DEFAULT_DRC_CHECK_IDS)


def configured_electrical_drc_check_severities(
    document: str,
) -> tuple[PcbDrcCheckSeverity, ...]:
    """Return explicit severities for bounded Error-default electrical DRC checks."""
    return _configured_drc_check_severities(document, ELECTRICAL_ERROR_DEFAULT_DRC_CHECK_IDS)


def configured_miscellaneous_drc_check_severities(
    document: str,
) -> tuple[PcbDrcCheckSeverity, ...]:
    """Return severities for bounded Error-default miscellaneous DRC checks."""
    return _configured_drc_check_severities(document, MISCELLANEOUS_ERROR_DEFAULT_DRC_CHECK_IDS)


def configured_warning_default_drc_check_severities(
    document: str,
) -> tuple[PcbDrcCheckSeverity, ...]:
    """Return explicit severities for reviewed KiCad 10.0 Warning-default checks."""
    return _configured_drc_check_severities(document, WARNING_DEFAULT_DRC_CHECK_IDS)


def ignored_core_drc_check_ids(document: str) -> tuple[str, ...]:
    """Return supported core DRC checks explicitly set to ``ignore``."""
    return tuple(
        check.check_id
        for check in configured_core_drc_check_severities(document)
        if check.configured_severity == "ignore"
    )


@dataclass(frozen=True, slots=True)
class PcbDrcExclusion:
    """One serialized KiCad PCB DRC exclusion and its optional review comment."""

    marker: str
    comment: str


def pcb_drc_exclusions(document: str) -> tuple[PcbDrcExclusion, ...]:
    """Read KiCad 10.0 project exclusions from strings or marker/comment pairs."""
    project = parse_model_text(document, _PcbProjectSettings)
    if project.board is None or project.board.design_settings is None:
        return ()
    settings = project.board.design_settings
    if (
        settings.meta is not None
        and settings.meta.version is not None
        and settings.meta.version != SUPPORTED_DRC_EXCLUSION_SCHEMA_VERSION
    ):
        raise ValueError(
            f"PCB DRC exclusion settings schema version is not supported: {settings.meta.version}"
        )
    records = settings.drc_exclusions or []
    exclusions: list[PcbDrcExclusion] = []
    seen_markers: set[str] = set()
    for record in records:
        exclusion_record: str | tuple[str, ...] = record
        if isinstance(exclusion_record, str):
            marker, comment = exclusion_record, ""
        else:
            if not exclusion_record:
                raise ValueError("PCB DRC exclusion marker/comment pair is empty")
            marker, comment = (
                exclusion_record[0],
                exclusion_record[1] if len(exclusion_record) > 1 else "",
            )
        if not marker or not marker.partition("|")[0]:
            raise ValueError("PCB DRC exclusion marker is empty or missing its rule key")
        if marker in seen_markers:
            raise ValueError("PCB DRC exclusion markers must be unique")
        seen_markers.add(marker)
        exclusions.append(PcbDrcExclusion(marker=marker, comment=comment))
    return tuple(sorted(exclusions, key=lambda exclusion: (exclusion.marker, exclusion.comment)))
