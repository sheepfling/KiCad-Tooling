"""Lossless parsing of repeated root-level PCB net settings sections."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, JsonValue

from .contracts import parse_model_text_allow_duplicate_json_keys_at
from .json_object_pairs import (
    JsonObjectPairs,
    json_object_pairs_source_order_value,
    retain_json_object_pairs,
)
from .json_value_support import canonical_json_value

_KNOWN_DUPLICATE_ROOT_SETTINGS_MEMBERS = frozenset(
    {
        ((), "board"),
        ((), "erc"),
        ((), "net_settings"),
    }
)


class _PcbProjectSettingsRoot(BaseModel):
    """Validate project roots while tolerating only reviewed repeated sections."""

    model_config = ConfigDict(extra="allow", strict=True)

    meta: JsonValue | None = None
    board: JsonValue | None = None
    net_settings: JsonValue | None = None


@dataclass(frozen=True, slots=True)
class PcbDuplicateNetSettingsSectionSetting:
    """Repeated root net_settings objects represented in source order."""

    source_order_sections_json: tuple[str, ...]


def configured_pcb_duplicate_net_settings_sections(
    document: str,
) -> tuple[PcbDuplicateNetSettingsSectionSetting, ...]:
    """Return duplicate root net_settings sections without collapsing their order."""
    parse_model_text_allow_duplicate_json_keys_at(
        document,
        _PcbProjectSettingsRoot,
        allowed_duplicate_object_paths=frozenset(),
        allowed_duplicate_object_members=_KNOWN_DUPLICATE_ROOT_SETTINGS_MEMBERS,
    )
    project = json.loads(document, object_pairs_hook=retain_json_object_pairs)
    if not isinstance(project, JsonObjectPairs):
        return ()
    values = tuple(value for key, value in project.pairs if key == "net_settings")
    if len(values) < 2:
        return ()
    return (
        PcbDuplicateNetSettingsSectionSetting(
            source_order_sections_json=tuple(
                canonical_json_value(json_object_pairs_source_order_value(value))
                for value in values
            ),
        ),
    )
