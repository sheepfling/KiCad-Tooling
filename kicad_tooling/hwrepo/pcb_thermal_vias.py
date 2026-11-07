"""Deterministic coverage for explicitly mapped PCB thermal-pad via screens."""

from __future__ import annotations

from collections import Counter

from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_thermal_via_models import (
    PcbThermalViaCoverageEntry,
    PcbThermalViaMap,
    PcbThermalViaMeasurement,
    PcbThermalViaRequirement,
)


def _layer_span(start_layer: str, end_layer: str) -> frozenset[str]:
    return frozenset((start_layer.casefold(), end_layer.casefold()))


def _entry(
    requirement: PcbThermalViaRequirement,
    snapshot: PcbConnectivitySnapshot,
) -> PcbThermalViaCoverageEntry:
    issues: list[str] = []
    pad = next(
        (item for item in snapshot.pads if item.pad.casefold() == requirement.pad.casefold()),
        None,
    )
    if pad is None:
        return PcbThermalViaCoverageEntry(
            id=requirement.id,
            status="INCOMPLETE",
            basis=requirement.basis,
            pad=requirement.pad,
            expected_footprint=requirement.footprint,
            observed_footprint=None,
            expected_net=requirement.net,
            observed_net=None,
            fitted=False,
            maximum_center_distance_um=requirement.maximum_center_distance_um,
            required_layer_spans=requirement.required_layer_spans,
            measurements=(),
            issues=(
                f"Mapped thermal pad {requirement.pad} is absent from the native PCB inventory",
            ),
        )

    if pad.footprint.casefold() != requirement.footprint.casefold():
        issues.append(
            f"{requirement.pad} footprint {pad.footprint!r} does not match mapped footprint "
            f"{requirement.footprint!r}"
        )
    if pad.net is None or pad.net.casefold() != requirement.net.casefold():
        issues.append(f"{requirement.pad} is not assigned to mapped net {requirement.net!r}")
    if pad.dnp:
        issues.append(f"{requirement.pad} belongs to a DNP footprint")
    if not pad.positions_nm:
        issues.append(f"{requirement.pad} has no native pad-center geometry")

    copper_layers = {item.casefold() for item in snapshot.copper_layers}
    for span in requirement.required_layer_spans:
        if (
            span.start_layer.casefold() not in copper_layers
            or span.end_layer.casefold() not in copper_layers
        ):
            issues.append(
                f"Required via span {span.start_layer} to {span.end_layer} is absent from the "
                "native copper stack"
            )

    max_radius_nm = requirement.maximum_center_distance_um * 1000
    max_radius_squared_nm2 = max_radius_nm * max_radius_nm
    connected_ids = set(pad.connected_vias)
    measurements: list[PcbThermalViaMeasurement] = []
    matching_counts: Counter[frozenset[str]] = Counter()
    for via in snapshot.vias:
        if via.net is None or via.net.casefold() != requirement.net.casefold():
            continue
        if pad.positions_nm:
            distance_squared_nm2 = min(
                (via.x_nm - x_nm) ** 2 + (via.y_nm - y_nm) ** 2 for x_nm, y_nm in pad.positions_nm
            )
        else:
            continue
        within_radius = distance_squared_nm2 <= max_radius_squared_nm2
        connected = via.id in connected_ids
        if not within_radius and not connected:
            continue
        measurement = PcbThermalViaMeasurement(
            via_id=via.id,
            net=via.net,
            start_layer=via.start_layer,
            end_layer=via.end_layer,
            multiplicity=via.multiplicity,
            center_distance_squared_nm2=distance_squared_nm2,
            within_authored_radius=within_radius,
            connected_to_pad_component=connected,
        )
        measurements.append(measurement)
        if connected and within_radius:
            matching_counts[_layer_span(via.start_layer, via.end_layer)] += via.multiplicity

    for span in requirement.required_layer_spans:
        observed = matching_counts[_layer_span(span.start_layer, span.end_layer)]
        if observed < span.minimum_vias:
            issues.append(
                f"{requirement.pad} has {observed} native-connected vias within "
                f"{requirement.maximum_center_distance_um} um for span {span.start_layer} to "
                f"{span.end_layer}; {span.minimum_vias} required"
            )

    return PcbThermalViaCoverageEntry(
        id=requirement.id,
        status="INCOMPLETE" if issues else "COMPLETE",
        basis=requirement.basis,
        pad=requirement.pad,
        expected_footprint=requirement.footprint,
        observed_footprint=pad.footprint,
        expected_net=requirement.net,
        observed_net=pad.net,
        fitted=not pad.dnp,
        maximum_center_distance_um=requirement.maximum_center_distance_um,
        required_layer_spans=requirement.required_layer_spans,
        measurements=tuple(sorted(measurements, key=lambda item: item.via_id)),
        issues=tuple(issues),
    )


def pcb_thermal_via_entries(
    requirements: PcbThermalViaMap,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbThermalViaCoverageEntry, ...]:
    """Count only native-connected vias on exact authored layer spans and within radius."""
    return tuple(_entry(item, snapshot) for item in requirements.requirements)
