"""Typed schematic-geometry rule IDs and source-bound coverage reports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    NonEmptyText,
    NonNegativeCount,
    RepositoryPath,
    StrictModel,
)

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
