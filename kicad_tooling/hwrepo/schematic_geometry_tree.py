"""Traverse checked KiCad schematic sheets by exact instance path."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Literal

from .schematic_geometry_scan import scan_unconnected_pin_wire_geometry
from .schematic_geometry_source import (
    resolve_schematic_sheet_path,
    schematic_instance_references,
    schematic_root,
    schematic_scalar,
    schematic_sheet_references,
    source_tree_sha256,
)
from .schematic_geometry_types import (
    MAX_SHEET_OCCURRENCES,
    PIN_GEOMETRY_RULE_IDS,
    SUPPORTED_SCHEMATIC_VERSION,
    SYMBOL_BODY_RULE_IDS,
    SchematicGeometryScan,
    SchematicSourceBinding,
)


def scan_schematic_geometry_tree(
    source_files: Mapping[str, bytes],
    *,
    root_path: str,
    project_directory: str,
    project_name: str,
    kicad_version: str,
    unconnected_pins: frozenset[str],
) -> SchematicGeometryScan:
    """Scan every project-local hierarchical sheet instance with exact path refs.

    The caller supplies only the source files it resolved and hash-checked
    against the native verification snapshot. Reused child files are scanned
    once per sheet-instance path so instance-specific component references
    remain distinct in findings.
    """
    if root_path not in source_files:
        raise ValueError(f"Root schematic is absent from the source map: {root_path}")
    occurrences: list[SchematicGeometryScan] = []
    bindings: list[SchematicSourceBinding] = []
    occurrence_paths: set[str] = set()

    def visit(
        source_path: str,
        sheet_instance_path: str,
        sheet_path: tuple[str, ...],
        ancestors: tuple[str, ...],
    ) -> None:
        if source_path in ancestors:
            raise ValueError(f"Recursive schematic sheet reference: {source_path}")
        if len(occurrences) >= MAX_SHEET_OCCURRENCES:
            raise ValueError(f"Schematic hierarchy exceeds {MAX_SHEET_OCCURRENCES} sheet instances")
        source = source_files.get(source_path)
        if source is None:
            raise ValueError(f"Referenced schematic source is missing: {source_path}")
        text, root = schematic_root(source)
        root_uuid = schematic_scalar(text, root, "uuid")
        if not root_uuid:
            raise ValueError(f"Schematic source has an empty UUID: {source_path}")
        if sheet_instance_path in occurrence_paths:
            raise ValueError(f"Duplicate schematic sheet-instance path: {sheet_instance_path}")
        occurrence_paths.add(sheet_instance_path)
        references, reference_issues = schematic_instance_references(
            text,
            root,
            project_name,
            sheet_instance_path,
        )
        scan = scan_unconnected_pin_wire_geometry(
            source,
            source_path=source_path,
            kicad_version=kicad_version,
            unconnected_pins=unconnected_pins,
            sheet_instance_path=sheet_instance_path,
            reference_overrides=references,
            require_reference_overrides=True,
            allow_hierarchical_sheets=True,
        )
        scan_issues = tuple(sorted(set(scan.unsupported) | set(reference_issues)))
        occurrence_issues = tuple(
            f"{source_path} at {sheet_instance_path}: {issue}" for issue in scan_issues
        )
        if occurrence_issues:
            occurrence_issues_by_rule = {
                rule_id: [f"{source_path} at {sheet_instance_path}: {issue}" for issue in issues]
                for rule_id, issues in scan.unsupported_by_rule.items()
            }
            if reference_issues:
                for rule_id in (*PIN_GEOMETRY_RULE_IDS, *SYMBOL_BODY_RULE_IDS):
                    occurrence_issues_by_rule.setdefault(rule_id, []).extend(
                        f"{source_path} at {sheet_instance_path}: {issue}"
                        for issue in reference_issues
                    )
            scan = replace(
                scan,
                status="UNSUPPORTED" if scan.status == "UNSUPPORTED" else "PARTIAL",
                unsupported=occurrence_issues,
                unsupported_by_rule={
                    rule_id: tuple(sorted(set(issues)))
                    for rule_id, issues in sorted(occurrence_issues_by_rule.items())
                },
            )
        occurrences.append(scan)
        bindings.append(
            SchematicSourceBinding(
                source_path=source_path,
                source_sha256=scan.source_sha256,
                sheet_instance_path=sheet_instance_path,
                sheet_path=sheet_path,
            )
        )
        if scan.schematic_version != SUPPORTED_SCHEMATIC_VERSION:
            return
        next_ancestors = (*ancestors, source_path)
        for sheet in schematic_sheet_references(source):
            child_path = resolve_schematic_sheet_path(
                source_path,
                project_directory,
                sheet.file,
            )
            child_instance_path = f"{sheet_instance_path}/{sheet.uuid}"
            visit(
                child_path,
                child_instance_path,
                (*sheet_path, sheet.name),
                next_ancestors,
            )

    root_source = source_files[root_path]
    root_text, root_node = schematic_root(root_source)
    root_uuid = schematic_scalar(root_text, root_node, "uuid")
    root_instance_path = f"/{root_uuid}"
    visit(root_path, root_instance_path, (), ())

    unique_sources = {binding.source_path: binding.source_sha256 for binding in bindings}

    statuses = {scan.status for scan in occurrences}
    status: Literal["COMPLETE", "PARTIAL", "UNSUPPORTED"] = (
        "COMPLETE"
        if statuses == {"COMPLETE"}
        else "UNSUPPORTED"
        if statuses == {"UNSUPPORTED"}
        else "PARTIAL"
    )
    root_scan = occurrences[0]
    unsupported = tuple(sorted({issue for scan in occurrences for issue in scan.unsupported}))
    unsupported_by_rule: dict[str, set[str]] = {}
    for occurrence in occurrences:
        for rule_id, issues in occurrence.unsupported_by_rule.items():
            unsupported_by_rule.setdefault(rule_id, set()).update(issues)
    return SchematicGeometryScan(
        status=status,
        source_path=root_path,
        source_sha256=root_scan.source_sha256,
        kicad_version=kicad_version,
        schematic_version=root_scan.schematic_version,
        findings=tuple(
            sorted(
                (item for scan in occurrences for item in scan.findings),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.reference,
                    item.pin_number,
                    item.wire_uuid,
                ),
            )
        ),
        pin_tip_on_wire_interiors=tuple(
            sorted(
                (item for scan in occurrences for item in scan.pin_tip_on_wire_interiors),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.reference,
                    item.pin_number,
                    item.wire_uuid,
                ),
            )
        ),
        wire_endpoints_near_pin_tips=tuple(
            sorted(
                (item for scan in occurrences for item in scan.wire_endpoints_near_pin_tips),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.reference,
                    item.pin_number,
                    item.distance_to_pin_tip_mm,
                    item.wire_uuid,
                ),
            )
        ),
        labels_near_wire_endpoints=tuple(
            sorted(
                (item for scan in occurrences for item in scan.labels_near_wire_endpoints),
                key=lambda item: (item.sheet_instance_path, item.label_kind, item.label_uuid),
            )
        ),
        unmarked_wire_crossings=tuple(
            sorted(
                (item for scan in occurrences for item in scan.unmarked_wire_crossings),
                key=lambda item: (item.sheet_instance_path, item.crossing_mm, item.wire_uuids),
            )
        ),
        unmarked_t_junctions=tuple(
            sorted(
                (item for scan in occurrences for item in scan.unmarked_t_junctions),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.junction_mm,
                    item.endpoint_wire_uuid,
                    item.interior_wire_uuid,
                ),
            )
        ),
        coincident_text_anchors=tuple(
            sorted(
                (item for scan in occurrences for item in scan.coincident_text_anchors),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.anchor_mm,
                    item.first_uuid,
                    item.second_uuid,
                ),
            )
        ),
        free_text_overlaps=tuple(
            sorted(
                (item for scan in occurrences for item in scan.free_text_overlaps),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.overlap_box_mm,
                    item.first_uuid,
                    item.second_uuid,
                ),
            )
        ),
        free_text_wire_overlaps=tuple(
            sorted(
                (item for scan in occurrences for item in scan.free_text_wire_overlaps),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.text_uuid,
                    item.wire_uuid,
                    item.wire_segment_start_mm,
                    item.wire_segment_end_mm,
                ),
            )
        ),
        free_text_symbol_body_overlaps=tuple(
            sorted(
                (item for scan in occurrences for item in scan.free_text_symbol_body_overlaps),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.reference,
                    item.symbol_uuid,
                    item.text_uuid,
                    item.overlap_box_mm,
                ),
            )
        ),
        wires_through_symbol_bodies=tuple(
            sorted(
                (item for scan in occurrences for item in scan.wires_through_symbol_bodies),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.reference,
                    item.symbol_uuid,
                    item.wire_uuid,
                    item.overlap_start_mm,
                ),
            )
        ),
        source_tree_sha256=source_tree_sha256(unique_sources),
        source_bindings=tuple(
            sorted(bindings, key=lambda binding: (binding.sheet_instance_path, binding.source_path))
        ),
        unsupported=unsupported,
        unsupported_by_rule={
            rule_id: tuple(sorted(issues))
            for rule_id, issues in sorted(unsupported_by_rule.items())
        },
    )
