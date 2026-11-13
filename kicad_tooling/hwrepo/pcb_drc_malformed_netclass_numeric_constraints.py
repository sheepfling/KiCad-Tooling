"""Recognition of nonnumeric PCB netclass constraint values."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from .json_object_pairs import JsonObjectPairs, retain_json_object_pairs
from .pcb_drc_duplicate_net_settings_sections import (
    pcb_json_type,
    validate_pcb_settings_document,
)

PCB_NUMERIC_NETCLASS_CONSTRAINTS = frozenset(
    {
        "clearance",
        "diff_pair_gap",
        "diff_pair_via_gap",
        "diff_pair_width",
        "microvia_diameter",
        "microvia_drill",
        "track_width",
        "via_diameter",
        "via_drill",
    }
)

_JSON_TYPES = frozenset({"array", "boolean", "null", "number", "object", "string"})


@dataclass(frozen=True, slots=True)
class PcbMalformedNetClassNumericConstraint:
    """A nonnumeric source member for a recognized PCB netclass constraint."""

    class_index: int
    class_name: str | None
    property_name: str
    observed_json_type: str
    member_occurrence: int

    def __post_init__(self) -> None:
        if self.class_index < 0:
            raise ValueError("PCB netclass index cannot be negative")
        if self.class_name == "":
            raise ValueError("PCB netclass name cannot be empty")
        if self.property_name not in PCB_NUMERIC_NETCLASS_CONSTRAINTS:
            raise ValueError("Unsupported PCB netclass numeric constraint")
        if self.observed_json_type not in _JSON_TYPES:
            raise ValueError("PCB netclass constraint must retain a JSON type")
        if self.observed_json_type == "number":
            raise ValueError("Nonnumeric PCB netclass constraint requires a nonnumber type")
        if self.member_occurrence < 1:
            raise ValueError("PCB netclass member occurrence is one-based")


def _is_json_number(value: object) -> bool:
    """Match nlohmann JSON number types without Python's bool-as-int behavior."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def configured_pcb_malformed_netclass_numeric_constraints(
    document: str,
) -> tuple[PcbMalformedNetClassNumericConstraint, ...]:
    """Find nonnumeric values in recognized PCB netclass constraint fields."""
    validate_pcb_settings_document(document, allow_source_bound_duplicates=True)
    project = json.loads(document, object_pairs_hook=retain_json_object_pairs)
    if not isinstance(project, JsonObjectPairs):
        return ()

    net_settings = tuple(value for key, value in project.pairs if key == "net_settings")
    if len(net_settings) != 1 or not isinstance(net_settings[0], JsonObjectPairs):
        return ()
    classes_members = tuple(value for key, value in net_settings[0].pairs if key == "classes")
    if len(classes_members) != 1 or not isinstance(classes_members[0], list):
        return ()

    constraints: list[PcbMalformedNetClassNumericConstraint] = []
    for class_index, entry in enumerate(cast(list[object], classes_members[0])):
        if not isinstance(entry, JsonObjectPairs):
            continue
        names = tuple(value for key, value in entry.pairs if key == "name")
        class_name = (
            names[0] if len(names) == 1 and isinstance(names[0], str) and names[0] else None
        )
        occurrences: dict[str, int] = {}
        for property_name, value in entry.pairs:
            if property_name not in PCB_NUMERIC_NETCLASS_CONSTRAINTS:
                continue
            occurrence = occurrences.get(property_name, 0) + 1
            occurrences[property_name] = occurrence
            if _is_json_number(value):
                continue
            constraints.append(
                PcbMalformedNetClassNumericConstraint(
                    class_index=class_index,
                    class_name=class_name,
                    property_name=property_name,
                    observed_json_type=pcb_json_type(value),
                    member_occurrence=occurrence,
                )
            )
    return tuple(constraints)
