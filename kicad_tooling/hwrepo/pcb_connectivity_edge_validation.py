"""Validate source-bound Edge.Cuts inventory and probe measurements."""

from __future__ import annotations

from .pcb_connectivity_edges import PcbEdgeCutObservation
from .pcb_connectivity_observations import PcbAccessProbeObservation

_EDGE_FIELDS = ("edge_obstacle_uuid", "edge_obstacle_distance_nm")


def validate_board_edge_evidence(
    edge_cuts: tuple[PcbEdgeCutObservation, ...],
    observations: tuple[PcbAccessProbeObservation, ...],
    *,
    schema_version: int,
    edge_inventory_present: bool,
) -> None:
    """Require every edge measurement to identify a retained Edge.Cuts item."""
    if schema_version < 21:
        if edge_cuts or any(
            getattr(item, field) is not None for item in observations for field in _EDGE_FIELDS
        ):
            raise ValueError("Edge.Cuts evidence requires native PCB schema v21+")
        return
    if not edge_inventory_present:
        raise ValueError("Native PCB schema v21+ requires explicit Edge.Cuts inventory")
    identities = [item.uuid.casefold() for item in edge_cuts]
    if len(set(identities)) != len(identities):
        raise ValueError("Native PCB Edge.Cuts identities must be unique")
    observed_ids = set(identities)
    for item in observations:
        if any(field not in item.model_fields_set for field in _EDGE_FIELDS):
            raise ValueError("Native PCB schema v21+ requires explicit probe Edge.Cuts evidence")
        if (
            item.edge_obstacle_uuid is not None
            and item.edge_obstacle_uuid.casefold() not in observed_ids
        ):
            raise ValueError("Native PCB probe observation refers to an unobserved Edge.Cuts item")
        if edge_cuts and item.target_exposed and item.edge_obstacle_uuid is None:
            raise ValueError("Native PCB probe observation omits its nearest Edge.Cuts measurement")
