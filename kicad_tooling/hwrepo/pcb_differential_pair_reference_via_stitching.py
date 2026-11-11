"""Review reference-via proximity at project-mapped pair layer transitions."""

from __future__ import annotations

from collections.abc import Mapping
from math import isqrt
from pathlib import PurePosixPath
from typing import Literal

from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence, map_sha256
from .model_primitives import Digest
from .netlist_contract_models import NetlistContract
from .pcb_connectivity_observations import PcbTrackObservation, PcbViaObservation
from .pcb_differential_pair_reference_via_models import (
    PcbDifferentialPairReferenceViaEntry,
    PcbDifferentialPairReferenceViaReport,
    PcbReferenceViaTransition,
)
from .pcb_signal_path_native_route import measure_project_mapped_signal_path
from .pcb_signal_path_rule_models import PcbSignalPathBundleRequirement, PcbSignalPathRuleMap
from .source_inventory_fingerprint import source_inventory_sha256
from .source_state_models import SourceHashInventory

ReferenceViaMode = Literal["review", "block", "off"]


def _round_distance_nm(distance_squared: int) -> int:
    floor = isqrt(distance_squared)
    return floor + (4 * distance_squared >= (2 * floor + 1) ** 2)


def _via_spans_layers(
    via: PcbViaObservation,
    requested_layers: tuple[str, str],
    copper_layers: tuple[str, ...],
) -> bool:
    indexes = {layer.casefold(): index for index, layer in enumerate(copper_layers)}
    start = indexes.get(via.start_layer.casefold())
    end = indexes.get(via.end_layer.casefold())
    requested = tuple(indexes.get(layer.casefold()) for layer in requested_layers)
    if start is None or end is None or any(index is None for index in requested):
        return False
    low, high = sorted((start, end))
    return all(low <= index <= high for index in requested if index is not None)


def _endpoint_vias(track: PcbTrackObservation) -> Mapping[tuple[int, int], set[str]]:
    return {
        track.start_nm: {item.casefold() for item in track.start_vias},
        track.end_nm: {item.casefold() for item in track.end_vias},
    }


def _transition_via(
    first: PcbTrackObservation,
    second: PcbTrackObservation,
    vias: Mapping[str, PcbViaObservation],
    copper_layers: tuple[str, ...],
) -> tuple[PcbViaObservation | None, str | None]:
    first_contacts = _endpoint_vias(first)
    second_contacts = _endpoint_vias(second)
    common_points = set(first_contacts) & set(second_contacts)
    common_via_ids = {
        via_id
        for point in common_points
        for via_id in first_contacts[point] & second_contacts[point]
    }
    if len(common_points) != 1 or len(common_via_ids) != 1:
        return None, "Cross-layer route adjacency does not resolve to one shared native via"
    via_id = next(iter(common_via_ids))
    via = vias.get(via_id)
    if via is None:
        return None, "Cross-layer route endpoint refers to a via absent from the native snapshot"
    if (
        first.net is None
        or second.net is None
        or via.net is None
        or via.net.casefold() != first.net.casefold()
        or via.net.casefold() != second.net.casefold()
    ):
        return None, "Cross-layer route via is not assigned to the mapped signal net"
    if not _via_spans_layers(via, (first.layer, second.layer), copper_layers):
        return None, "Signal via layer span does not match the route transition"
    point = next(iter(common_points))
    if (via.x_nm, via.y_nm) != point:
        return None, "Native signal via center differs from the routed transition vertex"
    return via, None


def _nearest_reference_via(
    signal_via: PcbViaObservation,
    *,
    reference_net: str,
    transition_layers: tuple[str, str],
    copper_layers: tuple[str, ...],
    vias: tuple[PcbViaObservation, ...],
) -> tuple[PcbViaObservation | None, int | None]:
    compatible = tuple(
        via
        for via in vias
        if via.net is not None
        and via.net.casefold() == reference_net.casefold()
        and _via_spans_layers(
            via,
            transition_layers,
            copper_layers,
        )
    )
    if not compatible:
        return None, None
    nearest = min(
        compatible,
        key=lambda via: (
            (via.x_nm - signal_via.x_nm) ** 2 + (via.y_nm - signal_via.y_nm) ** 2,
            via.id,
        ),
    )
    distance_squared = (nearest.x_nm - signal_via.x_nm) ** 2 + (nearest.y_nm - signal_via.y_nm) ** 2
    return nearest, distance_squared


