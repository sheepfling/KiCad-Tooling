"""Candidate translation for source-bound schematic geometry findings."""

from __future__ import annotations

from .design_lint_schematic_geometry_candidate_evidence import (
    LabelNearWireEndpointSource,
    PinTipOnWireInteriorSource,
    SchematicLabelEndpointCandidate,
    SchematicPinGeometryCandidate,
    SchematicWireTopologyCandidate,
    UnmarkedTJunctionSource,
    UnmarkedWireCrossingSource,
    WireEndOnPinLineSource,
    WireEndpointNearPinTipSource,
)
from .design_lint_schematic_symbol_body_candidate_evidence import (
    FreeTextSymbolBodyOverlapSource,
    SchematicSymbolBodyObstructionCandidate,
    WireThroughSymbolBodySource,
)
from .design_lint_schematic_text_candidate_evidence import (
    CoincidentTextAnchorsSource,
    FreeTextOverlapSource,
    FreeTextWireOverlapSource,
    SchematicTextGeometryCandidate,
)
from .design_lint_types import Candidate
from .schematic_geometry import SchematicGeometryScan


def schematic_geometry_candidates(scan: SchematicGeometryScan) -> tuple[Candidate, ...]:
    """Translate each supported geometry observation into its review candidate."""
    found: list[Candidate] = []
    for item in scan.findings:
        found.append(
            SchematicPinGeometryCandidate.from_source_evidence(WireEndOnPinLineSource(scan, item))
        )
    for item in scan.pin_tip_on_wire_interiors:
        found.append(
            SchematicPinGeometryCandidate.from_source_evidence(
                PinTipOnWireInteriorSource(scan, item)
            )
        )
    for item in scan.wire_endpoints_near_pin_tips:
        found.append(
            SchematicPinGeometryCandidate.from_source_evidence(
                WireEndpointNearPinTipSource(scan, item)
            )
        )
    for item in scan.labels_near_wire_endpoints:
        found.append(
            SchematicLabelEndpointCandidate.from_source_evidence(
                LabelNearWireEndpointSource(scan, item)
            )
        )
    for item in scan.unmarked_wire_crossings:
        found.append(
            SchematicWireTopologyCandidate.from_source_evidence(
                UnmarkedWireCrossingSource(scan, item)
            )
        )
    for item in scan.unmarked_t_junctions:
        found.append(
            SchematicWireTopologyCandidate.from_source_evidence(UnmarkedTJunctionSource(scan, item))
        )
    for item in scan.coincident_text_anchors:
        found.append(
            SchematicTextGeometryCandidate.from_source_evidence(
                CoincidentTextAnchorsSource(scan, item)
            )
        )
    for item in scan.free_text_overlaps:
        found.append(
            SchematicTextGeometryCandidate.from_source_evidence(FreeTextOverlapSource(scan, item))
        )
    for item in scan.free_text_wire_overlaps:
        found.append(
            SchematicTextGeometryCandidate.from_source_evidence(
                FreeTextWireOverlapSource(scan, item)
            )
        )
    for item in scan.free_text_symbol_body_overlaps:
        found.append(
            SchematicSymbolBodyObstructionCandidate.from_source_evidence(
                FreeTextSymbolBodyOverlapSource(scan, item)
            )
        )
    for item in scan.wires_through_symbol_bodies:
        found.append(
            SchematicSymbolBodyObstructionCandidate.from_source_evidence(
                WireThroughSymbolBodySource(scan, item)
            )
        )
    return tuple(found)
