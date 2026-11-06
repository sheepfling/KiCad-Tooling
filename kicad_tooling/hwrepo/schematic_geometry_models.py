"""Typed schematic-geometry rule IDs and source-bound coverage reports."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, TypeAlias

from pydantic import Field, field_serializer, model_validator

from .model_primitives import (
    Digest,
    NonEmptyText,
    NonNegativeCount,
    RepositoryPath,
    StrictModel,
)
from .source_state_models import SourceHashInventory

SchematicGeometryRuleId = Literal[
    "schematic.wire_end_on_pin_line",
    "schematic.pin_tip_on_wire_interior",
    "schematic.wire_endpoint_near_pin_tip",
    "schematic.label_near_wire_endpoint",
    "schematic.unmarked_wire_crossing",
    "schematic.unmarked_t_junction",
    "schematic.coincident_text_anchors",
    "schematic.free_text_overlap",
    "schematic.free_text_over_wire",
    "schematic.free_text_over_symbol_body",
    "schematic.wire_through_symbol_body",
]
SchematicGeometryRuleCoverageStatus = Literal["DISABLED", "COMPLETE", "PARTIAL", "UNSUPPORTED"]
SchematicInstanceReferenceIndex: TypeAlias = Mapping[NonEmptyText, NonEmptyText]


def _empty_rule_modes() -> dict[SchematicGeometryRuleId, Literal["review", "block", "off"]]:
    return {}


def _empty_rule_coverage() -> dict[SchematicGeometryRuleId, SchematicGeometryRuleCoverageStatus]:
    return {}


def _empty_unsupported_by_rule() -> dict[SchematicGeometryRuleId, tuple[NonEmptyText, ...]]:
    return {}


class SchematicGeometrySourceBinding(StrictModel):
    """One source file bound to a concrete schematic hierarchy occurrence."""

    source_path: RepositoryPath
    source_sha256: Digest
    sheet_instance_path: NonEmptyText
    sheet_path: tuple[NonEmptyText, ...] = ()


class SchematicSourceFile(StrictModel):
    """One schematic payload retained with the digest that admitted its bytes."""

    source_path: RepositoryPath
    source_sha256: Digest
    contents: bytes

    @model_validator(mode="after")
    def digest_matches_contents(self) -> SchematicSourceFile:
        if hashlib.sha256(self.contents).hexdigest() != self.source_sha256:
            raise ValueError("Schematic source digest does not match its retained bytes")
        return self


class SchematicInstanceReferenceResolution(StrictModel):
    """Instance-specific symbol references and parse issues bound to source context."""

    source_path: RepositoryPath
    source_sha256: Digest
    project_name: NonEmptyText
    sheet_instance_path: NonEmptyText
    references_by_symbol_uuid: SchematicInstanceReferenceIndex
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def make_reference_index_read_only(self) -> SchematicInstanceReferenceResolution:
        object.__setattr__(
            self,
            "references_by_symbol_uuid",
            MappingProxyType(dict(self.references_by_symbol_uuid)),
        )
        return self

    @field_serializer("references_by_symbol_uuid")
    def serialize_reference_index(
        self,
        references_by_symbol_uuid: SchematicInstanceReferenceIndex,
    ) -> dict[str, str]:
        return dict(references_by_symbol_uuid)


class VerifiedSchematicSourceTree(StrictModel):
    """Hash-verified schematic files plus the project context used to resolve sheets."""

    root_path: RepositoryPath
    project_directory: RepositoryPath
    source_files: tuple[SchematicSourceFile, ...]

    @model_validator(mode="after")
    def unique_sources_include_root(self) -> VerifiedSchematicSourceTree:
        paths = tuple(item.source_path for item in self.source_files)
        if len(paths) != len(set(paths)):
            raise ValueError("Verified schematic source paths must be unique")
        if self.root_path not in paths:
            raise ValueError("Verified schematic source tree must include its root file")
        return self

    @property
    def source_files_by_path(self) -> Mapping[RepositoryPath, SchematicSourceFile]:
        return MappingProxyType({item.source_path: item for item in self.source_files})

    @property
    def source_contents_by_path(self) -> Mapping[RepositoryPath, bytes]:
        return MappingProxyType({item.source_path: item.contents for item in self.source_files})

    @property
    def source_hashes(self) -> SourceHashInventory:
        return MappingProxyType(
            {item.source_path: item.source_sha256 for item in self.source_files}
        )


class SchematicGeometryCoverage(StrictModel):
    """Opt-in geometry-check coverage bound to schematic and native netlist bytes."""

    status: Literal[
        "NOT_REQUESTED", "DISABLED", "COMPLETE", "PARTIAL", "UNSUPPORTED", "BLOCKED"
    ] = "NOT_REQUESTED"
    mode: Literal["review", "block", "off"] | None = None
    rule_modes: Mapping[SchematicGeometryRuleId, Literal["review", "block", "off"]] = Field(
        default_factory=_empty_rule_modes
    )
    rule_coverage: Mapping[SchematicGeometryRuleId, SchematicGeometryRuleCoverageStatus] = Field(
        default_factory=_empty_rule_coverage
    )
    unsupported_by_rule: Mapping[SchematicGeometryRuleId, tuple[NonEmptyText, ...]] = Field(
        default_factory=_empty_unsupported_by_rule
    )
    source_path: RepositoryPath | None = None
    source_sha256: Digest | None = None
    source_tree_sha256: Digest | None = None
    source_bindings: tuple[SchematicGeometrySourceBinding, ...] = ()
    netlist_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    schematic_version: NonEmptyText | None = None
    finding_count: NonNegativeCount = 0
    unsupported: tuple[NonEmptyText, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> SchematicGeometryCoverage:
        if self.status in {"COMPLETE", "PARTIAL", "UNSUPPORTED"} and (
            self.source_path is None
            or self.source_sha256 is None
            or self.source_tree_sha256 is None
            or not self.source_bindings
            or self.netlist_sha256 is None
            or self.kicad_version is None
        ):
            raise ValueError(
                "Scanned schematic geometry must bind its source tree, instance paths, "
                "and native netlist evidence"
            )
        if self.status in {"COMPLETE", "PARTIAL", "UNSUPPORTED"}:
            instance_paths = tuple(item.sheet_instance_path for item in self.source_bindings)
            if len(instance_paths) != len(set(instance_paths)):
                raise ValueError(
                    "Schematic geometry source bindings must have unique instance paths"
                )
            if not any(
                item.source_path == self.source_path and item.source_sha256 == self.source_sha256
                for item in self.source_bindings
            ):
                raise ValueError("Schematic geometry bindings must include the root source")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked schematic geometry coverage must explain the evidence gap")
        return self
