"""Typed extraction of saved schematic ERC exclusions from project settings."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, JsonValue

from .contracts import parse_model_text
from .project_models import ProjectKind

SUPPORTED_ERC_EXCLUSION_SCHEMA_VERSION = 0
ERC_DEFAULT_IGNORED_RULE_KEYS = frozenset(
    {
        "footprint_filter",
        "four_way_junction",
        "simulation_model_issue",
        "single_global_label",
    }
)
ERC_DEFAULT_ERROR_RULE_KEYS = frozenset(
    {
        "bus_definition_conflict",
        "bus_entry_needed",
        "bus_to_bus_conflict",
        "bus_to_net_conflict",
        "different_unit_footprint",
        "different_unit_net",
        "duplicate_reference",
        "duplicate_sheet_names",
        "extra_units",
        "hier_label_mismatch",
        "label_dangling",
        "missing_power_pin",
        "pin_not_connected",
        "pin_not_driven",
        "power_pin_not_driven",
        "unannotated",
        "undefined_netclass",
        "unresolved_variable",
        "unit_value_mismatch",
        "wire_dangling",
    }
)
ERC_DEFAULT_WARNING_RULE_KEYS = frozenset(
    {
        "endpoint_off_grid",
        "field_name_whitespace",
        "footprint_link_issues",
        "ground_pin_not_ground",
        "isolated_pin_label",
        "label_multiple_wires",
        "lib_symbol_issues",
        "lib_symbol_mismatch",
        "missing_bidi_pin",
        "missing_input_pin",
        "missing_unit",
        "multiple_net_names",
        "net_not_bus_member",
        "no_connect_connected",
        "no_connect_dangling",
        "pin_to_pin",
        "same_local_global_label",
        "similar_label_and_power",
        "similar_labels",
        "similar_power",
        "stacked_pin_name",
        "unconnected_wire_endpoint",
    }
)
_ERC_RULE_KEYS_KICAD_10_0: frozenset[str] = (
    ERC_DEFAULT_ERROR_RULE_KEYS | ERC_DEFAULT_WARNING_RULE_KEYS | ERC_DEFAULT_IGNORED_RULE_KEYS
)
# Keep exact patch entries; later KiCad 10.0 releases can add ERC item keys.
_ERC_RULE_KEYS_KICAD_10_0_7 = _ERC_RULE_KEYS_KICAD_10_0 | {"same_local_global_power"}
_ERC_DEFAULT_WARNING_RULE_KEYS_KICAD_10_0_7 = ERC_DEFAULT_WARNING_RULE_KEYS | {
    "same_local_global_power"
}
ERC_RULE_KEYS_BY_KICAD_VERSION: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "10.0.0": _ERC_RULE_KEYS_KICAD_10_0,
        "10.0.5": _ERC_RULE_KEYS_KICAD_10_0,
        "10.0.6": _ERC_RULE_KEYS_KICAD_10_0,
        "10.0.7": _ERC_RULE_KEYS_KICAD_10_0_7,
        "10.0.8": _ERC_RULE_KEYS_KICAD_10_0_7,
    }
)
ERC_DEFAULT_WARNING_RULE_KEYS_BY_KICAD_VERSION: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "10.0.0": ERC_DEFAULT_WARNING_RULE_KEYS,
        "10.0.5": ERC_DEFAULT_WARNING_RULE_KEYS,
        "10.0.6": ERC_DEFAULT_WARNING_RULE_KEYS,
        "10.0.7": _ERC_DEFAULT_WARNING_RULE_KEYS_KICAD_10_0_7,
        "10.0.8": _ERC_DEFAULT_WARNING_RULE_KEYS_KICAD_10_0_7,
    }
)
SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS = frozenset(
    {
        ProjectKind.PCB,
        ProjectKind.SCHEMATIC,
        ProjectKind.SYSTEM_WIRING,
        ProjectKind.HARNESS_INTERFACE,
    }
)


class _ErcMeta(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    version: int | None = None


class _ErcSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    meta: _ErcMeta | None = None
    erc_exclusions: list[JsonValue] | None = None
    rule_severities: dict[str, str] | None = None


class _ProjectSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    erc: _ErcSettings | None = None


@dataclass(frozen=True, slots=True)
class SchematicErcExclusion:
    """One persisted exclusion, retaining a canonical marker and comment."""

    marker: str
    error_type: str
    comment: str


@dataclass(frozen=True, slots=True)
class SchematicErcRuleSeverity:
    """One explicitly configured schematic ERC rule severity."""

    rule_key: str
    severity: str


def configured_schematic_erc_rule_severities(
    document: str,
) -> tuple[SchematicErcRuleSeverity, ...]:
    """Read the supported KiCad 10.0 ERC severity map in stable key order."""
    project = parse_model_text(document, _ProjectSettings)
    if project.erc is None:
        return ()
    settings = project.erc
    if "meta" in settings.model_fields_set and settings.meta is None:
        raise ValueError("ERC severity settings metadata is malformed")
    if "rule_severities" in settings.model_fields_set and settings.rule_severities is None:
        raise ValueError("ERC rule severity map must be an object")
    schema_version = settings.meta.version if settings.meta is not None else 0
    if schema_version != SUPPORTED_ERC_EXCLUSION_SCHEMA_VERSION:
        raise ValueError(f"ERC severity settings schema version is not supported: {schema_version}")
    severities = settings.rule_severities or {}
    supported_severities = {"error", "warning", "ignore"}
    records: list[SchematicErcRuleSeverity] = []
    for rule_key, severity in sorted(severities.items()):
        if not rule_key.strip():
            raise ValueError("ERC rule severity key must not be empty")
        if severity not in supported_severities:
            raise ValueError(f"ERC rule severity for {rule_key!r} is not supported: {severity!r}")
        records.append(SchematicErcRuleSeverity(rule_key, severity))
    return tuple(records)


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
