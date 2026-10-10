"""Typed findings and shared constants for schematic geometry checks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

SUPPORTED_KICAD_VERSION = "10.0.6"


SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.5", "10.0.6"})


SUPPORTED_SCHEMATIC_VERSION = "20231120"


POINT_TOLERANCE_MM = 0.001


MAX_LABEL_ENDPOINT_GAP_MM = 1.27


MAX_PIN_ENDPOINT_GAP_MM = 0.5


DISTANCE_COMPARISON_EPSILON_MM = 1e-9


MAX_SHEET_OCCURRENCES = 1024


SCHEMATIC_GEOMETRY_RULE_IDS = (
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
)


PIN_GEOMETRY_RULE_IDS = SCHEMATIC_GEOMETRY_RULE_IDS[:3]


SYMBOL_BODY_RULE_IDS = (
    "schematic.free_text_over_symbol_body",
    "schematic.wire_through_symbol_body",
)


WIRE_GEOMETRY_RULE_IDS = (
    *PIN_GEOMETRY_RULE_IDS,
    "schematic.label_near_wire_endpoint",
    "schematic.unmarked_wire_crossing",
    "schematic.unmarked_t_junction",
    "schematic.free_text_over_wire",
    "schematic.wire_through_symbol_body",
)


SUBSYMBOL_UNIT = re.compile(r"_(\d+)_(\d+)\Z")


TEXT_MARKUP = re.compile(r"[~_^]\{[^{}]*\}")


TEXT_OVERLAP_GUARD_MM = 0.08


TEXT_OVERLAP_MIN_AREA_MM2 = 0.05


TEXT_WIRE_GUARD_MM = 0.12


TEXT_WIRE_MIN_OVERLAP_MM = 0.2


TEXT_WIRE_LENGTH_EPSILON_MM = 1e-9


SYMBOL_BODY_WIRE_GUARD_MM = 0.2


SYMBOL_BODY_WIRE_MIN_OVERLAP_MM = 0.3


SYMBOL_BODY_WIRE_LENGTH_EPSILON_MM = 1e-9


TEXT_BODY_TEXT_GUARD_MM = 0.1


TEXT_BODY_SYMBOL_GUARD_MM = 0.15


TEXT_BODY_MIN_OVERLAP_AREA_MM2 = 0.1


TEXT_BODY_AREA_EPSILON_MM2 = 1e-9


LABEL_KINDS: tuple[Literal["label", "global_label", "hierarchical_label"], ...] = (
    "label",
    "global_label",
    "hierarchical_label",
)


@dataclass(frozen=True)
class WireEndOnPinLine:
    """A native-unconnected pin whose tip-to-body line meets a wire endpoint."""

    reference: str
    symbol_library_id: str
    symbol_uuid: str
    pin_number: str
    pin_name: str
    pin_uuid: str | None
    pin_tip_mm: tuple[float, float]
    pin_body_end_mm: tuple[float, float]
    wire_uuid: str
    wire_endpoint_mm: tuple[float, float]
    distance_to_pin_tip_mm: float
    distance_along_pin_mm: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class PinTipOnWireInterior:
    """A native-unconnected pin tip intersects the interior of a wire segment."""

    reference: str
    symbol_library_id: str
    symbol_uuid: str
    pin_number: str
    pin_name: str
    pin_uuid: str | None
    pin_tip_mm: tuple[float, float]
    wire_uuid: str
    wire_segment_start_mm: tuple[float, float]
    wire_segment_end_mm: tuple[float, float]
    distance_to_wire_mm: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class WireEndpointNearPinTip:
    """A wire endpoint close to, but not touching, a native-unconnected pin tip."""

    reference: str
    symbol_library_id: str
    symbol_uuid: str
    pin_number: str
    pin_name: str
    pin_uuid: str | None
    pin_tip_mm: tuple[float, float]
    wire_uuid: str
    wire_endpoint_mm: tuple[float, float]
    distance_to_pin_tip_mm: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class LabelWireEndpointCandidate:
    """A wire endpoint within the review radius of an unattached label."""

    wire_uuid: str
    wire_endpoint_mm: tuple[float, float]
    distance_mm: float


@dataclass(frozen=True)
class LabelNearWireEndpoint:
    """A label anchor that narrowly misses nearby wire-endpoint geometry."""

    label_kind: Literal["label", "global_label", "hierarchical_label"]
    text: str
    label_uuid: str
    anchor_mm: tuple[float, float]
    candidates: tuple[LabelWireEndpointCandidate, ...]
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class UnmarkedWireCrossing:
    """Orthogonal wire interiors intersect without a junction marker."""

    wire_uuids: tuple[str, ...]
    crossing_mm: tuple[float, float]
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class UnmarkedTJunction:
    """A wire endpoint touches another wire's interior without a junction marker."""

    endpoint_wire_uuid: str
    interior_wire_uuid: str
    junction_mm: tuple[float, float]
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class CoincidentTextAnchors:
    """Two free-text insertion anchors occupy the same schematic coordinate."""

    first_text: str
    first_uuid: str
    second_text: str
    second_uuid: str
    anchor_mm: tuple[float, float]
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class FreeTextOverlap:
    """Two distinct free-text anchors have intersecting conservative glyph envelopes."""

    first_text: str
    first_uuid: str
    first_box_mm: tuple[float, float, float, float]
    second_text: str
    second_uuid: str
    second_box_mm: tuple[float, float, float, float]
    overlap_box_mm: tuple[float, float, float, float]
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class FreeTextWireOverlap:
    """A wire segment crosses the guarded envelope of one supported free-text item."""

    text: str
    text_uuid: str
    text_box_mm: tuple[float, float, float, float]
    wire_uuid: str
    wire_segment_start_mm: tuple[float, float]
    wire_segment_end_mm: tuple[float, float]
    overlap_length_mm: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class FreeTextSymbolBodyOverlap:
    """A supported free-text envelope overlaps a symbol-body envelope."""

    text: str
    text_uuid: str
    text_box_mm: tuple[float, float, float, float]
    reference: str
    symbol_library_id: str
    symbol_uuid: str
    body_box_mm: tuple[float, float, float, float]
    overlap_box_mm: tuple[float, float, float, float]
    overlap_area_mm2: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class WireThroughSymbolBody:
    """A native wire segment crosses a guarded symbol-body envelope."""

    reference: str
    symbol_library_id: str
    symbol_uuid: str
    wire_uuid: str
    body_box_mm: tuple[float, float, float, float]
    overlap_start_mm: tuple[float, float]
    overlap_end_mm: tuple[float, float]
    overlap_length_mm: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class SchematicSourceBinding:
    """One source file and instance path covered by a geometry scan."""

    source_path: str
    source_sha256: str
    sheet_instance_path: str
    sheet_path: tuple[str, ...]


