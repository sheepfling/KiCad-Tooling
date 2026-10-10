"""Coordinate deterministic schematic geometry checks for one sheet."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace

from .model_inventory import _atoms  # pyright: ignore[reportPrivateUsage]
from .schematic_geometry_source import (
    schematic_library_symbols,
    schematic_nodes,
    schematic_root,
    source_tree_sha256,
)
from .schematic_geometry_types import (
    PIN_GEOMETRY_RULE_IDS,
    SUPPORTED_KICAD_VERSIONS,
    SUPPORTED_SCHEMATIC_VERSION,
    SYMBOL_BODY_RULE_IDS,
    WIRE_GEOMETRY_RULE_IDS,
    SchematicGeometryScan,
    SchematicPin,
    SchematicSourceBinding,
    SymbolBodyEnvelope,
    all_rules_unsupported,
)
from .schematic_obstruction_geometry import (
    free_text_over_symbol_bodies,
    free_text_wire_overlaps,
    wire_through_symbol_bodies,
)
from .schematic_pin_geometry import unconnected_pin_wire_near_misses
from .schematic_symbol_geometry import pins_for_instance, symbol_body_envelope_for_instance
from .schematic_text_geometry import coincident_text_anchors, free_text_overlaps
from .schematic_wire_geometry import (
    junction_points,
    label_anchors,
    labels_near_wire_endpoints,
    no_connect_points,
    unmarked_orthogonal_crossings,
    unmarked_t_junctions,
    wire_geometry,
)


def scan_unconnected_pin_wire_geometry(
    source: bytes,
    *,
    source_path: str,
    kicad_version: str,
    unconnected_pins: frozenset[str],
    sheet_instance_path: str = "/",
    reference_overrides: Mapping[str, str] | None = None,
    require_reference_overrides: bool = False,
    allow_hierarchical_sheets: bool = False,
) -> SchematicGeometryScan:
    """Find bounded wire/pin near misses using native-unconnected pin evidence.

    This is a prototype for a review hint. It requires the native netlist's
    explicit unconnected pin set. It identifies either a wire endpoint on the
    interior of a pin segment or a pin tip on the interior of a wire segment.
    It refuses unvalidated KiCad versions and schematic format versions.
    Hierarchical sheets are rejected unless a tree scanner has already bound
    and will scan every sheet instance.
    """
    sha256 = hashlib.sha256(source).hexdigest()
    binding = SchematicSourceBinding(
        source_path=source_path,
        source_sha256=sha256,
        sheet_instance_path=sheet_instance_path,
        sheet_path=(),
    )
    if kicad_version not in SUPPORTED_KICAD_VERSIONS:
        supported_versions = ", ".join(sorted(SUPPORTED_KICAD_VERSIONS))
        issue = f"This prototype is validated only with KiCad {supported_versions}"
        return SchematicGeometryScan(
            status="UNSUPPORTED",
            source_path=source_path,
            source_sha256=sha256,
            kicad_version=kicad_version,
            schematic_version=None,
            source_tree_sha256=source_tree_sha256({source_path: sha256}),
            source_bindings=(binding,),
            unsupported=(issue,),
            unsupported_by_rule=all_rules_unsupported((issue,)),
        )
    text, root = schematic_root(source)
    versions = schematic_nodes(text, root, "version")
    if len(versions) != 1 or len(_atoms(text, versions[0])) != 2:
        raise ValueError("Expected one KiCad schematic version")
    schematic_version = _atoms(text, versions[0])[1]
    if schematic_version != SUPPORTED_SCHEMATIC_VERSION:
        issue = f"Schematic format {schematic_version} is outside this prototype's tested format"
        return SchematicGeometryScan(
            status="UNSUPPORTED",
            source_path=source_path,
            source_sha256=sha256,
            kicad_version=kicad_version,
            schematic_version=schematic_version,
            source_tree_sha256=source_tree_sha256({source_path: sha256}),
            source_bindings=(binding,),
            unsupported=(issue,),
            unsupported_by_rule=all_rules_unsupported((issue,)),
        )
    if schematic_nodes(text, root, "sheet") and not allow_hierarchical_sheets:
        issue = "Hierarchical sheets are outside this single-sheet prototype"
        return SchematicGeometryScan(
            status="UNSUPPORTED",
            source_path=source_path,
            source_sha256=sha256,
            kicad_version=kicad_version,
            schematic_version=schematic_version,
            source_tree_sha256=source_tree_sha256({source_path: sha256}),
            source_bindings=(binding,),
            unsupported=(issue,),
            unsupported_by_rule=all_rules_unsupported((issue,)),
        )

    libraries = schematic_library_symbols(text, root)
    pins: list[SchematicPin] = []
    body_envelopes: list[SymbolBodyEnvelope] = []
    unsupported: list[str] = []
    unsupported_by_rule: dict[str, list[str]] = {}

    def record_unsupported(issues: tuple[str, ...], rule_ids: tuple[str, ...]) -> None:
        if not issues:
            return
        unsupported.extend(issues)
        for rule_id in rule_ids:
            unsupported_by_rule.setdefault(rule_id, []).extend(issues)

    for placed in schematic_nodes(text, root, "symbol"):
        symbol_uuids = schematic_nodes(text, placed, "uuid")
        symbol_uuid = _atoms(text, symbol_uuids[0])[1] if len(symbol_uuids) == 1 else None
        if require_reference_overrides and (
            symbol_uuid is None
            or reference_overrides is None
            or symbol_uuid not in reference_overrides
        ):
            record_unsupported(
                (
                    f"No unique project-instance reference mapping for symbol {symbol_uuid or '<unknown>'}",
                ),
                (*PIN_GEOMETRY_RULE_IDS, *SYMBOL_BODY_RULE_IDS),
            )
            continue
        reference_override = (
            None
            if reference_overrides is None or symbol_uuid is None
            else reference_overrides.get(symbol_uuid)
        )
        instance_pins, issue = pins_for_instance(
            text,
            placed,
            libraries,
            reference_override=reference_override,
        )
        pins.extend(instance_pins)
        if issue is not None:
            record_unsupported((issue,), PIN_GEOMETRY_RULE_IDS)
        body_envelope, body_issue = symbol_body_envelope_for_instance(
            text,
            placed,
            libraries,
            reference_override=reference_override,
        )
        if body_envelope is not None:
            body_envelopes.append(body_envelope)
        if body_issue is not None:
            record_unsupported((body_issue,), SYMBOL_BODY_RULE_IDS)

    wire_ends, wire_segments, wire_issues = wire_geometry(text, root)
    record_unsupported(wire_issues, WIRE_GEOMETRY_RULE_IDS)
    body_wire_findings = wire_through_symbol_bodies(
        tuple(body_envelopes),
        wire_segments,
        sheet_instance_path=sheet_instance_path,
    )
    text_body_findings, text_body_issues = free_text_over_symbol_bodies(
        text,
        root,
        tuple(body_envelopes),
        sheet_instance_path=sheet_instance_path,
    )
    record_unsupported(text_body_issues, ("schematic.free_text_over_symbol_body",))
    junctions, junction_issues = junction_points(text, root)
    record_unsupported(
        junction_issues,
        ("schematic.unmarked_wire_crossing", "schematic.unmarked_t_junction"),
    )
    label_items, label_issues = label_anchors(text, root)
    record_unsupported(label_issues, ("schematic.label_near_wire_endpoint",))
    text_anchor_findings, text_anchor_issues = coincident_text_anchors(text, root)
    record_unsupported(text_anchor_issues, ("schematic.coincident_text_anchors",))
    text_overlap_findings, text_overlap_issues = free_text_overlaps(text, root)
    record_unsupported(text_overlap_issues, ("schematic.free_text_overlap",))
    text_wire_findings, text_wire_issues = free_text_wire_overlaps(
        text,
        root,
        wire_segments,
        sheet_instance_path=sheet_instance_path,
    )
    record_unsupported(text_wire_issues, ("schematic.free_text_over_wire",))
    no_connects = no_connect_points(text, root)
    findings, interior_touches, near_tip_endpoints = unconnected_pin_wire_near_misses(
        pins,
        unconnected_pins,
        no_connects,
        wire_ends,
        wire_segments,
        sheet_instance_path=sheet_instance_path,
    )
    label_findings = tuple(
        replace(item, sheet_instance_path=sheet_instance_path)
        for item in labels_near_wire_endpoints(label_items, pins, wire_ends, wire_segments)
    )
    unmarked_crossings = tuple(
        replace(item, sheet_instance_path=sheet_instance_path)
        for item in unmarked_orthogonal_crossings(wire_segments, junctions)
    )
    t_junction_findings = tuple(
        replace(item, sheet_instance_path=sheet_instance_path)
        for item in unmarked_t_junctions(wire_ends, wire_segments, junctions)
    )
    coincident_text_findings = tuple(
        replace(item, sheet_instance_path=sheet_instance_path) for item in text_anchor_findings
    )
    free_text_overlap_findings = tuple(
        replace(item, sheet_instance_path=sheet_instance_path) for item in text_overlap_findings
    )
    return SchematicGeometryScan(
        status="PARTIAL" if unsupported else "COMPLETE",
        source_path=source_path,
        source_sha256=sha256,
        kicad_version=kicad_version,
        schematic_version=schematic_version,
        source_tree_sha256=source_tree_sha256({source_path: sha256}),
        source_bindings=(binding,),
        findings=findings,
        pin_tip_on_wire_interiors=interior_touches,
        wire_endpoints_near_pin_tips=near_tip_endpoints,
        labels_near_wire_endpoints=label_findings,
        unmarked_wire_crossings=unmarked_crossings,
        unmarked_t_junctions=t_junction_findings,
        coincident_text_anchors=coincident_text_findings,
        free_text_overlaps=free_text_overlap_findings,
        free_text_wire_overlaps=text_wire_findings,
        free_text_symbol_body_overlaps=text_body_findings,
        wires_through_symbol_bodies=body_wire_findings,
        unsupported=tuple(sorted(set(unsupported))),
        unsupported_by_rule={
            rule_id: tuple(sorted(set(issues)))
            for rule_id, issues in sorted(unsupported_by_rule.items())
        },
    )


def scan_wire_ends_on_pin_lines(
    source: bytes,
    *,
    source_path: str,
    kicad_version: str,
    unconnected_pins: frozenset[str],
) -> SchematicGeometryScan:
    """Compatibility alias for the expanded pin/wire geometry scan."""
    return scan_unconnected_pin_wire_geometry(
        source,
        source_path=source_path,
        kicad_version=kicad_version,
        unconnected_pins=unconnected_pins,
    )
