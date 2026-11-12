"""Lossless parsing of repeated root-level PCB net settings sections."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, JsonValue

from .contracts import parse_model_text_allow_duplicate_json_keys_at
from .json_object_pairs import (
    JsonObjectPairs,
    json_object_pairs_source_order_value,
    json_value_from_object_pairs,
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
_KNOWN_DUPLICATE_SEVERITY_PATHS = frozenset(
    {
        ("board", "design_settings", "rule_severities"),
        ("erc", "rule_severities"),
    }
)
_DUPLICATE_NET_SETTINGS_CLASSES_MEMBER = (("net_settings",), "classes")


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


@dataclass(frozen=True, slots=True)
class PcbConflictingNetClassSettings:
    """Conflicting source-ordered definitions from the PCB netclass setting."""

    conflict_scope: str
    class_name: str | None
    source_order_values_json: tuple[str, ...]


def _validate_pcb_settings_document(
    document: str,
    *,
    allow_source_bound_duplicates: bool,
) -> None:
    duplicate_members = _KNOWN_DUPLICATE_ROOT_SETTINGS_MEMBERS
    duplicate_paths: frozenset[tuple[str, ...]] = frozenset()
    if allow_source_bound_duplicates:
        duplicate_members = duplicate_members | {_DUPLICATE_NET_SETTINGS_CLASSES_MEMBER}
        duplicate_paths = _KNOWN_DUPLICATE_SEVERITY_PATHS
    parse_model_text_allow_duplicate_json_keys_at(
        document,
        _PcbProjectSettingsRoot,
        allowed_duplicate_object_paths=duplicate_paths,
        allowed_duplicate_object_members=duplicate_members,
    )


def configured_pcb_duplicate_net_settings_sections(
    document: str,
    *,
    allow_source_bound_duplicates: bool = False,
) -> tuple[PcbDuplicateNetSettingsSectionSetting, ...]:
    """Return duplicate root net_settings sections without collapsing their order."""
    _validate_pcb_settings_document(
        document,
        allow_source_bound_duplicates=allow_source_bound_duplicates,
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


def configured_pcb_conflicting_netclass_settings(
    document: str,
) -> tuple[PcbConflictingNetClassSettings, ...]:
    """Retain conflicting duplicate netclass-list and named-class values."""
    _validate_pcb_settings_document(document, allow_source_bound_duplicates=True)
    project = json.loads(document, object_pairs_hook=retain_json_object_pairs)
    if not isinstance(project, JsonObjectPairs):
        return ()
    net_settings = tuple(value for key, value in project.pairs if key == "net_settings")
    if len(net_settings) != 1 or not isinstance(net_settings[0], JsonObjectPairs):
        return ()

    class_lists = tuple(value for key, value in net_settings[0].pairs if key == "classes")
    if not class_lists:
        return ()
    normalized_lists = tuple(json_value_from_object_pairs(value) for value in class_lists)
    signatures = tuple(canonical_json_value(value) for value in normalized_lists)
    if len(class_lists) > 1 and len(set(signatures)) > 1:
        return (
            PcbConflictingNetClassSettings(
                conflict_scope="classes_member",
                class_name=None,
                source_order_values_json=tuple(
                    canonical_json_value(value) for value in normalized_lists
                ),
            ),
        )

    definitions_by_name: dict[str, list[str]] = {}
    for class_list in normalized_lists:
        if not isinstance(class_list, list):
            continue
        for definition in class_list:
            if not isinstance(definition, dict):
                continue
            name = definition.get("name")
            if not isinstance(name, str) or not name:
                continue
            definitions_by_name.setdefault(name, []).append(canonical_json_value(definition))
    return tuple(
        PcbConflictingNetClassSettings(
            conflict_scope="class_name",
            class_name=name,
            source_order_values_json=tuple(values),
        )
        for name, values in sorted(definitions_by_name.items())
        if len(set(values)) > 1
    )
