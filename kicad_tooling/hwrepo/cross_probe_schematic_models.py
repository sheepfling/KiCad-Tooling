"""Source-bound records for schematic cross-probe anchors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, TypeAlias

from .findings_view_models import ReviewDrawing
from .model_primitives import Digest, FiniteMeasure, NonEmptyText, RepositoryPath
from .source_state_models import SourceHashInventory


@dataclass(frozen=True, slots=True)
class SchematicSymbolAnchor:
    """One exact symbol location within a source file and sheet occurrence."""

    reference: NonEmptyText
    source_path: RepositoryPath
    sheet_instance_path: NonEmptyText
    sheet_path: tuple[NonEmptyText, ...]
    symbol_uuid: NonEmptyText
    x_mm: FiniteMeasure
    y_mm: FiniteMeasure


SchematicSymbolAnchorIndex: TypeAlias = Mapping[NonEmptyText, tuple[SchematicSymbolAnchor, ...]]
SchematicDrawingBindingIndex: TypeAlias = Mapping[NonEmptyText, ReviewDrawing]


@dataclass(frozen=True, slots=True)
class SchematicSymbolAnchorResolution:
    """Instance anchors, issues, and the exact schematic source inventory used."""

    root_path: RepositoryPath
    project_directory: RepositoryPath
    project_name: NonEmptyText
    status: Literal["COMPLETE", "PARTIAL", "BLOCKED"]
    source_tree_sha256: Digest | None
    source_hashes: SourceHashInventory
    anchors_by_casefolded_reference: SchematicSymbolAnchorIndex
    issues: tuple[NonEmptyText, ...]

    def __post_init__(self) -> None:
        source_hashes = MappingProxyType(dict(self.source_hashes))
        anchors = MappingProxyType(
            {
                reference: tuple(items)
                for reference, items in self.anchors_by_casefolded_reference.items()
            }
        )
        issues = tuple(self.issues)
        if self.root_path not in source_hashes:
            if (
                self.status != "BLOCKED"
                or source_hashes
                or anchors
                or not issues
                or self.source_tree_sha256 is not None
            ):
                raise ValueError("Missing root schematic requires blocked empty anchor evidence")
        else:
            expected_status = "PARTIAL" if issues else "COMPLETE"
            if (
                self.status != expected_status
                or self.source_tree_sha256 is None
                or self.root_path not in source_hashes
            ):
                raise ValueError("Schematic anchor status must match its source-bound issues")
            for reference, items in anchors.items():
                if not reference or reference != reference.casefold() or not items:
                    raise ValueError(
                        "Schematic anchor indexes require case-folded non-empty entries"
                    )
                if any(
                    item.reference.casefold() != reference or item.source_path not in source_hashes
                    for item in items
                ):
                    raise ValueError("Schematic anchors must match their source inventory keys")
        object.__setattr__(self, "source_hashes", source_hashes)
        object.__setattr__(self, "anchors_by_casefolded_reference", anchors)
        object.__setattr__(self, "issues", issues)


@dataclass(frozen=True, slots=True)
class SchematicDrawingBindingResolution:
    """Source identities and exact drawing records used by schematic binding."""

    root_source: RepositoryPath
    legacy_root_instance: NonEmptyText | None
    source_hashes: SourceHashInventory
    source_inventory_sha256: Digest
    source_drawings: tuple[ReviewDrawing, ...]
    status: Literal["NOT_REQUESTED", "COMPLETE", "PARTIAL"]
    drawings_by_instance: SchematicDrawingBindingIndex
    issues: tuple[NonEmptyText, ...]

    def __post_init__(self) -> None:
        source_hashes = MappingProxyType(dict(self.source_hashes))
        source_drawings = tuple(self.source_drawings)
        drawings_by_instance = MappingProxyType(dict(self.drawings_by_instance))
        issues = tuple(self.issues)
        if any(drawing.kind != "schematic" for drawing in source_drawings):
            raise ValueError("Schematic drawing resolution may retain only schematic drawings")
        if any(drawing not in source_drawings for drawing in drawings_by_instance.values()):
            raise ValueError("Bound drawings must be retained in the source drawing records")
        for instance_path, drawing in drawings_by_instance.items():
            if not instance_path:
                raise ValueError("Schematic drawing bindings require non-empty instance paths")
            if drawing.sheet_instance_path is None:
                if (
                    instance_path != self.legacy_root_instance
                    or self.root_source not in source_hashes
                ):
                    raise ValueError("Legacy root drawing binding requires its root source")
            elif (
                drawing.sheet_instance_path != instance_path
                or drawing.schematic_source is None
                or drawing.schematic_source_sha256 is None
                or source_hashes.get(drawing.schematic_source) != drawing.schematic_source_sha256
            ):
                raise ValueError("Instance drawing bindings require matching source identities")
        expected_status = (
            "NOT_REQUESTED"
            if not source_drawings
            else "COMPLETE"
            if len(drawings_by_instance) == len(source_drawings) and not issues
            else "PARTIAL"
        )
        if self.status != expected_status:
            raise ValueError("Schematic drawing binding status must match its retained evidence")
        object.__setattr__(self, "source_hashes", source_hashes)
        object.__setattr__(self, "source_drawings", source_drawings)
        object.__setattr__(self, "drawings_by_instance", drawings_by_instance)
        object.__setattr__(self, "issues", issues)
