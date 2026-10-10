"""Deterministic, source-bound RF module antenna and placement-keepout checks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import TypeVar

from .models import (
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbFootprintPlacementObservation,
    PcbRuleAreaPolygonObservation,
)
from .pcb_rf_antenna_models import (
    PcbRfModuleAntennaCoverageEntry,
    PcbRfModuleAntennaMap,
    PcbRfModuleAntennaRequirement,
)

_PI = Decimal("3.141592653589793238462643383279502884197169399375105820974944592307816406286")
_MICRODEGREES_PER_TURN = 360_000_000
_DECIMAL_EPSILON = Decimal("1e-68")

_Key = TypeVar("_Key", bound=str)
_Value = TypeVar("_Value")


def _casefold_matches(mapping: Mapping[_Key, _Value], key: str) -> tuple[tuple[_Key, _Value], ...]:
    folded = key.casefold()
    return tuple((name, value) for name, value in mapping.items() if name.casefold() == folded)


def _canonical_ring(ring: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    """Ignore starting vertex and winding when comparing a polygon contour."""
    if len(ring) < 3 or len(set(ring)) < 3:
        raise ValueError("RF antenna keepout contour needs three distinct vertices")
    forward = tuple(ring)
    reverse = tuple(reversed(ring))
    return min(
        candidate[index:] + candidate[:index]
        for candidate in (forward, reverse)
        for index in range(len(candidate))
    )


def _canonical_polygon_values(
    polygons: tuple[PcbRuleAreaPolygonObservation, ...],
) -> tuple[tuple[tuple[tuple[int, int], ...], tuple[tuple[tuple[int, int], ...], ...]], ...]:
    return tuple(
        sorted(
            (
                _canonical_ring(polygon.outline_nm),
                tuple(sorted(_canonical_ring(hole) for hole in polygon.holes_nm)),
            )
            for polygon in polygons
        )
    )


def _geometry_digest(polygons: tuple[PcbRuleAreaPolygonObservation, ...]) -> str:
    canonical = _canonical_polygon_values(polygons)
    encoded = json.dumps(canonical, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _sine_cosine_microdegrees(angle_microdegrees: int) -> tuple[Decimal, Decimal]:
    """Compute stable trigonometric values without platform libm rounding drift."""
    normalized = angle_microdegrees % _MICRODEGREES_PER_TURN
    if normalized > _MICRODEGREES_PER_TURN // 2:
        normalized -= _MICRODEGREES_PER_TURN
    with localcontext() as context:
        context.prec = 76
        radians = Decimal(normalized) * _PI / Decimal(180_000_000)
        square = radians * radians
        sine = sine_term = radians
        cosine = cosine_term = Decimal(1)
        for index in range(1, 100):
            sine_term *= -square / Decimal((2 * index) * (2 * index + 1))
            cosine_term *= -square / Decimal((2 * index - 1) * (2 * index))
            sine += sine_term
            cosine += cosine_term
            if abs(sine_term) < _DECIMAL_EPSILON and abs(cosine_term) < _DECIMAL_EPSILON:
                break
        return +sine, +cosine


def _round_nm(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_HALF_UP))


def _transform_point(
    point: tuple[int, int], placement: PcbFootprintPlacementObservation
) -> tuple[int, int]:
    sine, cosine = _sine_cosine_microdegrees(placement.orientation_microdegrees)
    with localcontext() as context:
        context.prec = 76
        local_x = Decimal(point[0])
        local_y = Decimal(-point[1] if placement.side == "B.Cu" else point[1])
        origin_x = Decimal(placement.position_nm[0])
        origin_y = Decimal(placement.position_nm[1])
        board_x = origin_x + cosine * local_x + sine * local_y
        board_y = origin_y - sine * local_x + cosine * local_y
        return _round_nm(board_x), _round_nm(board_y)


def _transform_polygons(
    requirement: PcbRfModuleAntennaRequirement,
    placement: PcbFootprintPlacementObservation,
) -> tuple[PcbRuleAreaPolygonObservation, ...]:
    assert requirement.keepout is not None
    transformed = tuple(
        PcbRuleAreaPolygonObservation(
            outline_nm=_canonical_ring(
                tuple(_transform_point(point, placement) for point in polygon.outline_nm)
            ),
            holes_nm=tuple(
                sorted(
                    _canonical_ring(tuple(_transform_point(point, placement) for point in hole))
                    for hole in polygon.holes_nm
                )
            ),
        )
        for polygon in requirement.keepout.local_polygons
    )
    return tuple(sorted(transformed, key=lambda polygon: (polygon.outline_nm, polygon.holes_nm)))


def _source_nets_for_pin(netlist: NetlistContract, pin: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                name
                for name, pins in netlist.nets.items()
                if any(candidate.casefold() == pin.casefold() for candidate in pins)
            ),
            key=lambda item: (item.casefold(), item),
        )
    )


def _mapped_value(mapping: Mapping[_Key, _Value], key: str) -> tuple[_Value, ...]:
    return tuple(value for _, value in _casefold_matches(mapping, key))


def _append_keepout_issues(
    requirement: PcbRfModuleAntennaRequirement,
    snapshot: PcbConnectivitySnapshot,
    placement: PcbFootprintPlacementObservation | None,
    *,
    issues: list[str],
) -> tuple[
    tuple[str, ...],
    str | None,
    str | None,
    tuple[str, ...],
    tuple[bool | None, bool | None, bool | None, bool | None, bool | None],
]:
    keepout = requirement.keepout
    if keepout is None:
        return (), None, None, (), (None, None, None, None, None)
    if snapshot.schema_version != "12" or "footprints" not in snapshot.model_fields_set:
        issues.append("native footprint-placement evidence requires PCB snapshot schema 12")
        return (), None, None, (), (None, None, None, None, None)
    if placement is None:
        issues.append("native PCB footprint placement is missing for the mapped RF module")
        return (), None, None, (), (None, None, None, None, None)
    try:
        expected_polygons = _transform_polygons(requirement, placement)
        expected_digest = _geometry_digest(expected_polygons)
    except (ValueError, ArithmeticError) as exc:
        issues.append(f"could not transform the authored antenna keepout: {exc}")
        return (), None, None, (), (None, None, None, None, None)
    areas = tuple(item for item in snapshot.rule_areas if item.name == keepout.name)
    if not areas:
        issues.append("named native antenna keepout is missing")
        return (), expected_digest, None, (), (None, None, None, None, None)
    if len(areas) != 1:
        issues.append("named native antenna keepout is ambiguous because it is duplicated")
    area = min(areas, key=lambda item: item.uuid.casefold())
    observed_digest = _geometry_digest(area.polygons)
    observed_layers = tuple(sorted(area.layers, key=lambda item: (item.casefold(), item)))
    if observed_digest != expected_digest:
        issues.append(
            "native antenna keepout geometry does not match the transformed local outline"
        )
    if {item.casefold() for item in area.layers} != {item.casefold() for item in keepout.layers}:
        issues.append("native antenna keepout copper layers differ from the project requirement")
    expected_flags = (
        keepout.forbids_tracks,
        keepout.forbids_vias,
        keepout.forbids_pads,
        keepout.forbids_zone_fills,
        keepout.forbids_footprints,
    )
    observed_flags = (
        area.forbids_tracks,
        area.forbids_vias,
        area.forbids_pads,
        area.forbids_zone_fills,
        area.forbids_footprints,
    )
    if expected_flags != observed_flags:
        issues.append("native antenna keepout restrictions differ from the project requirement")
    return (area.uuid,), expected_digest, observed_digest, observed_layers, observed_flags


def pcb_rf_module_antenna_entries(
    authored: PcbRfModuleAntennaMap,
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbRfModuleAntennaCoverageEntry, ...]:
    """Compare project-authored RF intent with schematic and native board evidence."""
    entries: list[PcbRfModuleAntennaCoverageEntry] = []
    for requirement in sorted(
        authored.requirements,
        key=lambda item: (item.id.casefold(), item.id),
    ):
        issues: list[str] = []
        expected_dnp = requirement.disposition == "dnp"

        component_matches = _casefold_matches(netlist.components, requirement.reference)
        component = component_matches[0][1] if len(component_matches) == 1 else None
        if not component_matches:
            issues.append("mapped RF module is absent from the native schematic netlist")
        elif len(component_matches) > 1:
            issues.append("mapped RF module reference is ambiguous in the native schematic netlist")
        symbol_values = _mapped_value(netlist.component_symbols, requirement.reference)
        observed_symbol = str(symbol_values[0]) if len(symbol_values) == 1 else None
        if len(symbol_values) != 1:
            issues.append("native schematic symbol identity is missing or ambiguous")
        elif observed_symbol != requirement.expected_symbol:
            issues.append("native schematic symbol differs from the project RF module identity")
        observed_schematic_footprint = getattr(component, "footprint", None)
        observed_part_id = getattr(component, "part_id", None)
        if component is not None and observed_schematic_footprint != requirement.expected_footprint:
            issues.append("native schematic footprint differs from the project RF module identity")
        if (
            component is not None
            and requirement.expected_part_id is not None
            and observed_part_id != requirement.expected_part_id
        ):
            issues.append("native schematic part ID differs from the project RF module identity")
        schematic_dnp = (
            any(
                item.casefold() == requirement.reference.casefold()
                for item in netlist.dnp_components
            )
            if component is not None
            else None
        )
        if schematic_dnp is not None and schematic_dnp != expected_dnp:
            issues.append(
                "schematic fitted/DNP state differs from the explicit antenna disposition"
            )

        footprint_matches = tuple(
            item
            for item in snapshot.footprints
            if item.reference.casefold() == requirement.reference.casefold()
        )
        placement = footprint_matches[0] if len(footprint_matches) == 1 else None
        if not footprint_matches:
            issues.append("native PCB footprint placement is missing for the mapped RF module")
        elif len(footprint_matches) > 1:
            issues.append("native PCB footprint placement is ambiguous for the mapped RF module")
        observed_board_footprint = None if placement is None else placement.footprint
        board_dnp = None if placement is None else placement.dnp
        if placement is not None and placement.footprint != requirement.expected_footprint:
            issues.append("native PCB footprint differs from the project RF module identity")
        if board_dnp is not None and board_dnp != expected_dnp:
            issues.append(
                "native PCB fitted/DNP state differs from the explicit antenna disposition"
            )

        observed_schematic_rf_feed_nets: tuple[str, ...] = ()
        observed_board_rf_feed_net: str | None = None
        if requirement.rf_feed_pad is not None and requirement.rf_feed_net is not None:
            observed_schematic_rf_feed_nets = _source_nets_for_pin(netlist, requirement.rf_feed_pad)
            if observed_schematic_rf_feed_nets != (requirement.rf_feed_net,):
                issues.append("schematic RF feed pad is missing or assigned to a different net")
            pad_matches = tuple(
                item
                for item in snapshot.pads
                if item.pad.casefold() == requirement.rf_feed_pad.casefold()
            )
            if len(pad_matches) != 1:
                issues.append("native PCB RF feed pad is missing or ambiguous")
            else:
                pad = pad_matches[0]
                observed_board_rf_feed_net = pad.net
                if pad.net != requirement.rf_feed_net:
                    issues.append("native PCB RF feed pad is assigned to a different net")
                if pad.footprint != requirement.expected_footprint:
                    issues.append("native PCB RF feed pad footprint differs from the mapped module")
                if pad.dnp != expected_dnp:
                    issues.append(
                        "native PCB RF feed pad fitted/DNP state differs from disposition"
                    )

        (
            observed_keepout_uuids,
            expected_geometry_sha256,
            observed_geometry_sha256,
            observed_layers,
            observed_flags,
        ) = _append_keepout_issues(requirement, snapshot, placement, issues=issues)
        keepout = requirement.keepout
        entry = PcbRfModuleAntennaCoverageEntry(
            id=requirement.id,
            basis=requirement.basis,
            reference=requirement.reference,
            disposition=requirement.disposition,
            expected_symbol=requirement.expected_symbol,
            observed_symbol=observed_symbol,
            expected_footprint=requirement.expected_footprint,
            observed_schematic_footprint=observed_schematic_footprint,
            observed_board_footprint=observed_board_footprint,
            expected_part_id=requirement.expected_part_id,
            observed_part_id=observed_part_id,
            expected_dnp=expected_dnp,
            observed_schematic_dnp=schematic_dnp,
            observed_board_dnp=board_dnp,
            rf_feed_pad=requirement.rf_feed_pad,
            expected_rf_feed_net=requirement.rf_feed_net,
            observed_schematic_rf_feed_nets=observed_schematic_rf_feed_nets,
            observed_board_rf_feed_net=observed_board_rf_feed_net,
            expected_keepout_name=None if keepout is None else keepout.name,
            observed_keepout_uuids=observed_keepout_uuids,
            expected_geometry_sha256=expected_geometry_sha256,
            observed_geometry_sha256=observed_geometry_sha256,
            expected_layers=() if keepout is None else keepout.layers,
            observed_layers=observed_layers,
            expected_forbids_tracks=None if keepout is None else keepout.forbids_tracks,
            expected_forbids_vias=None if keepout is None else keepout.forbids_vias,
            expected_forbids_pads=None if keepout is None else keepout.forbids_pads,
            expected_forbids_zone_fills=None if keepout is None else keepout.forbids_zone_fills,
            expected_forbids_footprints=None if keepout is None else keepout.forbids_footprints,
            observed_forbids_tracks=observed_flags[0],
            observed_forbids_vias=observed_flags[1],
            observed_forbids_pads=observed_flags[2],
            observed_forbids_zone_fills=observed_flags[3],
            observed_forbids_footprints=observed_flags[4],
            status="INCOMPLETE" if issues else "COMPLETE",
            issues=tuple(dict.fromkeys(issues)),
        )
        entries.append(entry)
    return tuple(entries)
