"""Reconcile parts populations with source-bound cross-probe locations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from .cross_probe_board import (
    BoardFootprintAnchorsByCasefoldedReference,
    CrossProbeBoardMarkerResolution,
)
from .cross_probe_models import CrossProbeEntry, CrossProbeLocation
from .cross_probe_schematic_models import (
    SchematicDrawingBindingResolution,
    SchematicSymbolAnchor,
    SchematicSymbolAnchorResolution,
)
from .cross_probe_variant import VariantObservation
from .findings_view_models import ReviewDrawing
from .model_primitives import RepositoryPath
from .purchasing_models import PurchasingComponent
from .source_state_models import SourceHashInventory

SchematicAnchorsByCasefoldedReference = Mapping[str, tuple[SchematicSymbolAnchor, ...]]
SchematicDrawingsByInstancePath = Mapping[str, ReviewDrawing]
CrossProbeEntryOrigin = Literal["PARTS_PLAN", "VARIANT_NATIVE"]


@dataclass(frozen=True, slots=True)
class CrossProbeLocationEvidence:
    """Indexes derived from the current source inventory and admitted drawings."""

    source_hashes: SourceHashInventory
    board_marker_resolution: CrossProbeBoardMarkerResolution
    schematic_anchor_resolution: SchematicSymbolAnchorResolution
    schematic_drawing_resolution: SchematicDrawingBindingResolution

    def __post_init__(self) -> None:
        """Snapshot the indexes and reject locations without current source IDs."""
        source_hashes = MappingProxyType(dict(self.source_hashes))
        board_source_sha256 = self.board_marker_resolution.board_source_sha256
        if board_source_sha256 is None:
            if self.board_marker_resolution.board_path in source_hashes:
                raise ValueError("Blocked PCB anchors cannot have a current board source hash")
        elif source_hashes.get(self.board_marker_resolution.board_path) != board_source_sha256:
            raise ValueError("PCB anchors require a matching current board source hash")
        if any(
            source_hashes.get(path) != source_sha256
            for path, source_sha256 in self.schematic_anchor_resolution.source_hashes.items()
        ):
            raise ValueError("Schematic anchors require matching current source hashes")
        if any(
            source_hashes.get(path) != source_sha256
            for path, source_sha256 in self.schematic_drawing_resolution.source_hashes.items()
        ):
            raise ValueError("Schematic drawings require matching current source hashes")
        if (
            self.schematic_anchor_resolution.status == "BLOCKED"
            and self.schematic_anchor_resolution.root_path in source_hashes
        ):
            raise ValueError("Available root schematic cannot have blocked anchor evidence")
        if any(
            anchor.source_path not in source_hashes
            for anchors in self.schematic_anchor_resolution.anchors_by_casefolded_reference.values()
            for anchor in anchors
        ):
            raise ValueError("Schematic anchors require current source hashes")
        object.__setattr__(self, "source_hashes", source_hashes)

    @property
    def board_path(self) -> RepositoryPath:
        """Expose the PCB source path while retaining its resolved evidence."""
        return self.board_marker_resolution.board_path

    @property
    def board_anchors(self) -> BoardFootprintAnchorsByCasefoldedReference:
        """Expose the immutable PCB index after source-identity validation."""
        return self.board_marker_resolution.anchors_by_casefolded_reference

    @property
    def board_drawing(self) -> ReviewDrawing | None:
        """Expose the unique PCB drawing only when one retained candidate exists."""
        return self.board_marker_resolution.board_drawing

    @property
    def schematic_drawings(self) -> SchematicDrawingsByInstancePath:
        """Expose bound drawings while retaining their source-bound resolution."""
        return self.schematic_drawing_resolution.drawings_by_instance

    @property
    def schematic_anchors(self) -> SchematicAnchorsByCasefoldedReference:
        """Expose the immutable index while retaining its source-bound resolution."""
        return self.schematic_anchor_resolution.anchors_by_casefolded_reference


@dataclass(frozen=True, slots=True)
class CrossProbePopulationInput:
    """Admitted parts, optional variant components, and matching location evidence."""

    parts_components: tuple[PurchasingComponent, ...]
    variant_components: tuple[PurchasingComponent, ...]
    locations: CrossProbeLocationEvidence
    variant: VariantObservation | None

    def __post_init__(self) -> None:
        """Keep component sequences stable and require evidence for variant rows."""
        object.__setattr__(self, "parts_components", tuple(self.parts_components))
        object.__setattr__(self, "variant_components", tuple(self.variant_components))
        if self.variant is None and self.variant_components:
            raise ValueError("Variant components require an admitted variant observation")


@dataclass(frozen=True, slots=True)
class CrossProbePopulationResult:
    """Reconciled entries and variant-board references with no parts counterpart."""

    entries: tuple[CrossProbeEntry, ...]
    board_only: tuple[str, ...]


def build_cross_probe_entry(
    component: PurchasingComponent,
    *,
    duplicate: bool,
    origin: CrossProbeEntryOrigin,
    locations: CrossProbeLocationEvidence,
) -> CrossProbeEntry:
    """Project one admitted component through the source-bound location indexes."""
    excluded = component.dnp or component.exclude_from_bom
    population = (
        "DUPLICATE"
        if duplicate
        else "DNP"
        if component.dnp
        else "EXCLUDED"
        if component.exclude_from_bom
        else "FITTED"
    )
    if duplicate:
        return CrossProbeEntry(
            reference=component.reference,
            origin=origin,
            part_id=component.part_id,
            value=component.value,
            footprint=component.footprint,
            population=population,
            issues=("Duplicate case-insensitive parts reference; no unique location assigned.",),
        )
    if excluded:
        return CrossProbeEntry(
            reference=component.reference,
            origin=origin,
            part_id=component.part_id,
            value=component.value,
            footprint=component.footprint,
            population=population,
            issues=("DNP or excluded component; no fitted placement asserted.",),
        )
    key = component.reference.casefold()
    issues: list[str] = []
    board: list[CrossProbeLocation] = []
    placed = locations.board_anchors.get(key, ())
    if len(placed) > 1:
        issues.append("PCB has duplicate reference placements; no board location assigned.")
    elif not placed:
        issues.append("No matching PCB footprint placement.")
    else:
        item = placed[0]
        if item.issue or item.x_mm is None or item.y_mm is None or item.side is None:
            issues.append(item.issue or "PCB position is unsupported.")
        else:
            if component.footprint and component.footprint != item.footprint:
                issues.append(
                    "Assigned and placed footprint identities differ; inspect both sources."
                )
            board_drawing = locations.board_drawing
            drawing_file = (
                board_drawing.file
                if board_drawing is not None
                and board_drawing.mapping_supported
                and item.side == "F.Cu"
                and 0 <= item.x_mm <= board_drawing.width_mm
                and 0 <= item.y_mm <= board_drawing.height_mm
                else None
            )
            if drawing_file is None:
                issues.append("PCB source position has no supported front-board drawing marker.")
            board.append(
                CrossProbeLocation(
                    kind="pcb",
                    source_path=locations.board_path,
                    x_mm=item.x_mm,
                    y_mm=item.y_mm,
                    side=item.side,
                    drawing_file=drawing_file,
                )
            )
    schematic: list[CrossProbeLocation] = []
    symbols = locations.schematic_anchors.get(key, ())
    if not symbols:
        issues.append("No uniquely instance-mapped schematic symbol location.")
    for symbol in symbols:
        schematic_drawing = locations.schematic_drawings.get(symbol.sheet_instance_path)
        drawing_file = (
            schematic_drawing.file
            if schematic_drawing is not None
            and schematic_drawing.mapping_supported
            and (
                schematic_drawing.schematic_source is None
                or schematic_drawing.schematic_source == symbol.source_path
            )
            and 0 <= symbol.x_mm <= schematic_drawing.width_mm
            and 0 <= symbol.y_mm <= schematic_drawing.height_mm
            else None
        )
        if drawing_file is None:
            issues.append(
                "Schematic symbol has a source coordinate without a supported SVG marker."
            )
        schematic.append(
            CrossProbeLocation(
                kind="schematic",
                source_path=symbol.source_path,
                x_mm=symbol.x_mm,
                y_mm=symbol.y_mm,
                drawing_file=drawing_file,
                sheet_instance_path=symbol.sheet_instance_path,
                sheet_path=symbol.sheet_path,
                symbol_uuid=symbol.symbol_uuid,
            )
        )
    return CrossProbeEntry(
        reference=component.reference,
        origin=origin,
        part_id=component.part_id,
        value=component.value,
        footprint=component.footprint,
        population=population,
        board=tuple(board),
        schematic=tuple(schematic),
        issues=tuple(dict.fromkeys(issues)),
    )


def reconcile_cross_probe_population(
    request: CrossProbePopulationInput,
) -> CrossProbePopulationResult:
    """Join parts rows with variant populations without losing their source origin."""
    parts_keys = {item.reference.casefold() for item in request.parts_components}
    variant_only = (
        tuple(
            item
            for item in request.variant_components
            if item.reference.casefold() not in parts_keys
        )
        if request.variant is not None
        else ()
    )
    components = (*request.parts_components, *variant_only)
    counts = Counter(item.reference.casefold() for item in components)
    entries = tuple(
        build_cross_probe_entry(
            component,
            duplicate=counts[component.reference.casefold()] > 1,
            origin=(
                "PARTS_PLAN" if component.reference.casefold() in parts_keys else "VARIANT_NATIVE"
            ),
            locations=request.locations,
        )
        for component in components
    )
    variant = request.variant
    if variant is None:
        return CrossProbePopulationResult(entries=entries, board_only=())

    observed_entries: list[CrossProbeEntry] = []
    for entry, component in zip(entries, components, strict=True):
        key = entry.reference.casefold()
        native_component = variant.schematic.get(key)
        schematic_population = (
            "ABSENT"
            if native_component is None
            else "DNP"
            if key in variant.schematic_dnp
            else "FITTED"
        )
        board_population = (
            "FITTED"
            if key in variant.board_fitted
            else "DNP"
            if key in variant.board_all
            else "ABSENT"
        )
        located = entry
        if (
            entry.population in {"DNP", "EXCLUDED"}
            and board_population == "FITTED"
            and counts[key] == 1
        ):
            located = build_cross_probe_entry(
                component.model_copy(update={"dnp": False, "exclude_from_bom": False}),
                duplicate=False,
                origin=entry.origin,
                locations=request.locations,
            )
        row_issues = list(located.issues)
        if entry.origin == "VARIANT_NATIVE":
            row_issues.append("Reference comes from the selected variant, not the parts receipt.")
        board = located.board
        if board_population != "FITTED" and board:
            board = ()
            row_issues.append("Selected variant does not have a fitted PCB position.")
        if entry.origin == "PARTS_PLAN":
            if entry.population == "FITTED" and board_population != "FITTED":
                row_issues.append("Parts-plan fitted state differs from selected PCB variant.")
            elif entry.population in {"DNP", "EXCLUDED"} and board_population == "FITTED":
                row_issues.append("Selected PCB variant fits a parts-plan excluded reference.")
        if schematic_population == "DNP" and board_population == "FITTED":
            row_issues.append("Selected variant schematic and PCB population differ.")
        if schematic_population == "ABSENT" and board_population == "FITTED":
            row_issues.append(
                "Selected variant PCB reference is absent from its schematic netlist."
            )
        if (
            native_component is not None
            and entry.population != "DUPLICATE"
            and entry.origin == "PARTS_PLAN"
        ):
            if entry.part_id != native_component.part_id:
                row_issues.append("Parts-plan and selected variant part identities differ.")
            if entry.value != native_component.value:
                row_issues.append("Parts-plan and selected variant values differ.")
            if entry.footprint != native_component.footprint:
                row_issues.append("Parts-plan and selected variant footprints differ.")
        observed_entries.append(
            located.model_copy(
                update={
                    "population": entry.population,
                    "origin": entry.origin,
                    "board": board,
                    "variant_schematic": schematic_population,
                    "variant_board": board_population,
                    "variant_part_id": (
                        native_component.part_id if native_component is not None else None
                    ),
                    "variant_value": (
                        native_component.value if native_component is not None else None
                    ),
                    "variant_footprint": (
                        native_component.footprint if native_component is not None else None
                    ),
                    "issues": tuple(row_issues),
                }
            )
        )
    entries = tuple(observed_entries)
    parts_entry_keys = {item.reference.casefold() for item in entries}
    board_only = tuple(
        sorted(ref for key, ref in variant.board_all.items() if key not in parts_entry_keys)
    )
    return CrossProbePopulationResult(entries=entries, board_only=board_only)