@dataclass(frozen=True)
class SchematicSheetReference:
    """A child sheet declared by one schematic source file."""

    uuid: str
    name: str
    file: str


def _empty_unsupported_by_rule() -> dict[str, tuple[str, ...]]:
    return {}


@dataclass(frozen=True)
class SchematicGeometryScan:
    """Version and source binding for this limited read-only geometry pass."""

    status: Literal["COMPLETE", "PARTIAL", "UNSUPPORTED"]
    source_path: str
    source_sha256: str
    kicad_version: str
    schematic_version: str | None
    findings: tuple[WireEndOnPinLine, ...] = ()
    pin_tip_on_wire_interiors: tuple[PinTipOnWireInterior, ...] = ()
    wire_endpoints_near_pin_tips: tuple[WireEndpointNearPinTip, ...] = ()
    labels_near_wire_endpoints: tuple[LabelNearWireEndpoint, ...] = ()
    unmarked_wire_crossings: tuple[UnmarkedWireCrossing, ...] = ()
    unmarked_t_junctions: tuple[UnmarkedTJunction, ...] = ()
    coincident_text_anchors: tuple[CoincidentTextAnchors, ...] = ()
    free_text_overlaps: tuple[FreeTextOverlap, ...] = ()
    free_text_wire_overlaps: tuple[FreeTextWireOverlap, ...] = ()
    free_text_symbol_body_overlaps: tuple[FreeTextSymbolBodyOverlap, ...] = ()
    wires_through_symbol_bodies: tuple[WireThroughSymbolBody, ...] = ()
    source_tree_sha256: str | None = None
    source_bindings: tuple[SchematicSourceBinding, ...] = ()
    unsupported: tuple[str, ...] = ()
    unsupported_by_rule: Mapping[str, tuple[str, ...]] = field(
        default_factory=_empty_unsupported_by_rule
    )


@dataclass(frozen=True)
class SchematicPin:
    reference: str
    library_id: str
    symbol_uuid: str
    number: str
    name: str
    pin_uuid: str | None
    tip: tuple[float, float]
    body_end: tuple[float, float]


@dataclass(frozen=True)
class WireEnd:
    uuid: str
    point: tuple[float, float]


@dataclass(frozen=True)
class WireSegment:
    uuid: str
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True)
class LabelAnchor:
    kind: Literal["label", "global_label", "hierarchical_label"]
    text: str
    uuid: str
    point: tuple[float, float]


@dataclass(frozen=True)
class TextAnchor:
    text: str
    uuid: str
    point: tuple[float, float]


@dataclass(frozen=True)
class SchematicTextMetrics:
    advances_mm: Mapping[str, float]
    reference_size_mm: float
    single_glyph_end_spacing_mm: float
    line_end_spacing_mm: float
    multiline_line_spacing_mm: float
    vertical_top_ratio: float
    vertical_bottom_ratio: float
    stroke_width_mm: float


@dataclass(frozen=True)
class FreeTextGeometry:
    anchor: TextAnchor
    box_mm: tuple[float, float, float, float]


@dataclass(frozen=True)
class SymbolBodyEnvelope:
    reference: str
    library_id: str
    symbol_uuid: str
    box_mm: tuple[float, float, float, float]


def all_rules_unsupported(issues: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    return {rule_id: issues for rule_id in SCHEMATIC_GEOMETRY_RULE_IDS}
