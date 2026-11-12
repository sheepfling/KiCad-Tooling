"""Lossless parsing of repeated root-level PCB net settings sections."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

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
_DUPLICATE_NETCLASS_CLEARANCE_MEMBER = (("net_settings", "classes"), "clearance")
_DUPLICATE_NETCLASS_ASSIGNMENT_PATH = ("net_settings", "netclass_assignments")
_DUPLICATE_ROOT_CLEARANCE_MEMBER = ((), "clearance")


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
    property_name: str | None = None
    net_name: str | None = None


@dataclass(frozen=True, slots=True)
class PcbUnresolvedNetClassAssignment:
    """One net assignment that names no declared class in a complete class list."""

    net_name: str
    assigned_class: str
    declared_class_names: tuple[str, ...]
    assigned_classes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.net_name or not self.assigned_class:
            raise ValueError("PCB netclass assignments require non-empty names")
        if not self.declared_class_names or "Default" not in self.declared_class_names:
            raise ValueError("PCB netclass assignment evidence requires a complete class list")
        if self.assigned_class in self.declared_class_names:
            raise ValueError("PCB netclass assignment must name an undeclared class")
        if self.assigned_classes and (
            any(not name for name in self.assigned_classes)
            or self.assigned_class not in self.assigned_classes
        ):
            raise ValueError("PCB netclass assignment list must retain its unresolved class")


@dataclass(frozen=True, slots=True)
class PcbMalformedNetClassAssignment:
    """Netclass assignment whose JSON shape is outside KiCad's measured forms."""

    net_name: str | None
    observed_json_type: str
    malformed_member_indexes: tuple[int, ...] = ()
    malformed_member_kinds: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        allowed_json_types = {"array", "boolean", "null", "number", "object", "string"}
        if self.observed_json_type not in allowed_json_types:
            raise ValueError("PCB netclass assignment must retain a JSON type")
        if self.net_name is not None and not self.net_name:
            raise ValueError("PCB netclass assignment net name cannot be empty")
        if len(self.malformed_member_indexes) != len(self.malformed_member_kinds):
            raise ValueError("PCB netclass assignment member evidence must align")
        if tuple(sorted(set(self.malformed_member_indexes))) != self.malformed_member_indexes:
            raise ValueError("PCB netclass assignment member indexes must be unique and ordered")
        if any(index < 0 for index in self.malformed_member_indexes):
            raise ValueError("PCB netclass assignment member indexes cannot be negative")
        if self.observed_json_type != "array" and self.malformed_member_indexes:
            raise ValueError("Only array assignments can have malformed member indexes")


