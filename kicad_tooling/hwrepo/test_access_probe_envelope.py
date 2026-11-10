"""Evaluate project-authored PCB probe envelopes against native snapshots."""

from __future__ import annotations

from math import ceil

from .electrical_report_models import ElectricalCheck
from .pcb_connectivity_observations import PcbAccessProbeObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_test_access_models import (
    PcbAccessProbeRequest,
    PcbAccessProbeRequestSet,
    TestAccessAnalysis,
    TestAccessEndpointRequirement,
)


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
                PcbAccessProbeRequest(endpoint=endpoint.pin, net=decision.net, side=side)
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
    """Check authored probe envelopes against retained native pad, via, and courtyard geometry."""
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
            required_nm = ceil((envelope.tip_diameter_mm / 2 + envelope.clearance_mm) * 1_000_000)
            required_aperture_nm = ceil(
                (envelope.tip_diameter_mm + 2 * envelope.clearance_mm) * 1_000_000
            )
            required_courtyard_nm = (
                None
                if envelope.courtyard_clearance_mm is None
                else ceil(
                    (envelope.tip_diameter_mm / 2 + envelope.courtyard_clearance_mm) * 1_000_000
                )
            )
            required_via_nm = (
                None
                if envelope.via_clearance_mm is None
                else ceil((envelope.tip_diameter_mm / 2 + envelope.via_clearance_mm) * 1_000_000)
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
                side_clear = aperture_clear and neighbor_clear and courtyard_clear and via_clear
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
            "from arbitrary mask graphics. It does not establish body height, probe angle, fixture or cover access, "
            "or physical reach; tracks, zone apertures, "
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