def _bundle_entry(
    bundle: PcbSignalPathBundleRequirement,
    *,
    requirements: PcbSignalPathRuleMap,
    evidence: PcbGeometrySourceEvidence,
    observed: NetlistContract,
) -> PcbDifferentialPairReferenceViaEntry:
    reference_net = bundle.reference_net
    max_distance = bundle.max_reference_via_distance_nm
    if reference_net is None or max_distance is None:
        raise ValueError("Only bundles with a complete reference-via contract can be analyzed")
    source_nets = {name.casefold() for name in observed.nets}
    if reference_net.casefold() not in source_nets:
        return PcbDifferentialPairReferenceViaEntry(
            bundle_id=bundle.id,
            reference_net=reference_net,
            max_distance_nm=max_distance,
            status="INCOMPLETE",
            transitions=(),
            issue=f"Authored reference net {reference_net!r} is absent from the source netlist",
        )

    paths = {item.id.casefold(): item for item in requirements.paths}
    tracks = {item.uuid.casefold(): item for item in evidence.snapshot.tracks}
    vias = {item.id.casefold(): item for item in evidence.snapshot.vias}
    transitions: list[PcbReferenceViaTransition] = []
    for path_id in sorted(bundle.path_ids, key=str.casefold):
        path = paths[path_id.casefold()]
        route = measure_project_mapped_signal_path(
            path,
            observed=observed,
            evidence=evidence,
        )
        if route.status != "RESOLVED":
            transitions.append(
                PcbReferenceViaTransition(
                    path_id=path_id,
                    status="INCOMPLETE",
                    issue=route.issue or "Mapped route is incomplete",
                )
            )
            continue
        if len(route.track_uuids) != len(route.track_layers) or not route.track_layers:
            transitions.append(
                PcbReferenceViaTransition(
                    path_id=path_id,
                    status="INCOMPLETE",
                    issue="Resolved mapped route lacks ordered native track-layer evidence",
                )
            )
            continue
        ordered_tracks = tuple(tracks.get(item.casefold()) for item in route.track_uuids)
        if any(item is None for item in ordered_tracks):
            transitions.append(
                PcbReferenceViaTransition(
                    path_id=path_id,
                    status="INCOMPLETE",
                    issue="Resolved mapped route refers to a track absent from its native snapshot",
                )
            )
            continue
        complete_tracks = tuple(item for item in ordered_tracks if item is not None)
        for first, second, first_layer, second_layer in zip(
            complete_tracks[:-1],
            complete_tracks[1:],
            route.track_layers[:-1],
            route.track_layers[1:],
            strict=True,
        ):
            if first_layer.casefold() == second_layer.casefold():
                continue
            signal_via, issue = _transition_via(
                first,
                second,
                vias,
                evidence.snapshot.copper_layers,
            )
            if signal_via is None:
                transitions.append(
                    PcbReferenceViaTransition(
                        path_id=path.id,
                        from_layer=first_layer,
                        to_layer=second_layer,
                        status="INCOMPLETE",
                        issue=issue or "Cross-layer route transition is unsupported",
                    )
                )
                continue
            nearest, distance_squared = _nearest_reference_via(
                signal_via,
                reference_net=reference_net,
                transition_layers=(first_layer, second_layer),
                copper_layers=evidence.snapshot.copper_layers,
                vias=evidence.snapshot.vias,
            )
            within = (
                nearest is not None
                and distance_squared is not None
                and distance_squared <= max_distance**2
            )
            transitions.append(
                PcbReferenceViaTransition(
                    path_id=path.id,
                    from_layer=first_layer,
                    to_layer=second_layer,
                    signal_via_id=signal_via.id,
                    position_nm=(signal_via.x_nm, signal_via.y_nm),
                    nearest_reference_via_id=None if nearest is None else nearest.id,
                    nearest_distance_nm=(
                        None if distance_squared is None else _round_distance_nm(distance_squared)
                    ),
                    nearest_distance_squared_nm2=distance_squared,
                    status="WITHIN_LIMIT" if within else "MISSING_REFERENCE_VIA",
                )
            )
    has_incomplete = any(item.status == "INCOMPLETE" for item in transitions)
    has_missing = any(item.status == "MISSING_REFERENCE_VIA" for item in transitions)
    status = (
        "INCOMPLETE"
        if has_incomplete
        else "MISSING_REFERENCE_VIA"
        if has_missing
        else "WITHIN_LIMIT"
    )
    return PcbDifferentialPairReferenceViaEntry(
        bundle_id=bundle.id,
        reference_net=reference_net,
        max_distance_nm=max_distance,
        status=status,
        transitions=tuple(transitions),
    )


def measure_differential_pair_reference_via_stitching(
    requirements: PcbSignalPathRuleMap,
    observed: NetlistContract,
    evidence: PcbGeometrySourceEvidence,
    source_hashes: SourceHashInventory,
    netlist_sha256: Digest,
    mode: ReferenceViaMode,
) -> PcbDifferentialPairReferenceViaReport:
    """Check authored reference-via distance limits at exact mapped layer transitions."""
    configured = tuple(
        item
        for item in requirements.bundles
        if item.reference_net is not None and item.max_reference_via_distance_nm is not None
    )
    if not configured:
        return PcbDifferentialPairReferenceViaReport()
    requirement_sha256 = map_sha256(requirements)
    if mode == "off":
        return PcbDifferentialPairReferenceViaReport(
            status="DISABLED",
            mode=mode,
            map_sha256=requirement_sha256,
            configured_bundle_ids=tuple(
                item.id for item in sorted(configured, key=lambda item: item.id.casefold())
            ),
        )
    entries = tuple(
        _bundle_entry(
            bundle,
            requirements=requirements,
            evidence=evidence,
            observed=observed,
        )
        for bundle in sorted(configured, key=lambda item: item.id.casefold())
    )
    return PcbDifferentialPairReferenceViaReport(
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
        configured_bundle_ids=tuple(
            item.id for item in sorted(configured, key=lambda item: item.id.casefold())
        ),
        entries=entries,
    )
