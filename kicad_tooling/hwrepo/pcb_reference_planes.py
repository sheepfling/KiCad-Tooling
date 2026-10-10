"""Deterministic centerline coverage review against adjacent native copper planes."""

from __future__ import annotations

from fractions import Fraction
from itertools import pairwise
from math import isqrt

from .models import (
    PcbConnectivitySnapshot,
    PcbViaObservation,
    PcbZoneFilledIslandObservation,
)
from .pcb_reference_plane_models import (
    PcbReferencePlaneCoverageEntry,
    PcbReferencePlaneMap,
    PcbReferencePlaneTrackMeasurement,
)

Point = tuple[int, int]
RationalPoint = tuple[Fraction, Fraction]
Ring = tuple[Point, ...]


def _cross(first: Point, second: Point) -> int:
    return first[0] * second[1] - first[1] * second[0]


def _point_on_segment(point: RationalPoint, first: Point, second: Point) -> bool:
    px, py = point
    dx, dy = second[0] - first[0], second[1] - first[1]
    qx, qy = px - first[0], py - first[1]
    if dx * qy - dy * qx != 0:
        return False
    return min(first[0], second[0]) <= px <= max(first[0], second[0]) and min(
        first[1], second[1]
    ) <= py <= max(first[1], second[1])


def _ring_contains(point: RationalPoint, ring: Ring) -> bool:
    """Use an exact even-odd test; a ring boundary is considered contained."""
    inside = False
    for index, first in enumerate(ring):
        second = ring[(index + 1) % len(ring)]
        if _point_on_segment(point, first, second):
            return True
        py = point[1]
        if (first[1] > py) == (second[1] > py):
            continue
        crossing_x = Fraction(first[0]) + (py - first[1]) * Fraction(
            second[0] - first[0], second[1] - first[1]
        )
        if crossing_x > point[0]:
            inside = not inside
    return inside


def _island_contains(point: RationalPoint, island: PcbZoneFilledIslandObservation) -> bool:
    outline = tuple(island.outline_nm)
    if not _ring_contains(point, outline):
        return False
    return not any(_ring_contains(point, tuple(hole)) for hole in island.holes_nm)


def _segment_edge_parameters(
    start: Point, end: Point, first: Point, second: Point
) -> tuple[Fraction, ...]:
    """Return exact route parameters where one segment meets a polygon edge."""
    route = (end[0] - start[0], end[1] - start[1])
    edge = (second[0] - first[0], second[1] - first[1])
    offset = (first[0] - start[0], first[1] - start[1])
    denominator = _cross(route, edge)
    if denominator:
        along_route = Fraction(_cross(offset, edge), denominator)
        along_edge = Fraction(_cross(offset, route), denominator)
        if 0 <= along_route <= 1 and 0 <= along_edge <= 1:
            return (along_route,)
        return ()
    if _cross(offset, route):
        return ()

    axis = 0 if abs(route[0]) >= abs(route[1]) else 1
    first_parameter = Fraction(first[axis] - start[axis], route[axis])
    second_parameter = Fraction(second[axis] - start[axis], route[axis])
    low = max(Fraction(0), min(first_parameter, second_parameter))
    high = min(Fraction(1), max(first_parameter, second_parameter))
    if low > high:
        return ()
    return (low, high)


def _covered_fraction(
    start: Point,
    end: Point,
    islands: tuple[PcbZoneFilledIslandObservation, ...],
) -> Fraction:
    """Measure the share of one straight track centerline inside a union of zones."""
    route = (end[0] - start[0], end[1] - start[1])
    if route == (0, 0):
        return Fraction(0)
    rings = tuple(ring for island in islands for ring in (island.outline_nm, *island.holes_nm))
    boundaries = {Fraction(0), Fraction(1)}
    for ring in rings:
        for index, first in enumerate(ring):
            boundaries.update(
                _segment_edge_parameters(start, end, first, ring[(index + 1) % len(ring)])
            )
    ordered = sorted(boundaries)
    covered = Fraction(0)
    for low, high in pairwise(ordered):
        if low == high:
            continue
        midpoint = (low + high) / 2
        point = (
            Fraction(start[0]) + midpoint * route[0],
            Fraction(start[1]) + midpoint * route[1],
        )
        if any(_island_contains(point, island) for island in islands):
            covered += high - low
    return covered


def _adjacent_layers(copper_layers: tuple[str, ...], signal_layer: str) -> tuple[str, ...]:
    index = next(
        (i for i, layer in enumerate(copper_layers) if layer.casefold() == signal_layer.casefold()),
        None,
    )
    if index is None:
        return ()
    return tuple(
        copper_layers[adjacent]
        for adjacent in (index - 1, index + 1)
        if 0 <= adjacent < len(copper_layers)
    )


def _via_spans_layer(
    via: PcbViaObservation,
    copper_layers: tuple[str, ...],
    target_layer: str,
) -> bool:
    indexes = {layer.casefold(): index for index, layer in enumerate(copper_layers)}
    start = indexes.get(via.start_layer.casefold())
    end = indexes.get(via.end_layer.casefold())
    target = indexes.get(target_layer.casefold())
    if start is None or end is None or target is None:
        return False
    return min(start, end) <= target <= max(start, end)


