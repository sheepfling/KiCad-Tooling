"""Deterministic routed differential-pair skew analysis for exact project maps."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Literal

from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence, map_sha256
from .model_primitives import Digest
from .netlist_contract_models import NetlistContract
from .pcb_connectivity_observations import PcbPadConnectivityObservation
from .pcb_differential_pair_skew_models import (
    PcbDifferentialPairRouteMeasurement,
    PcbDifferentialPairRouteSkewEntry,
    PcbDifferentialPairRouteSkewReport,
)
from .pcb_drc_models import PcbSignalPathRequirement, PcbSignalPathRuleMap
from .pcb_native_route_topology import resolve_native_pad_route
from .source_inventory_fingerprint import source_inventory_sha256
from .source_state_models import SourceHashInventory

RouteSkewMode = Literal["review", "block", "off"]


def _route_measurement(
    path: PcbSignalPathRequirement,
    *,
    observed: NetlistContract,
    snapshot: PcbGeometrySourceEvidence,
    pads: Mapping[str, PcbPadConnectivityObservation],
) -> PcbDifferentialPairRouteMeasurement:
    """Bind and measure one authored path, retaining unsupported topology as incomplete."""
    path_id = path.id
    net = path.net
    from_pad = path.from_pad
    to_pad = path.to_pad
    source_pins = {
        item.casefold()
        for name, references in observed.nets.items()
        if name.casefold() == net.casefold()
        for item in references
    }
    absent = tuple(
        reference for reference in (from_pad, to_pad) if reference.casefold() not in source_pins
    )
    if absent:
        return PcbDifferentialPairRouteMeasurement(
            path_id=path_id,
            net=net,
            from_pad=from_pad,
            to_pad=to_pad,
            status="INCOMPLETE",
            issue=(
                "Mapped endpoint(s) are absent from the source-bound schematic net "
                f"{net!r}: {', '.join(absent)}"
            ),
        )
    route = resolve_native_pad_route(
        net=net,
        from_pad=from_pad,
        to_pad=to_pad,
        layers=snapshot.snapshot.copper_layers,
        snapshot=snapshot.snapshot,
        pads=pads,
        require_branch_free=False,
    )
    tracks_by_id = {item.uuid.casefold(): item for item in snapshot.snapshot.tracks}
    track_layers = tuple(
        tracks_by_id[track_id.casefold()].layer
        for track_id in route.track_uuids
        if track_id.casefold() in tracks_by_id
    )
    if len(track_layers) != len(route.track_uuids):
        return PcbDifferentialPairRouteMeasurement(
            path_id=path_id,
            net=net,
            from_pad=from_pad,
            to_pad=to_pad,
            status="INCOMPLETE",
            issue="Resolved native route refers to a track absent from its snapshot",
        )
    return PcbDifferentialPairRouteMeasurement(
        path_id=path_id,
        net=net,
        from_pad=from_pad,
        to_pad=to_pad,
        status=route.status,
        track_uuids=route.track_uuids,
        track_layers=track_layers,
        length_nm=route.length_nm,
        issue=route.issue,
    )


def measure_differential_pair_route_skew(
    requirements: PcbSignalPathRuleMap,
    observed: NetlistContract,
    evidence: PcbGeometrySourceEvidence,
    source_hashes: SourceHashInventory,
    netlist_sha256: Digest,
    mode: RouteSkewMode,
) -> PcbDifferentialPairRouteSkewReport:
    """Measure exact mapped route lengths against each authored bundle maximum."""
    requirement_sha256 = map_sha256(requirements)
    if not requirements.bundles:
        return PcbDifferentialPairRouteSkewReport()
    if mode == "off":
        return PcbDifferentialPairRouteSkewReport(
            status="DISABLED",
            mode=mode,
            map_sha256=requirement_sha256,
        )

    paths = {item.id.casefold(): item for item in requirements.paths}
    pads = {item.pad.casefold(): item for item in evidence.snapshot.pads}
    entries: list[PcbDifferentialPairRouteSkewEntry] = []
    for bundle in sorted(requirements.bundles, key=lambda item: item.id.casefold()):
        members = tuple(
            _route_measurement(
                paths[path_id.casefold()],
                observed=observed,
                snapshot=evidence,
                pads=pads,
            )
            for path_id in sorted(bundle.path_ids, key=str.casefold)
        )
        unresolved = tuple(item for item in members if item.status != "RESOLVED")
        if unresolved:
            entries.append(
                PcbDifferentialPairRouteSkewEntry(
                    bundle_id=bundle.id,
                    max_skew_nm=bundle.max_skew.max_nm,
                    status="INCOMPLETE",
                    paths=members,
                    issue="; ".join(
                        f"{item.path_id}: {item.issue}" for item in unresolved if item.issue
                    ),
                )
            )
            continue
        lengths = tuple(item.length_nm for item in members)
        skew = max(item for item in lengths if item is not None) - min(
            item for item in lengths if item is not None
        )
        entries.append(
            PcbDifferentialPairRouteSkewEntry(
                bundle_id=bundle.id,
                max_skew_nm=bundle.max_skew.max_nm,
                measured_skew_nm=skew,
                status="WITHIN_LIMIT" if skew <= bundle.max_skew.max_nm else "EXCEEDS_LIMIT",
                paths=members,
            )
        )

    return PcbDifferentialPairRouteSkewReport(
        status="COMPLETE"
        if all(item.status == "WITHIN_LIMIT" for item in entries)
        else "INCOMPLETE",
        mode=mode,
        map_sha256=requirement_sha256,
        source_inventory_sha256=source_inventory_sha256(source_hashes),
        netlist_sha256=netlist_sha256,
        board_path=evidence.board_path,
        board_sha256=evidence.board_sha256,
        snapshot_path=evidence.snapshot_relative_path,
        snapshot_sha256=evidence.snapshot_sha256,
        command_path=PurePosixPath(evidence.snapshot_relative_path)
        .with_name(evidence.command_path.name)
        .as_posix(),
        command_sha256=evidence.command_sha256,
        probe_sha256=evidence.probe_sha256,
        kicad_version=evidence.snapshot.kicad_version,
        image=evidence.snapshot.image,
        entries=tuple(entries),
    )
