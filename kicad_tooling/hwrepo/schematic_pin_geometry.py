"""Near-miss checks between native-unconnected pins and schematic wires."""

from __future__ import annotations

import math

from .schematic_geometry_primitives import point_to_segment
from .schematic_geometry_types import (
    DISTANCE_COMPARISON_EPSILON_MM,
    MAX_PIN_ENDPOINT_GAP_MM,
    POINT_TOLERANCE_MM,
    PinTipOnWireInterior,
    SchematicPin,
    WireEnd,
    WireEndOnPinLine,
    WireEndpointNearPinTip,
    WireSegment,
)


def unconnected_pin_wire_near_misses(
    pins: list[SchematicPin],
    unconnected_pins: frozenset[str],
    no_connects: tuple[tuple[float, float], ...],
    wire_ends: tuple[WireEnd, ...],
    wire_segments: tuple[WireSegment, ...],
    *,
    sheet_instance_path: str,
) -> tuple[
    tuple[WireEndOnPinLine, ...],
    tuple[PinTipOnWireInterior, ...],
    tuple[WireEndpointNearPinTip, ...],
]:
    findings: list[WireEndOnPinLine] = []
    interior_touches: list[PinTipOnWireInterior] = []
    near_tip_endpoints: list[WireEndpointNearPinTip] = []
    seen: set[tuple[str, str, str, tuple[float, float]]] = set()
    seen_intersections: set[tuple[str, str, str, tuple[float, float], tuple[float, float]]] = set()
    seen_near_tips: set[tuple[str, str, str, tuple[float, float]]] = set()
    for pin in pins:
        pin_key = f"{pin.reference}.{pin.number}"
        if pin_key not in unconnected_pins:
            continue
        if any(math.dist(pin.tip, marker) <= POINT_TOLERANCE_MM for marker in no_connects):
            continue
        for wire_end in wire_ends:
            distance_to_tip = math.dist(pin.tip, wire_end.point)
            if (
                POINT_TOLERANCE_MM
                < distance_to_tip
                <= MAX_PIN_ENDPOINT_GAP_MM + DISTANCE_COMPARISON_EPSILON_MM
            ):
                measurement = point_to_segment(wire_end.point, pin.tip, pin.body_end)
                on_pin_segment = measurement is not None and measurement[0] <= POINT_TOLERANCE_MM
                if not on_pin_segment:
                    key = (wire_end.uuid, pin.reference, pin.number, wire_end.point)
                    if key not in seen_near_tips:
                        seen_near_tips.add(key)
                        near_tip_endpoints.append(
                            WireEndpointNearPinTip(
                                reference=pin.reference,
                                symbol_library_id=pin.library_id,
                                symbol_uuid=pin.symbol_uuid,
                                pin_number=pin.number,
                                pin_name=pin.name,
                                pin_uuid=pin.pin_uuid,
                                pin_tip_mm=pin.tip,
                                wire_uuid=wire_end.uuid,
                                wire_endpoint_mm=wire_end.point,
                                distance_to_pin_tip_mm=round(distance_to_tip, 6),
                                sheet_instance_path=sheet_instance_path,
                            )
                        )
            measurement = point_to_segment(wire_end.point, pin.tip, pin.body_end)
            if measurement is None:
                continue
            distance, along, _length = measurement
            distance_to_tip = math.dist(wire_end.point, pin.tip)
            if distance > POINT_TOLERANCE_MM or distance_to_tip <= POINT_TOLERANCE_MM:
                continue
            key = (wire_end.uuid, pin.reference, pin.number, wire_end.point)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                WireEndOnPinLine(
                    reference=pin.reference,
                    symbol_library_id=pin.library_id,
                    symbol_uuid=pin.symbol_uuid,
                    pin_number=pin.number,
                    pin_name=pin.name,
                    pin_uuid=pin.pin_uuid,
                    pin_tip_mm=pin.tip,
                    pin_body_end_mm=pin.body_end,
                    wire_uuid=wire_end.uuid,
                    wire_endpoint_mm=wire_end.point,
                    distance_to_pin_tip_mm=round(distance_to_tip, 6),
                    distance_along_pin_mm=round(along, 6),
                    sheet_instance_path=sheet_instance_path,
                )
            )
        for segment in wire_segments:
            measurement = point_to_segment(pin.tip, segment.start, segment.end)
            if measurement is None:
                continue
            distance, along, length = measurement
            if (
                distance > POINT_TOLERANCE_MM
                or along <= POINT_TOLERANCE_MM
                or length - along <= POINT_TOLERANCE_MM
            ):
                continue
            key = (
                segment.uuid,
                pin.reference,
                pin.number,
                segment.start,
                segment.end,
            )
            if key in seen_intersections:
                continue
            seen_intersections.add(key)
            interior_touches.append(
                PinTipOnWireInterior(
                    reference=pin.reference,
                    symbol_library_id=pin.library_id,
                    symbol_uuid=pin.symbol_uuid,
                    pin_number=pin.number,
                    pin_name=pin.name,
                    pin_uuid=pin.pin_uuid,
                    pin_tip_mm=pin.tip,
                    wire_uuid=segment.uuid,
                    wire_segment_start_mm=segment.start,
                    wire_segment_end_mm=segment.end,
                    distance_to_wire_mm=round(distance, 6),
                    sheet_instance_path=sheet_instance_path,
                )
            )
    findings.sort(key=lambda item: (item.reference, item.pin_number, item.wire_uuid))
    interior_touches.sort(key=lambda item: (item.reference, item.pin_number, item.wire_uuid))
    near_tip_endpoints.sort(
        key=lambda item: (
            item.reference,
            item.pin_number,
            item.distance_to_pin_tip_mm,
            item.wire_uuid,
        )
    )
    return tuple(findings), tuple(interior_touches), tuple(near_tip_endpoints)
