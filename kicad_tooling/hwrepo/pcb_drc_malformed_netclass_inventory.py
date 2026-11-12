"""Recognition of unsupported PCB netclass inventory JSON shapes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from .json_object_pairs import JsonObjectPairs, retain_json_object_pairs
from .pcb_drc_duplicate_net_settings_sections import (
    pcb_json_type,
    validate_pcb_settings_document,
)


@dataclass(frozen=True, slots=True)
class PcbMalformedNetClassInventory:
    """A classes list or one of its entries outside KiCad's loaded shapes."""

    location: str
    problem: str
    observed_json_type: str
    entry_index: int | None = None

    def __post_init__(self) -> None:
        allowed_json_types = {"array", "boolean", "null", "number", "object", "string"}
        if self.observed_json_type not in allowed_json_types:
            raise ValueError("PCB netclass inventory must retain a JSON type")
        if self.problem == "classes_not_array":
            if self.location != "net_settings.classes" or self.entry_index is not None:
                raise ValueError("Malformed classes collection evidence has an invalid location")
            if self.observed_json_type == "array":
                raise ValueError("Malformed classes collection evidence requires a non-array type")
        elif self.problem == "entry_not_object":
            if self.entry_index is None or self.observed_json_type == "object":
                raise ValueError("Malformed class entry evidence must identify a non-object item")
        elif self.problem == "entry_missing_name":
            if self.entry_index is None or self.observed_json_type != "object":
                raise ValueError("Unnamed class evidence must identify an object item")
        elif self.problem == "entry_name_not_string":
            if self.entry_index is None or self.observed_json_type == "string":
                raise ValueError("Non-string class name evidence must retain its JSON type")
        elif self.problem == "entry_name_empty":
            if self.entry_index is None or self.observed_json_type != "string":
                raise ValueError("Empty class name evidence must identify a string value")
        else:
            raise ValueError("Unsupported PCB netclass inventory problem")
        if self.entry_index is not None and self.entry_index < 0:
            raise ValueError("PCB netclass inventory entry index cannot be negative")


def configured_pcb_malformed_netclass_inventory(
    document: str,
) -> tuple[PcbMalformedNetClassInventory, ...]:
    """Find classes containers and entries KiCad 10.0.8 silently leaves unloaded."""
    validate_pcb_settings_document(document, allow_source_bound_duplicates=True)
    project = json.loads(document, object_pairs_hook=retain_json_object_pairs)
    if not isinstance(project, JsonObjectPairs):
        return ()

    net_settings_members = tuple(value for key, value in project.pairs if key == "net_settings")
    if len(net_settings_members) != 1 or not isinstance(net_settings_members[0], JsonObjectPairs):
        return ()
    classes_members = tuple(
        value for key, value in net_settings_members[0].pairs if key == "classes"
    )
    if len(classes_members) != 1:
        return ()

    classes = classes_members[0]
    if not isinstance(classes, list):
        return (
            PcbMalformedNetClassInventory(
                location="net_settings.classes",
                problem="classes_not_array",
                observed_json_type=pcb_json_type(classes),
            ),
        )

    malformed: list[PcbMalformedNetClassInventory] = []
    for entry_index, entry in enumerate(cast(list[object], classes)):
        location = f"net_settings.classes[{entry_index}]"
        if not isinstance(entry, JsonObjectPairs):
            malformed.append(
                PcbMalformedNetClassInventory(
                    location=location,
                    problem="entry_not_object",
                    observed_json_type=pcb_json_type(entry),
                    entry_index=entry_index,
                )
            )
        else:
            names = tuple(value for key, value in entry.pairs if key == "name")
            if not names:
                malformed.append(
                    PcbMalformedNetClassInventory(
                        location=location,
                        problem="entry_missing_name",
                        observed_json_type="object",
                        entry_index=entry_index,
                    )
                )
            elif len(names) == 1 and not isinstance(names[0], str):
                malformed.append(
                    PcbMalformedNetClassInventory(
                        location=location,
                        problem="entry_name_not_string",
                        observed_json_type=pcb_json_type(names[0]),
                        entry_index=entry_index,
                    )
                )
            elif len(names) == 1 and names[0] == "":
                malformed.append(
                    PcbMalformedNetClassInventory(
                        location=location,
                        problem="entry_name_empty",
                        observed_json_type="string",
                        entry_index=entry_index,
                    )
                )
    return tuple(malformed)