def validate_pcb_settings_document(
    document: str,
    *,
    allow_source_bound_duplicates: bool,
) -> None:
    """Validate PCB project settings while allowing only reviewed repeated values."""
    duplicate_members = _KNOWN_DUPLICATE_ROOT_SETTINGS_MEMBERS
    duplicate_paths: frozenset[tuple[str, ...]] = frozenset()
    if allow_source_bound_duplicates:
        duplicate_members = duplicate_members | {
            _DUPLICATE_NET_SETTINGS_CLASSES_MEMBER,
            _DUPLICATE_NETCLASS_CLEARANCE_MEMBER,
        }
        duplicate_paths = _KNOWN_DUPLICATE_SEVERITY_PATHS | {
            _DUPLICATE_NETCLASS_ASSIGNMENT_PATH,
        }
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
    validate_pcb_settings_document(
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


def _conflicting_netclass_assignment_settings(
    net_settings: JsonObjectPairs,
) -> tuple[PcbConflictingNetClassSettings, ...]:
    """Retain repeated net keys with different netclass values in source order."""
    assignment_maps = tuple(
        value for key, value in net_settings.pairs if key == "netclass_assignments"
    )
    if len(assignment_maps) != 1 or not isinstance(assignment_maps[0], JsonObjectPairs):
        return ()

    assignments_by_net: dict[str, list[str]] = {}
    for net_name, value in assignment_maps[0].pairs:
        assignments_by_net.setdefault(net_name, []).append(
            canonical_json_value(json_value_from_object_pairs(value))
        )
    return tuple(
        PcbConflictingNetClassSettings(
            conflict_scope="netclass_assignment",
            class_name=None,
            source_order_values_json=tuple(values),
            net_name=net_name,
        )
        for net_name, values in sorted(assignments_by_net.items())
        if len(values) > 1 and len(set(values)) > 1
    )


def configured_pcb_conflicting_netclass_settings(
    document: str,
) -> tuple[PcbConflictingNetClassSettings, ...]:
    """Retain conflicting duplicate netclass-list, class, and assignment values."""
    validate_pcb_settings_document(document, allow_source_bound_duplicates=True)
    project = json.loads(document, object_pairs_hook=retain_json_object_pairs)
    if not isinstance(project, JsonObjectPairs):
        return ()
    net_settings = tuple(value for key, value in project.pairs if key == "net_settings")
    if len(net_settings) != 1 or not isinstance(net_settings[0], JsonObjectPairs):
        return ()

    class_lists = tuple(value for key, value in net_settings[0].pairs if key == "classes")
    assignment_conflicts = _conflicting_netclass_assignment_settings(net_settings[0])
    if not class_lists:
        return assignment_conflicts
    normalized_lists = tuple(
        json_value_from_object_pairs(
            value,
            allowed_duplicate_object_members=frozenset({_DUPLICATE_ROOT_CLEARANCE_MEMBER}),
        )
        for value in class_lists
    )
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
            *assignment_conflicts,
        )

    definitions_by_name: dict[str, list[str]] = {}
    property_conflicts: dict[tuple[str, str, tuple[str, ...]], PcbConflictingNetClassSettings] = {}
    for class_list in class_lists:
        if not isinstance(class_list, list):
            continue
        for source_definition in cast(list[object], class_list):
            if not isinstance(source_definition, JsonObjectPairs):
                continue
            name = next(
                (value for key, value in reversed(source_definition.pairs) if key == "name"),
                None,
            )
            if not isinstance(name, str) or not name:
                continue
            clearance_values = tuple(
                canonical_json_value(json_value_from_object_pairs(value))
                for key, value in source_definition.pairs
                if key == "clearance"
            )
            if len(clearance_values) > 1 and len(set(clearance_values)) > 1:
                setting = PcbConflictingNetClassSettings(
                    conflict_scope="class_property",
                    class_name=name,
                    source_order_values_json=clearance_values,
                    property_name="clearance",
                )
                property_conflicts[(name.casefold(), "clearance", clearance_values)] = setting
            definition = json_value_from_object_pairs(
                source_definition,
                allowed_duplicate_object_members=frozenset({_DUPLICATE_ROOT_CLEARANCE_MEMBER}),
            )
            if not isinstance(definition, dict):
                continue
            definitions_by_name.setdefault(name, []).append(canonical_json_value(definition))
    class_name_conflicts = tuple(
        PcbConflictingNetClassSettings(
            conflict_scope="class_name",
            class_name=name,
            source_order_values_json=tuple(values),
        )
        for name, values in sorted(definitions_by_name.items())
        if len(set(values)) > 1
    )
    return (*property_conflicts.values(), *class_name_conflicts, *assignment_conflicts)


