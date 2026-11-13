"""Read complete project netclass names visible to native PCB DRC rules."""

from __future__ import annotations

import json
from typing import cast

from .json_object_pairs import (
    JsonObjectPairs,
    retain_json_object_pairs,
    unique_json_array_member,
    unique_json_string_member,
)


def pcb_project_netclass_scope_names(document: str) -> tuple[str, ...] | None:
    """Return declared and referenced class names from a unique project inventory.

    KiCad custom DRC rules can match class names that are referenced by net
    assignments or netclass patterns even when no class definition exists.
    Include each source of a class name so this review does not duplicate a
    separate unresolved-assignment finding.
    """
    try:
        root = json.loads(document, object_pairs_hook=retain_json_object_pairs)
    except (json.JSONDecodeError, RecursionError):
        return None
    if not isinstance(root, JsonObjectPairs):
        return None
    net_settings_values = tuple(value for key, value in root.pairs if key == "net_settings")
    if len(net_settings_values) != 1 or not isinstance(net_settings_values[0], JsonObjectPairs):
        return None

    net_settings = net_settings_values[0]
    class_definitions = unique_json_array_member(net_settings, "classes")
    if class_definitions is None:
        return None
    names: list[str] = []
    for definition in class_definitions:
        if not isinstance(definition, JsonObjectPairs):
            return None
        name = unique_json_string_member(definition, "name")
        if not name:
            return None
        names.append(name)
    if not names or "Default" not in names or len(set(names)) != len(names):
        return None

    assignment_members = tuple(
        value for key, value in net_settings.pairs if key == "netclass_assignments"
    )
    if len(assignment_members) > 1:
        return None
    assignments = assignment_members[0] if assignment_members else JsonObjectPairs(())
    if not isinstance(assignments, JsonObjectPairs):
        return None
    for net_name, assignment in assignments.pairs:
        if not net_name:
            return None
        if isinstance(assignment, str) and assignment:
            names.append(assignment)
        elif isinstance(assignment, list):
            assignment_items = cast(list[object], assignment)
            assignment_names = tuple(
                item for item in assignment_items if isinstance(item, str) and item
            )
            if len(assignment_names) != len(assignment_items):
                return None
            names.extend(assignment_names)
        else:
            return None

    pattern_members = tuple(
        value for key, value in net_settings.pairs if key == "netclass_patterns"
    )
    if len(pattern_members) > 1:
        return None
    pattern_value: object = pattern_members[0] if pattern_members else []
    if not isinstance(pattern_value, list):
        return None
    patterns = cast(list[object], pattern_value)
    for entry in patterns:
        if not isinstance(entry, JsonObjectPairs):
            return None
        pattern = unique_json_string_member(entry, "pattern")
        netclass = unique_json_string_member(entry, "netclass")
        if not pattern or not netclass:
            return None
        names.append(netclass)

    distinct_names = tuple(dict.fromkeys(names))
    if any(not name.isascii() for name in distinct_names):
        return None
    folded = tuple(name.casefold() for name in distinct_names)
    if len(set(folded)) != len(folded):
        return None
    return tuple(sorted(distinct_names, key=lambda name: (name.casefold(), name)))
