"""Evaluate project-authored PCB probe envelopes against native snapshots."""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal

from .electrical_report_models import ElectricalCheck
from .pcb_connectivity_observations import PcbAccessProbeObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_test_access_models import (
    PcbAccessProbeRequest,
    PcbAccessProbeRequestSet,
    TestAccessAnalysis,
    TestAccessEndpointRequirement,
)


def _probe_radius_nm(tip_diameter_mm: float, clearance_mm: float) -> int:
    """Round the decimal-authored tip radius and clearance upward to nanometers."""
    radius_mm = Decimal(str(tip_diameter_mm)) / 2 + Decimal(str(clearance_mm))
    return int((radius_mm * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def _probe_aperture_diameter_nm(tip_diameter_mm: float, clearance_mm: float) -> int:
    """Round the decimal-authored tip-plus-clearance diameter upward to nanometers."""
    diameter_mm = Decimal(str(tip_diameter_mm)) + 2 * Decimal(str(clearance_mm))
    return int((diameter_mm * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def pcb_access_probe_request_set(
    spec: TestAccessAnalysis,
) -> PcbAccessProbeRequestSet | None:
    """Build the deterministic native requests for configured probe envelopes."""
    requests: list[PcbAccessProbeRequest] = []
    for decision in spec.decisions:
        if decision.mode != "required":
            continue
        for endpoint in decision.endpoints:
            if endpoint.probe_envelope is None:
                continue
            sides = (
                ("front", "back")
                if endpoint.approach_side == "either"
                else (endpoint.approach_side,)
            )
            requests.extend(
                PcbAccessProbeRequest(
                    endpoint=endpoint.pin,
                    net=decision.net,
                    side=side,
                    include_edge_cuts=(
                        True
                        if (
                            endpoint.probe_envelope.board_edge_clearance_mm is not None
                            or endpoint.probe_envelope.drill_hole_clearance_mm is not None
                        )
                        else None
                    ),
                    include_drill_holes=(
                        True
                        if endpoint.probe_envelope.drill_hole_clearance_mm is not None
                        else None
                    ),
                )
                for side in sides
            )
    if not requests:
        return None
    return PcbAccessProbeRequestSet(
        requests=tuple(
            sorted(
                requests,
                key=lambda item: (item.endpoint.casefold(), item.side, item.net.casefold()),
            )
        )
    )


def pcb_probe_envelope_checks(
    spec: TestAccessAnalysis,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[ElectricalCheck, ...]:
    """Check authored probe envelopes against retained native pad and PCB geometry."""
    request_set = pcb_access_probe_request_set(spec)
    if request_set is None:
        return ()
    requires_courtyard = any(
        endpoint.probe_envelope is not None
        and endpoint.probe_envelope.courtyard_clearance_mm is not None
        for decision in spec.decisions
        if decision.mode == "required"
        for endpoint in decision.endpoints
    )
    requires_via = any(
        endpoint.probe_envelope is not None and endpoint.probe_envelope.via_clearance_mm is not None
        for decision in spec.decisions
        if decision.mode == "required"
        for endpoint in decision.endpoints
    )
    requires_track = any(
        endpoint.probe_envelope is not None
        and endpoint.probe_envelope.track_clearance_mm is not None
        for decision in spec.decisions
        if decision.mode == "required"
        for endpoint in decision.endpoints
    )
    requires_zone = any(
        endpoint.probe_envelope is not None
        and endpoint.probe_envelope.zone_clearance_mm is not None
        for decision in spec.decisions
        if decision.mode == "required"
        for endpoint in decision.endpoints
    )
    requires_edge = any(
        endpoint.probe_envelope is not None
        and endpoint.probe_envelope.board_edge_clearance_mm is not None
        for decision in spec.decisions
        if decision.mode == "required"
        for endpoint in decision.endpoints
    )
    requires_drill_hole = any(
        endpoint.probe_envelope is not None
        and endpoint.probe_envelope.drill_hole_clearance_mm is not None
        for decision in spec.decisions
        if decision.mode == "required"
        for endpoint in decision.endpoints
    )
    if requires_courtyard and int(snapshot.schema_version) < 17:
        return (
            ElectricalCheck(
                id="test-access/pcb-probe-envelope/courtyard-evidence",
                status="NOT_RUN",
                detail="Authored courtyard clearance requires native PCB snapshot schema v17 or newer.",
            ),
        )
    if requires_via and int(snapshot.schema_version) < 18:
        return (
            ElectricalCheck(
                id="test-access/pcb-probe-envelope/via-evidence",
                status="NOT_RUN",
                detail="Authored via clearance requires native PCB snapshot schema v18 or newer.",
            ),
        )
    if requires_track and int(snapshot.schema_version) < 19:
        return (
            ElectricalCheck(
                id="test-access/pcb-probe-envelope/track-evidence",
                status="NOT_RUN",
                detail="Authored track clearance requires native PCB snapshot schema v19 or newer.",
            ),
        )
    if requires_zone and int(snapshot.schema_version) < 20:
        return (
            ElectricalCheck(
                id="test-access/pcb-probe-envelope/zone-evidence",
                status="NOT_RUN",
                detail="Authored copper-zone clearance requires native PCB snapshot schema v20 or newer.",
            ),
        )
    if requires_edge and (int(snapshot.schema_version) < 21 or not snapshot.edge_cuts):
        return (
            ElectricalCheck(
                id="test-access/pcb-probe-envelope/edge-evidence",
                status="NOT_RUN",
                detail=(
                    "Authored board-edge clearance requires native PCB schema v21+ "
                    "and an observed Edge.Cuts inventory."
                ),
            ),
        )
    if requires_drill_hole and int(snapshot.schema_version) < 22:
        return (
            ElectricalCheck(
                id="test-access/pcb-probe-envelope/drill-hole-evidence",
                status="NOT_RUN",
                detail=(
                    "Authored drill-hole clearance requires native PCB snapshot schema v22 or newer."
                ),
            ),
        )
    observations = {
        (item.endpoint.casefold(), item.side): item for item in snapshot.access_probe_observations
    }
    expected_keys = {(item.endpoint.casefold(), item.side) for item in request_set.requests}
    if expected_keys != set(observations):
        return (
            ElectricalCheck(
                id="test-access/pcb-probe-envelope/evidence",
                status="FAIL",
                detail="Native probe observations do not exactly cover configured endpoint surfaces.",
            ),
        )

    checks: list[ElectricalCheck] = []
    for decision in spec.decisions:
        if decision.mode != "required":
            continue
        endpoint_results: list[
            tuple[TestAccessEndpointRequirement, bool, bool, tuple[str, ...]]
        ] = []
        for endpoint in decision.endpoints:
            envelope = endpoint.probe_envelope
            if envelope is None:
                continue
            sides = (
                ("front", "back")
                if endpoint.approach_side == "either"
                else (endpoint.approach_side,)
            )
            required_nm = _probe_radius_nm(envelope.tip_diameter_mm, envelope.clearance_mm)
            required_aperture_nm = _probe_aperture_diameter_nm(
                envelope.tip_diameter_mm, envelope.clearance_mm
            )
            required_courtyard_nm = (
                None
                if envelope.courtyard_clearance_mm is None
                else _probe_radius_nm(envelope.tip_diameter_mm, envelope.courtyard_clearance_mm)
            )
            required_via_nm = (
                None
                if envelope.via_clearance_mm is None
                else _probe_radius_nm(envelope.tip_diameter_mm, envelope.via_clearance_mm)
            )
            required_track_nm = (
                None
                if envelope.track_clearance_mm is None
                else _probe_radius_nm(envelope.tip_diameter_mm, envelope.track_clearance_mm)
            )
            required_zone_nm = (
                None
                if envelope.zone_clearance_mm is None
                else _probe_radius_nm(envelope.tip_diameter_mm, envelope.zone_clearance_mm)
            )
            required_board_edge_nm = (
                None
                if envelope.board_edge_clearance_mm is None
                else _probe_radius_nm(envelope.tip_diameter_mm, envelope.board_edge_clearance_mm)
            )
            required_drill_hole_nm = (
                None
                if envelope.drill_hole_clearance_mm is None
                else _probe_radius_nm(envelope.tip_diameter_mm, envelope.drill_hole_clearance_mm)
            )
            side_details: list[str] = []
            endpoint_pass = False
            endpoint_unresolved = False
            for side in sides:
                observation: PcbAccessProbeObservation | None = observations.get(
                    (endpoint.pin.casefold(), side)
                )
                if observation is None:
                    side_details.append(f"{side}: native observation is missing")
                    continue
                if observation.target_net != decision.net:
                    side_details.append(
                        f"{side}: target pad is on {observation.target_net or 'no net'}; "
                        f"expected {decision.net}"
                    )
                    continue
                if not observation.target_exposed:
                    side_details.append(
                        f"{side}: target pad has no exposed copper and mask surface"
                    )
                    continue
                if observation.target_aperture_shape is None:
                    aperture_clear = False
                    side_details.append(f"{side}: target aperture geometry is unavailable")
                elif observation.target_aperture_shape == "unsupported":
                    aperture_clear = False
                    side_details.append(
                        f"{side}: target aperture shape is unsupported for deterministic probe-tip fit"
                    )
                else:
                    assert observation.target_aperture_diameter_nm is not None
                    aperture_clear = observation.target_aperture_diameter_nm >= required_aperture_nm
                    if observation.target_aperture_shape == "circle":
                        aperture_description = "circular target mask aperture is"
                    else:
                        aperture_description = (
                            f"{observation.target_aperture_shape} mask aperture supports "
                            "a centered circular tip diameter of"
                        )
                    side_details.append(
                        f"{side}: {aperture_description} "
                        f"{observation.target_aperture_diameter_nm / 1_000_000:.6g} mm; "
                        f"required tip-plus-clearance diameter is "
                        f"{required_aperture_nm / 1_000_000:.6g} mm"
                    )
                if observation.obstacle is None:
                    neighbor_clear = True
                    side_details.append(
                        f"{side}: no different-net exposed pad was observed; "
                        f"required envelope radius is {required_nm / 1_000_000:.6g} mm"
                    )
                else:
                    assert observation.distance_nm is not None
                    neighbor_clear = observation.distance_nm >= required_nm
                    side_details.append(
                        f"{side}: nearest different-net exposed pad {observation.obstacle} "
                        f"({observation.obstacle_net or 'no net'}) is "
                        f"{observation.distance_nm / 1_000_000:.6g} mm from the pad center; "
                        f"required envelope radius is {required_nm / 1_000_000:.6g} mm"
                    )
                courtyard_clear = True
                courtyard_unresolved = False
                measured_courtyard_failure = False
                if required_courtyard_nm is not None:
                    if (
                        observation.unmeasured_courtyard_footprint is not None
                        and observation.unmeasured_courtyard_distance_nm is not None
                        and observation.unmeasured_courtyard_distance_nm <= required_courtyard_nm
                    ):
                        courtyard_clear = False
                        courtyard_unresolved = True
                        side_details.append(
                            f"{side}: footprint {observation.unmeasured_courtyard_footprint} has no "
                            "same-side courtyard and its native bounding box is within the authored "
                            f"probe envelope ({observation.unmeasured_courtyard_distance_nm / 1_000_000:.6g} mm; "
                            f"required radius {required_courtyard_nm / 1_000_000:.6g} mm)"
                        )
                    if observation.courtyard_obstacle is None:
                        side_details.append(
                            f"{side}: no same-side footprint courtyard was observed within the "
                            "source inventory"
                        )
                    else:
                        assert observation.courtyard_distance_nm is not None
                        measured_courtyard_clear = (
                            observation.courtyard_distance_nm >= required_courtyard_nm
                        )
                        courtyard_clear = courtyard_clear and measured_courtyard_clear
                        measured_courtyard_failure = not measured_courtyard_clear
                        side_details.append(
                            f"{side}: nearest fitted footprint courtyard {observation.courtyard_obstacle} "
                            f"is {observation.courtyard_distance_nm / 1_000_000:.6g} mm from the pad center; "
                            f"required probe radius plus courtyard clearance is "
                            f"{required_courtyard_nm / 1_000_000:.6g} mm"
                        )
                    courtyard_unresolved = courtyard_unresolved and not measured_courtyard_failure
                via_clear = True
                if required_via_nm is not None:
                    if observation.via_obstacle_id is None:
                        side_details.append(
                            f"{side}: no different-net or unconnected untented outer-layer via was observed; "
                            f"required envelope radius is {required_via_nm / 1_000_000:.6g} mm"
                        )
                    else:
                        assert observation.via_obstacle_distance_nm is not None
                        via_clear = observation.via_obstacle_distance_nm >= required_via_nm
                        side_details.append(
                            f"{side}: nearest different-net or unconnected untented via "
                            f"{observation.via_obstacle_id} ({observation.via_obstacle_net or 'no net'}) is "
                            f"{observation.via_obstacle_distance_nm / 1_000_000:.6g} mm from the pad center; "
                            f"required envelope radius is {required_via_nm / 1_000_000:.6g} mm"
                        )
                track_clear = True
                if required_track_nm is not None:
                    if observation.track_obstacle_uuid is None:
                        side_details.append(
                            f"{side}: no different-net or unconnected outer-layer track was observed; "
                            f"required envelope radius is {required_track_nm / 1_000_000:.6g} mm"
                        )
                    else:
                        assert observation.track_obstacle_distance_nm is not None
                        track_clear = observation.track_obstacle_distance_nm >= required_track_nm
                        side_details.append(
                            f"{side}: nearest different-net or unconnected outer-layer "
                            f"{observation.track_obstacle_geometry} {observation.track_obstacle_uuid} "
                            f"({observation.track_obstacle_net or 'no net'}) is "
                            f"{observation.track_obstacle_distance_nm / 1_000_000:.6g} mm from the pad center; "
                            f"required envelope radius is {required_track_nm / 1_000_000:.6g} mm"
                        )
                side_clear = (
                    aperture_clear
                    and neighbor_clear
                    and courtyard_clear
                    and via_clear
                    and track_clear
                )
                zone_clear = True
                if required_zone_nm is not None:
                    if observation.zone_obstacle_uuid is None:
                        side_details.append(
                            f"{side}: no different-net or unconnected filled outer-layer zone was observed; "
                            f"required envelope radius is {required_zone_nm / 1_000_000:.6g} mm"
                        )
                    else:
                        assert observation.zone_obstacle_distance_nm is not None
                        assert observation.zone_obstacle_island_index is not None
                        assert observation.zone_obstacle_layer is not None
                        zone_clear = observation.zone_obstacle_distance_nm >= required_zone_nm
                        side_details.append(
                            f"{side}: nearest different-net or unconnected filled zone "
                            f"{observation.zone_obstacle_uuid} island {observation.zone_obstacle_island_index} "
                            f"on {observation.zone_obstacle_layer} "
                            f"({observation.zone_obstacle_net or 'no net'}) is "
                            f"{observation.zone_obstacle_distance_nm / 1_000_000:.6g} mm from the pad center; "
                            f"required envelope radius is {required_zone_nm / 1_000_000:.6g} mm"
                        )
                side_clear = side_clear and zone_clear
                edge_clear = True
                if required_board_edge_nm is not None:
                    if observation.edge_obstacle_uuid is None:
                        edge_clear = False
                        side_details.append(
                            f"{side}: no native Edge.Cuts obstacle was measured; "
                            f"required probe radius plus board-edge clearance is "
                            f"{required_board_edge_nm / 1_000_000:.6g} mm"
                        )
                    else:
                        assert observation.edge_obstacle_distance_nm is not None
                        edge_clear = observation.edge_obstacle_distance_nm >= required_board_edge_nm
                        side_details.append(
                            f"{side}: nearest native Edge.Cuts item "
                            f"{observation.edge_obstacle_uuid} is "
                            f"{observation.edge_obstacle_distance_nm / 1_000_000:.6g} mm "
                            f"from the pad center; required probe radius plus board-edge "
                            f"clearance is {required_board_edge_nm / 1_000_000:.6g} mm"
                        )
                side_clear = side_clear and edge_clear
                drill_hole_clear = True
                if required_drill_hole_nm is not None:
                    if observation.hole_obstacle_id is None:
                        side_details.append(
                            f"{side}: no fitted surface drill hole was observed; required probe "
                            f"radius plus drill-hole clearance is "
                            f"{required_drill_hole_nm / 1_000_000:.6g} mm"
                        )
                    else:
                        assert observation.hole_obstacle_distance_nm is not None
                        drill_hole_clear = (
                            observation.hole_obstacle_distance_nm >= required_drill_hole_nm
                        )
                        side_details.append(
                            f"{side}: nearest fitted drill hole {observation.hole_obstacle_id} "
                            f"is {observation.hole_obstacle_distance_nm / 1_000_000:.6g} mm "
                            f"from the pad center; required probe radius plus drill-hole "
                            f"clearance is {required_drill_hole_nm / 1_000_000:.6g} mm"
                        )
                side_clear = side_clear and drill_hole_clear
                endpoint_pass = endpoint_pass or side_clear
                endpoint_unresolved = endpoint_unresolved or courtyard_unresolved
            endpoint_results.append(
                (endpoint, endpoint_pass, endpoint_unresolved, tuple(side_details))
            )

        if not endpoint_results:
            continue
        passed = (
            all(item[1] for item in endpoint_results)
            if decision.selection == "all"
            else any(item[1] for item in endpoint_results)
        )
        unresolved = (
            any(item[2] for item in endpoint_results)
            and not passed
            and (
                decision.selection == "any"
                or not any(not item[1] and not item[2] for item in endpoint_results)
            )
        )
        details = tuple(
            f"{endpoint.pin}: {'; '.join(side_details)}"
            for endpoint, _endpoint_pass, _endpoint_unresolved, side_details in endpoint_results
        )
        limitation = (
            "Target fit is measured only for undrilled circle, oval, rectangle, and roundrect pads, "
            "using KiCad mask expansion and the smaller pad dimension as the centered circular-tip fit. "
            "Neighbor clearance checks fitted exposed footprint pads from the target pad center. Optional "
            "courtyard clearance compares same-side fitted footprint courtyard polygons, and uses the nearest "
            "unmeasured footprint bounding box to identify missing nearby courtyards. Optional via clearance "
            "measures only untented vias that span the selected outer copper side; it does not infer exposure "
            "from arbitrary mask graphics. Optional track and filled-zone clearances measure outer-layer copper "
            "regardless of solder-mask exposure, so they do not classify custom mask openings. Optional board-edge "
            "clearance measures individual native Edge.Cuts shapes but does not validate outline closure or distinguish "
            "the outer perimeter from internal cutouts. The checks do not establish "
            "body height, probe angle, fixture or cover access, "
            "or physical reach; zone apertures, "
            "custom/chamfered/trapezoid target shapes, and footprints on the opposite board side are not evaluated."
        )
        checks.append(
            ElectricalCheck(
                id=f"test-access/pcb-probe-envelope/{decision.id}",
                status="PASS" if passed else "NOT_RUN" if unresolved else "FAIL",
                detail=(" ".join(details) + " " + limitation),
            )
        )
    return tuple(checks)