def configured_pcb_unresolved_netclass_assignments(
    document: str,
) -> tuple[PcbUnresolvedNetClassAssignment, ...]:
    """Find unique assignment targets absent from one complete classes list."""
    validate_pcb_settings_document(document, allow_source_bound_duplicates=True)
    project = json.loads(document, object_pairs_hook=retain_json_object_pairs)
    if not isinstance(project, JsonObjectPairs):
        return ()
    net_settings_members = tuple(value for key, value in project.pairs if key == "net_settings")
    if len(net_settings_members) != 1 or not isinstance(net_settings_members[0], JsonObjectPairs):
        return ()

    net_settings = net_settings_members[0]
    class_lists = tuple(value for key, value in net_settings.pairs if key == "classes")
    assignment_maps = tuple(
        value for key, value in net_settings.pairs if key == "netclass_assignments"
    )
    if (
        len(class_lists) != 1
        or not isinstance(class_lists[0], list)
        or len(assignment_maps) != 1
        or not isinstance(assignment_maps[0], JsonObjectPairs)
    ):
        return ()

    class_names: list[str] = []
    for definition in cast(list[object], class_lists[0]):
        if not isinstance(definition, JsonObjectPairs):
            return ()
        names = tuple(value for key, value in definition.pairs if key == "name")
        if len(names) != 1 or not isinstance(names[0], str) or not names[0]:
            return ()
        class_names.append(names[0])
    if not class_names or "Default" not in class_names:
        return ()

    assignments_by_net: dict[str, list[object]] = {}
    for net_name, value in assignment_maps[0].pairs:
        assignments_by_net.setdefault(net_name, []).append(value)

    unresolved: list[PcbUnresolvedNetClassAssignment] = []
    for net_name, source_values in sorted(assignments_by_net.items()):
        values = tuple(json_value_from_object_pairs(value) for value in source_values)
        normalized = tuple(canonical_json_value(value) for value in values)
        if not net_name or len(set(normalized)) != 1 or not values:
            continue
        assignment = values[0]
        if isinstance(assignment, str) and assignment:
            assigned_classes = (assignment,)
            evidence_classes: tuple[str, ...] = ()
        elif isinstance(assignment, list) and all(
            isinstance(name, str) and name for name in assignment
        ):
            assigned_classes = tuple(cast(list[str], assignment))
            evidence_classes = assigned_classes
        else:
            continue
        unresolved_classes = tuple(
            name for name in dict.fromkeys(assigned_classes) if name not in class_names
        )
        for assigned_class in unresolved_classes:
            unresolved.append(
                PcbUnresolvedNetClassAssignment(
                    net_name=net_name,
                    assigned_class=assigned_class,
                    declared_class_names=tuple(class_names),
                    assigned_classes=evidence_classes,
                )
            )
    return tuple(unresolved)


def pcb_json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (JsonObjectPairs, dict)):
        return "object"
    if isinstance(value, list):
        return "array"
    raise TypeError(f"unsupported decoded JSON value type: {type(value).__name__}")


def _pcb_json_member_kind(value: object) -> str:
    if value == "":
        return "empty-string"
    return pcb_json_type(value)


def _malformed_pcb_netclass_assignment(
    net_name: str | None,
    assignment: JsonValue,
) -> PcbMalformedNetClassAssignment | None:
    if isinstance(assignment, str):
        return None
    if not isinstance(assignment, list):
        return PcbMalformedNetClassAssignment(
            net_name=net_name,
            observed_json_type=pcb_json_type(assignment),
        )

    assignment_members = cast(list[JsonValue], assignment)
    malformed_members = tuple(
        (index, _pcb_json_member_kind(value))
        for index, value in enumerate(assignment_members)
        if not isinstance(value, str) or not value
    )
    if not malformed_members:
        return None
    return PcbMalformedNetClassAssignment(
        net_name=net_name,
        observed_json_type="array",
        malformed_member_indexes=tuple(index for index, _ in malformed_members),
        malformed_member_kinds=tuple(kind for _, kind in malformed_members),
    )


def configured_pcb_malformed_netclass_assignments(
    document: str,
) -> tuple[PcbMalformedNetClassAssignment, ...]:
    """Find unsupported JSON shapes in unique PCB netclass assignment settings."""
    validate_pcb_settings_document(document, allow_source_bound_duplicates=True)
    project = json.loads(document, object_pairs_hook=retain_json_object_pairs)
    if not isinstance(project, JsonObjectPairs):
        return ()

    net_settings_members = tuple(value for key, value in project.pairs if key == "net_settings")
    if len(net_settings_members) != 1 or not isinstance(net_settings_members[0], JsonObjectPairs):
        return ()
    assignment_maps = tuple(
        value for key, value in net_settings_members[0].pairs if key == "netclass_assignments"
    )
    if len(assignment_maps) != 1:
        return ()

    assignment_map = assignment_maps[0]
    if not isinstance(assignment_map, JsonObjectPairs):
        return (
            PcbMalformedNetClassAssignment(
                net_name=None,
                observed_json_type=pcb_json_type(assignment_map),
            ),
        )

    assignments_by_net: dict[str, list[JsonValue]] = {}
    for net_name, value in assignment_map.pairs:
        assignments_by_net.setdefault(net_name, []).append(json_value_from_object_pairs(value))

    malformed: list[PcbMalformedNetClassAssignment] = []
    for net_name, values in sorted(assignments_by_net.items()):
        normalized = tuple(canonical_json_value(value) for value in values)
        if not net_name or len(set(normalized)) != 1:
            continue
        candidate = _malformed_pcb_netclass_assignment(net_name, values[0])
        if candidate is not None:
            malformed.append(candidate)
    return tuple(malformed)
