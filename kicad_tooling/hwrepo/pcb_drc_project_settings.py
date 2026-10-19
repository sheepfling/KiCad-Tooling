"""Typed extraction of the KiCad project settings used by PCB DRC review."""

from __future__ import annotations

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


class _PcbDesignSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    rule_severities: dict[str, str] | None = None


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
