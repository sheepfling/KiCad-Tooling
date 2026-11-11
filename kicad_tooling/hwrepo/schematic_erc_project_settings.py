"""Typed extraction of saved schematic ERC exclusions from project settings."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from .contracts import parse_model_text

SUPPORTED_ERC_EXCLUSION_SCHEMA_VERSION = 1


class _ErcMeta(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    version: int | None = None


class _ErcSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    meta: _ErcMeta | None = None
    erc_exclusions: list[JsonValue] | None = None


class _ProjectSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    erc: _ErcSettings | None = None


@dataclass(frozen=True, slots=True)
class SchematicErcExclusion:
    """One persisted exclusion, retaining a canonical marker and comment."""

    marker: str
    error_type: str
    comment: str


def _proto_marker_identity(value: JsonValue) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise TypeError("KiCad 10 ERC exclusion must contain a marker object")
    error_type = value.get("error_type")
    position = value.get("position")
    items = value.get("items")
    if not isinstance(error_type, str) or not error_type.strip():
        raise ValueError("ERC exclusion marker has no error_type")
    if not isinstance(position, dict) or not isinstance(items, list):
        raise TypeError("ERC exclusion marker does not match the supported KiCad 10 schema")
    coordinates = (position.get("x_nm"), position.get("y_nm"))
    if not all(
        isinstance(coordinate, str) and re.fullmatch(r"-?\d+", coordinate) is not None
        for coordinate in coordinates
    ):
        raise ValueError("ERC exclusion marker position must contain integer x_nm and y_nm strings")
    if not items:
        raise ValueError("ERC exclusion marker items must contain non-empty UUID values")
    item_values: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("ERC exclusion marker items must contain non-empty UUID values")
        item_value = item.get("value")
        if not isinstance(item_value, str):
            raise TypeError("ERC exclusion marker items must contain non-empty UUID values")
        item_values.append(item_value)
    try:
        parsed_uuids = [UUID(item_value) for item_value in item_values]
    except ValueError as exc:
        raise ValueError("ERC exclusion marker item values must be UUIDs") from exc
    if any(
        str(parsed) != item_value
        for parsed, item_value in zip(parsed_uuids, item_values, strict=True)
    ):
        raise ValueError("ERC exclusion marker item values must be canonical UUIDs")
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return canonical, error_type


def _legacy_marker_identity(value: JsonValue) -> tuple[str, str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Legacy ERC exclusion marker is empty or not text")
    error_type = value.partition("|")[0]
    if not error_type:
        raise ValueError("Legacy ERC exclusion marker is missing its error type")
    return value, error_type


def _read_exclusion(record: JsonValue, schema_version: int) -> SchematicErcExclusion:
    if schema_version == SUPPORTED_ERC_EXCLUSION_SCHEMA_VERSION:
        if not isinstance(record, dict):
            raise ValueError("KiCad 10 ERC exclusions must use marker objects")
        marker, error_type = _proto_marker_identity(record.get("marker"))
        comment_value = record.get("comment", "")
        if not isinstance(comment_value, str):
            raise ValueError("ERC exclusion comment must be text")
        comment = comment_value
    elif isinstance(record, str):
        marker, error_type = _legacy_marker_identity(record)
        comment = ""
    elif isinstance(record, list) and len(record) in {1, 2} and isinstance(record[0], str):
        marker, error_type = _legacy_marker_identity(record[0])
        comment = record[1] if len(record) == 2 else ""
        if not isinstance(comment, str):
            raise ValueError("Legacy ERC exclusion comment must be text")
    else:
        raise ValueError("Legacy ERC exclusion must be a marker or marker/comment pair")
    if error_type.startswith("ERCET_"):
        error_type = error_type.removeprefix("ERCET_").lower()
    return SchematicErcExclusion(marker=marker, error_type=error_type, comment=comment)


def schematic_erc_exclusions(document: str) -> tuple[SchematicErcExclusion, ...]:
    """Return supported persisted ERC exclusions, rejecting unknown schemas."""
    project = parse_model_text(document, _ProjectSettings)
    if project.erc is None:
        return ()
    settings = project.erc
    if "meta" in settings.model_fields_set and settings.meta is None:
        raise ValueError("ERC exclusion settings metadata is malformed")
    if "erc_exclusions" in settings.model_fields_set and settings.erc_exclusions is None:
        raise ValueError("ERC exclusion list must be an array")
    schema_version = settings.meta.version if settings.meta is not None else 0
    if schema_version not in {0, SUPPORTED_ERC_EXCLUSION_SCHEMA_VERSION}:
        raise ValueError(
            f"ERC exclusion settings schema version is not supported: {schema_version}"
        )
    records = settings.erc_exclusions or []
    exclusions = tuple(_read_exclusion(record, schema_version) for record in records)
    markers = [item.marker for item in exclusions]
    if len(markers) != len(set(markers)):
        raise ValueError("ERC exclusion markers must be unique")
    return tuple(sorted(exclusions, key=lambda item: (item.marker, item.comment)))


def schematic_erc_exclusion_marker_sha256(exclusion: SchematicErcExclusion) -> str:
    """Return the stable identity digest used by source-bound review findings."""
    return hashlib.sha256(exclusion.marker.encode("utf-8")).hexdigest()
