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
    """Check authored probe envelopes against retained native aperture and pad geometry."""
    request_set = pcb_access_probe_request_set(spec)
    if request_set is None:
        return ()
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
        endpoint_results: list[tuple[TestAccessEndpointRequirement, bool, tuple[str, ...]]] = []
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
            side_details: list[str] = []
            endpoint_pass = False
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
                side_clear = aperture_clear and neighbor_clear
                endpoint_pass = endpoint_pass or side_clear
            endpoint_results.append((endpoint, endpoint_pass, tuple(side_details)))

        if not endpoint_results:
            continue
        passed = (
            all(item[1] for item in endpoint_results)
            if decision.selection == "all"
            else any(item[1] for item in endpoint_results)
        )
        details = tuple(
            f"{endpoint.pin}: {'; '.join(side_details)}"
            for endpoint, _endpoint_pass, side_details in endpoint_results
        )
        limitation = (
            "Target fit is measured only for undrilled circle, oval, rectangle, and roundrect pads, "
            "using KiCad mask expansion and the smaller pad dimension as the centered circular-tip fit. "
            "Neighbor clearance checks fitted exposed footprint pads from the target pad center; "
            "custom/chamfered/trapezoid shapes, tracks, vias, zone apertures, component bodies, fixtures, covers "
            "and probe reach are not evaluated."
        )
        checks.append(
            ElectricalCheck(
                id=f"test-access/pcb-probe-envelope/{decision.id}",
                status="PASS" if passed else "FAIL",
                detail=(" ".join(details) + " " + limitation),
            )
        )
    return tuple(checks)
