"""Validate source-bound probe evidence against the native PCB inventory."""

from __future__ import annotations

from collections.abc import Mapping

from .pcb_connectivity_observations import (
    PcbAccessProbeObservation,
    PcbFootprintPlacementObservation,
    PcbPadConnectivityObservation,
    PcbViaObservation,
)


def validate_access_probe_relationships(
    observations: tuple[PcbAccessProbeObservation, ...],
    pads_by_reference: Mapping[str, PcbPadConnectivityObservation],
    vias_by_id: Mapping[str, PcbViaObservation],
    footprints: tuple[PcbFootprintPlacementObservation, ...],
    schema_version: int,
) -> None:
    """Reject probe geometry that is not tied to observed pads and footprints."""
    probe_keys = [(item.endpoint.casefold(), item.side.casefold()) for item in observations]
    if len(set(probe_keys)) != len(probe_keys):
        raise ValueError("Native PCB probe endpoint and side identities must be unique")
    footprints_by_reference = {item.reference.casefold(): item for item in footprints}
    for item in observations:
        target = pads_by_reference.get(item.endpoint.casefold())
        if target is None:
            raise ValueError("Native PCB probe observation refers to an unobserved pad")
        if target.net != item.target_net:
            raise ValueError("Native PCB probe target net differs from its pad inventory")
        if item.obstacle is not None:
            obstacle = pads_by_reference.get(item.obstacle.casefold())
            if obstacle is None:
                raise ValueError(
                    "Native PCB probe observation refers to an unobserved obstacle pad"
                )
            if obstacle.net != item.obstacle_net:
                raise ValueError("Native PCB probe obstacle net differs from its pad inventory")
        if item.via_obstacle_id is not None:
            via = vias_by_id.get(item.via_obstacle_id)
            if via is None:
                raise ValueError("Native PCB probe observation refers to an unobserved via")
            if via.net != item.via_obstacle_net:
                raise ValueError("Native PCB probe via net differs from its via inventory")
        if schema_version >= 10 and any(
            field not in item.model_fields_set
            for field in ("target_aperture_shape", "target_aperture_diameter_nm")
        ):
            raise ValueError("Native PCB schema v10+ requires explicit target aperture evidence")
        if schema_version >= 17:
            _validate_courtyard_evidence(item, footprints_by_reference)
        elif any(
            field in item.model_fields_set
            for field in (
                "courtyard_obstacle",
                "courtyard_distance_nm",
                "unmeasured_courtyard_footprint",
                "unmeasured_courtyard_distance_nm",
            )
        ):
            raise ValueError("Native probe courtyard evidence requires schema v17+")
        if schema_version >= 18:
            if any(
                field not in item.model_fields_set
                for field in (
                    "via_obstacle_id",
                    "via_obstacle_net",
                    "via_obstacle_distance_nm",
                    "via_obstacle_tented",
                )
            ):
                raise ValueError("Native PCB schema v18+ requires explicit via access evidence")
        elif any(
            field in item.model_fields_set
            for field in (
                "via_obstacle_id",
                "via_obstacle_net",
                "via_obstacle_distance_nm",
                "via_obstacle_tented",
            )
        ):
            raise ValueError("Native probe via evidence requires schema v18+")


def _validate_courtyard_evidence(
    observation: PcbAccessProbeObservation,
    footprints_by_reference: Mapping[str, PcbFootprintPlacementObservation],
) -> None:
    if any(
        field not in observation.model_fields_set
        for field in (
            "courtyard_obstacle",
            "courtyard_distance_nm",
            "unmeasured_courtyard_footprint",
            "unmeasured_courtyard_distance_nm",
        )
    ):
        raise ValueError("Native PCB schema v17+ requires explicit courtyard evidence")
    for reference in (
        observation.courtyard_obstacle,
        observation.unmeasured_courtyard_footprint,
    ):
        if reference is None:
            continue
        footprint = footprints_by_reference.get(reference.casefold())
        if footprint is None:
            raise ValueError("Native probe courtyard evidence refers to an unobserved footprint")
        if footprint.dnp:
            raise ValueError("Native probe courtyard evidence cannot use a DNP footprint")
        expected_side = "F.Cu" if observation.side == "front" else "B.Cu"
        if footprint.side != expected_side:
            raise ValueError("Native probe courtyard evidence uses the wrong board side")
