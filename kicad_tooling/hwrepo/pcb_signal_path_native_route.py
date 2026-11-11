"""Resolve source-mapped PCB pad routes from native connectivity snapshots."""

from __future__ import annotations

from collections.abc import Mapping

from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from .netlist_contract_models import NetlistContract
from .pcb_connectivity_observations import PcbPadConnectivityObservation
from .pcb_differential_pair_skew_models import PcbDifferentialPairRouteMeasurement
from .pcb_native_route_topology import resolve_native_pad_route
from .pcb_signal_path_rule_models import PcbSignalPathRequirement


def measure_project_mapped_signal_path(
    path: PcbSignalPathRequirement,
    *,
    observed: NetlistContract,
    evidence: PcbGeometrySourceEvidence,
    pads: Mapping[str, PcbPadConnectivityObservation] | None = None,
) -> PcbDifferentialPairRouteMeasurement:
    """Bind and measure one authored endpoint route using exact native evidence."""
    source_pins = {
        item.casefold()
        for name, references in observed.nets.items()
        if name.casefold() == path.net.casefold()
        for item in references
    }
    absent = tuple(
        reference
        for reference in (path.from_pad, path.to_pad)
        if reference.casefold() not in source_pins
    )
    if absent:
        return PcbDifferentialPairRouteMeasurement(
            path_id=path.id,
            net=path.net,
            from_pad=path.from_pad,
            to_pad=path.to_pad,
            status="INCOMPLETE",
            issue=(
                "Mapped endpoint(s) are absent from the source-bound schematic net "
                f"{path.net!r}: {', '.join(absent)}"
            ),
        )
    pad_map = pads or {item.pad.casefold(): item for item in evidence.snapshot.pads}
    route = resolve_native_pad_route(
        net=path.net,
        from_pad=path.from_pad,
        to_pad=path.to_pad,
        layers=evidence.snapshot.copper_layers,
        snapshot=evidence.snapshot,
        pads=pad_map,
        require_branch_free=False,
    )
    tracks_by_id = {item.uuid.casefold(): item for item in evidence.snapshot.tracks}
    track_layers = tuple(
        tracks_by_id[track_id.casefold()].layer
        for track_id in route.track_uuids
        if track_id.casefold() in tracks_by_id
    )
    if len(track_layers) != len(route.track_uuids):
        return PcbDifferentialPairRouteMeasurement(
            path_id=path.id,
            net=path.net,
            from_pad=path.from_pad,
            to_pad=path.to_pad,
            status="INCOMPLETE",
            issue="Resolved native route refers to a track absent from its snapshot",
        )
    return PcbDifferentialPairRouteMeasurement(
        path_id=path.id,
        net=path.net,
        from_pad=path.from_pad,
        to_pad=path.to_pad,
        status=route.status,
        track_uuids=route.track_uuids,
        track_layers=track_layers,
        length_nm=route.length_nm,
        issue=route.issue,
    )