def pcb_reference_plane_entries(
    specification: PcbReferencePlaneMap,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbReferencePlaneCoverageEntry, ...]:
    """Measure each mapped straight track against each immediately adjacent reference layer."""
    entries: list[PcbReferencePlaneCoverageEntry] = []
    stack = snapshot.copper_layers
    vias_by_id = {item.id.casefold(): item for item in snapshot.vias}
    for requirement in specification.requirements:
        issues: list[str] = []
        measurements: list[PcbReferencePlaneTrackMeasurement] = []
        excluded_short: list[str] = []
        selected_tracks = tuple(
            item
            for item in snapshot.tracks
            if item.net is not None
            and item.net.casefold() == requirement.signal_net.casefold()
            and any(
                item.layer.casefold() == layer.casefold() for layer in requirement.signal_layers
            )
        )
        if not selected_tracks:
            issues.append(
                f"No native track items were observed on {requirement.signal_net} in the mapped layers"
            )

        for layer in requirement.signal_layers:
            if not any(item.casefold() == layer.casefold() for item in stack):
                issues.append(f"Mapped signal layer {layer} is absent from the native copper stack")

        minimum_length_nm = requirement.minimum_track_length_um * 1000
        for track in sorted(selected_tracks, key=lambda item: item.uuid.casefold()):
            dx = track.end_nm[0] - track.start_nm[0]
            dy = track.end_nm[1] - track.start_nm[1]
            length_nm = isqrt(dx * dx + dy * dy)
            if length_nm < minimum_length_nm:
                excluded_short.append(track.uuid)
                continue
            if track.geometry_kind != "segment":
                issues.append(
                    f"Track {track.uuid} uses unsupported {track.geometry_kind or 'unknown'} geometry"
                )
                continue
            neighbors = _adjacent_layers(stack, track.layer)
            if not neighbors:
                issues.append(f"Track {track.uuid} has no observed adjacent copper layer")
                continue
            for reference_layer in neighbors:
                zones = tuple(
                    zone
                    for zone in snapshot.zones
                    if zone.net is not None
                    and zone.net.casefold() == requirement.reference_net.casefold()
                    and zone.layer.casefold() == reference_layer.casefold()
                )
                islands = tuple(island for zone in zones for island in zone.filled_islands)
                fraction = _covered_fraction(track.start_nm, track.end_nm, islands)
                endpoint_via_ids = tuple(
                    sorted(
                        {*track.start_vias, *track.end_vias},
                        key=str.casefold,
                    )
                )
                endpoint_vias_with_hole_centers = tuple(
                    via_id
                    for via_id in endpoint_via_ids
                    if _via_spans_layer(vias_by_id[via_id.casefold()], stack, reference_layer)
                    and any(
                        _ring_contains(
                            (
                                Fraction(vias_by_id[via_id.casefold()].x_nm),
                                Fraction(vias_by_id[via_id.casefold()].y_nm),
                            ),
                            tuple(hole),
                        )
                        for island in islands
                        for hole in island.holes_nm
                    )
                )
                threshold = Fraction(str(requirement.minimum_referenced_fraction))
                measurements.append(
                    PcbReferencePlaneTrackMeasurement(
                        track_uuid=track.uuid,
                        signal_layer=track.layer,
                        reference_layer=reference_layer,
                        reference_zone_uuids=tuple(
                            sorted((zone.uuid for zone in zones), key=str.casefold)
                        ),
                        endpoint_via_ids=endpoint_via_ids,
                        endpoint_via_ids_with_center_in_reference_holes=(
                            endpoint_vias_with_hole_centers
                        ),
                        segment_length_nm=length_nm,
                        covered_fraction_numerator=fraction.numerator,
                        covered_fraction_denominator=fraction.denominator,
                        below_minimum=fraction < threshold,
                    )
                )

        if not measurements and not issues:
            issues.append("No mapped native track met the project-authored minimum segment length")
        if excluded_short and requirement.review_excluded_short_tracks:
            issues.append(
                "One or more mapped native tracks are shorter than the configured minimum and "
                "require review"
            )
        entries.append(
            PcbReferencePlaneCoverageEntry(
                id=requirement.id,
                status="INCOMPLETE" if issues else "COMPLETE",
                basis=requirement.basis,
                signal_net=requirement.signal_net,
                signal_layers=requirement.signal_layers,
                reference_net=requirement.reference_net,
                minimum_track_length_um=requirement.minimum_track_length_um,
                minimum_referenced_fraction=requirement.minimum_referenced_fraction,
                review_excluded_short_tracks=requirement.review_excluded_short_tracks,
                tracks=tuple(measurements),
                excluded_short_track_uuids=tuple(sorted(excluded_short, key=str.casefold)),
                issues=tuple(issues),
            )
        )
    return tuple(entries)
