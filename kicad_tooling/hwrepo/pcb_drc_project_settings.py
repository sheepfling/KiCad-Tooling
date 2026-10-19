"""Typed extraction of the KiCad project settings used by PCB DRC review."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

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
SUPPORTED_DRC_EXCLUSION_SCHEMA_VERSION = 2


class _PcbDesignSettingsMeta(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    version: int | None = None


class _PcbDesignSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    meta: _PcbDesignSettingsMeta | None = None
    rule_severities: dict[str, str] | None = None
    drc_exclusions: list[str | tuple[str, ...]] | None = None


class _PcbProjectBoard(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    design_settings: _PcbDesignSettings | None = None


class _PcbProjectSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    board: _PcbProjectBoard | None = None


def ignored_core_drc_check_ids(document: str) -> tuple[str, ...]:
    """Return supported core DRC checks explicitly set to ``ignore``.

    Only connection, shorting, and clearance checks with Error defaults in the
    KiCad 10 PCB Editor reference manual are included. Other checks can
    legitimately default to Ignore and are deliberately outside this rule.
    """
    project = parse_model_text(document, _PcbProjectSettings)
    if project.board is None or project.board.design_settings is None:
        return ()
    severities = project.board.design_settings.rule_severities or {}
    return tuple(
        check_id for check_id in sorted(CORE_DRC_CHECK_IDS) if severities.get(check_id) == "ignore"
    )


@dataclass(frozen=True)
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
        if isinstance(record, str):
            marker, comment = record, ""
        else:
            if not record:
                raise ValueError("PCB DRC exclusion marker/comment pair is empty")
            marker, comment = record[0], record[1] if len(record) > 1 else ""
        if not marker or not marker.partition("|")[0]:
            raise ValueError("PCB DRC exclusion marker is empty or missing its rule key")
        if marker in seen_markers:
            raise ValueError("PCB DRC exclusion markers must be unique")
        seen_markers.add(marker)
        exclusions.append(PcbDrcExclusion(marker=marker, comment=comment))
    return tuple(sorted(exclusions, key=lambda exclusion: (exclusion.marker, exclusion.comment)))
