"""Typed extraction of saved schematic ERC exclusions from project settings."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, JsonValue

from .contracts import parse_model_text

SUPPORTED_ERC_EXCLUSION_SCHEMA_VERSION = 0


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


def _serialized_marker_identity(value: str) -> tuple[str, str]:
    if not value.strip():
        raise ValueError("ERC exclusion marker is empty")
    fields = value.split("|")
    if len(fields) != 8:
        raise ValueError("ERC exclusion marker must contain eight serialized fields")
    error_type = fields[0]
    if not error_type.strip():
        raise ValueError("ERC exclusion marker is missing its settings key")
    for coordinate in fields[1:3]:
        try:
            if str(int(coordinate)) != coordinate:
                raise ValueError
        except ValueError as exc:
            raise ValueError("ERC exclusion marker coordinates must be integer text") from exc
    return value, error_type


def _read_exclusion(record: JsonValue) -> SchematicErcExclusion:
    if isinstance(record, str):
        marker, error_type = _serialized_marker_identity(record)
        comment = ""
    elif isinstance(record, list) and len(record) == 2:
        marker_value, comment_value = record
        if not isinstance(marker_value, str) or not isinstance(comment_value, str):
            raise TypeError("ERC exclusion marker/comment pair must contain text")
        marker, error_type = _serialized_marker_identity(marker_value)
        comment = comment_value
    else:
        raise ValueError("ERC exclusion must be a serialized marker or marker/comment pair")
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
    exclusions = tuple(_read_exclusion(record) for record in records)
    markers = [item.marker for item in exclusions]
    if len(markers) != len(set(markers)):
        raise ValueError("ERC exclusion markers must be unique")
    return tuple(sorted(exclusions, key=lambda item: (item.marker, item.comment)))


def schematic_erc_exclusion_marker_sha256(exclusion: SchematicErcExclusion) -> str:
    """Return the stable identity digest used by source-bound review findings."""
    return hashlib.sha256(exclusion.marker.encode("utf-8")).hexdigest()
