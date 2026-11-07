"""Tooling-owned native route inputs for mapped differential-pair skew checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_connectivity_observations import (
    PcbPadConnectivityObservation,
    PcbTrackObservation,
    PcbViaObservation,
)
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_drc_models import (
    PcbDrcMaximumRequirement,
    PcbDrcMinMaxRequirement,
    PcbSignalPathBundleRequirement,
    PcbSignalPathRequirement,
    PcbSignalPathRuleMap,
)

IMAGE = "ghcr.io/example/kicad:10.0.5@sha256:" + "b" * 64
BOARD_SHA256 = "a" * 64
NETLIST_SHA256 = "d" * 64


def route_map(*, maximum_skew_nm: int = 500_000) -> PcbSignalPathRuleMap:
    """Return one mapped two-path bundle with a fully explicit skew limit."""
    return PcbSignalPathRuleMap(
        basis="Synthetic exact high-speed pair route map",
        paths=(
            PcbSignalPathRequirement(
                id="positive-path",
                basis="Synthetic positive endpoint mapping",
                net="USB_DP",
                from_pad="J1.1",
                to_pad="U1.1",
                length=PcbDrcMinMaxRequirement(max_nm=100_000_000),
            ),
            PcbSignalPathRequirement(
                id="negative-path",
                basis="Synthetic negative endpoint mapping",
                net="USB_DN",
                from_pad="J1.2",
                to_pad="U1.2",
                length=PcbDrcMinMaxRequirement(max_nm=100_000_000),
            ),
        ),
        bundles=(
            PcbSignalPathBundleRequirement(
                id="usb-data-pair",
                basis="Synthetic project-reviewed pair skew bound",
                path_ids=("positive-path", "negative-path"),
                from_pad_pattern="J?-?",
                to_pad_pattern="U?-?",
                max_skew=PcbDrcMaximumRequirement(max_nm=maximum_skew_nm),
            ),
        ),
    )


def route_snapshot(
    *,
    positive_length_nm: int = 1_000_000,
    negative_length_nm: int = 2_000_000,
    missing_nets: tuple[str, ...] = (),
    negative_branch: bool = False,
    negative_alternate_route: bool = False,
    negative_layer_transition: bool = False,
) -> PcbConnectivitySnapshot:
    """Construct minimal native routes with optional negative-net ambiguity controls."""
    endpoints = (
        ("J1.1", "USB_DP", "U1.1", (0, 0), (positive_length_nm, 0)),
        ("J1.2", "USB_DN", "U1.2", (0, 100_000), (negative_length_nm, 100_000)),
    )
    pads: list[PcbPadConnectivityObservation] = []
    tracks: list[PcbTrackObservation] = []
    vias: list[PcbViaObservation] = []
    for index, (source, net, destination, start, end) in enumerate(endpoints, start=1):
        for reference, position in ((source, start), (destination, end)):
            pads.append(
                PcbPadConnectivityObservation(
                    pad=reference,
                    net=net,
                    footprint="Synthetic:Connector",
                    dnp=False,
                    connected_pads=(source, destination),
                    connected_zones=(),
                    connected_islands=(),
                    connected_vias=(),
                    positions_nm=(position,),
                )
            )
        if net in missing_nets:
            continue
        direct_id = f"00000000-0000-0000-0000-00000000010{index}"
        if net == "USB_DN" and negative_layer_transition:
            second_id = "00000000-0000-0000-0000-000000000103"
            via_id = "0000000000000000000000000000000000000000000000000000000000000001"
            junction = ((start[0] + end[0]) // 2, start[1])
            tracks.extend(
                (
                    PcbTrackObservation(
                        uuid=direct_id,
                        net=net,
                        layer="F.Cu",
                        width_nm=180_000,
                        start_nm=start,
                        end_nm=junction,
                        geometry_kind="segment",
                        start_pads=(source,),
                        end_pads=(),
                        start_vias=(),
                        end_vias=(via_id,),
                        start_tracks=(),
                        end_tracks=(second_id,),
                    ),
                    PcbTrackObservation(
                        uuid=second_id,
                        net=net,
                        layer="B.Cu",
                        width_nm=180_000,
                        start_nm=junction,
                        end_nm=end,
                        geometry_kind="segment",
                        start_pads=(),
                        end_pads=(destination,),
                        start_vias=(via_id,),
                        end_vias=(),
                        start_tracks=(direct_id,),
                        end_tracks=(),
                    ),
                )
            )
            vias.append(
                PcbViaObservation(
                    id=via_id,
                    net=net,
                    x_nm=junction[0],
                    y_nm=junction[1],
                    start_layer="F.Cu",
                    end_layer="B.Cu",
                    diameter_nm=600_000,
                    drill_nm=300_000,
                    kind="through",
                    multiplicity=1,
                )
            )
        elif net == "USB_DN" and negative_branch:
            second_id = "00000000-0000-0000-0000-000000000103"
            spur_id = "00000000-0000-0000-0000-000000000104"
            junction = ((start[0] + end[0]) // 2, start[1])
            spur_end = (junction[0], junction[1] + 200_000)
            tracks.extend(
                (
                    PcbTrackObservation(
                        uuid=direct_id,
                        net=net,
                        layer="F.Cu",
                        width_nm=180_000,
                        start_nm=start,
                        end_nm=junction,
                        geometry_kind="segment",
                        start_pads=(source,),
                        end_pads=(),
                        start_vias=(),
                        end_vias=(),
                        start_tracks=(),
                        end_tracks=(second_id, spur_id),
                    ),
                    PcbTrackObservation(
                        uuid=second_id,
                        net=net,
                        layer="F.Cu",
                        width_nm=180_000,
                        start_nm=junction,
                        end_nm=end,
                        geometry_kind="segment",
                        start_pads=(),
                        end_pads=(destination,),
                        start_vias=(),
                        end_vias=(),
                        start_tracks=(direct_id, spur_id),
                        end_tracks=(),
                    ),
                    PcbTrackObservation(
                        uuid=spur_id,
                        net=net,
                        layer="F.Cu",
                        width_nm=180_000,
                        start_nm=junction,
                        end_nm=spur_end,
                        geometry_kind="segment",
                        start_pads=(),
                        end_pads=(),
                        start_vias=(),
                        end_vias=(),
                        start_tracks=(direct_id, second_id),
                        end_tracks=(),
                    ),
                )
            )
        elif net == "USB_DN" and negative_alternate_route:
            first_alt = "00000000-0000-0000-0000-000000000103"
            second_alt = "00000000-0000-0000-0000-000000000104"
            last_alt = "00000000-0000-0000-0000-000000000105"
            first_turn = (end[0] // 4, start[1] + 100_000)
            second_turn = (end[0] * 3 // 4, start[1] + 100_000)
            tracks.extend(
                (
                    PcbTrackObservation(
                        uuid=direct_id,
                        net=net,
                        layer="F.Cu",
                        width_nm=180_000,
                        start_nm=start,
                        end_nm=end,
                        geometry_kind="segment",
                        start_pads=(source,),
                        end_pads=(destination,),
                        start_vias=(),
                        end_vias=(),
                        start_tracks=(first_alt,),
                        end_tracks=(last_alt,),
                    ),
                    PcbTrackObservation(
                        uuid=first_alt,
                        net=net,
                        layer="F.Cu",
                        width_nm=180_000,
                        start_nm=start,
                        end_nm=first_turn,
                        geometry_kind="segment",
                        start_pads=(source,),
                        end_pads=(),
                        start_vias=(),
                        end_vias=(),
                        start_tracks=(direct_id,),
                        end_tracks=(second_alt,),
                    ),
                    PcbTrackObservation(
                        uuid=second_alt,
                        net=net,
                        layer="F.Cu",
                        width_nm=180_000,
                        start_nm=first_turn,
                        end_nm=second_turn,
                        geometry_kind="segment",
                        start_pads=(),
                        end_pads=(),
                        start_vias=(),
                        end_vias=(),
                        start_tracks=(first_alt,),
                        end_tracks=(last_alt,),
                    ),
                    PcbTrackObservation(
                        uuid=last_alt,
                        net=net,
                        layer="F.Cu",
                        width_nm=180_000,
                        start_nm=second_turn,
                        end_nm=end,
                        geometry_kind="segment",
                        start_pads=(),
                        end_pads=(destination,),
                        start_vias=(),
                        end_vias=(),
                        start_tracks=(second_alt,),
                        end_tracks=(direct_id,),
                    ),
                )
            )
        else:
            tracks.append(
                PcbTrackObservation(
                    uuid=direct_id,
                    net=net,
                    layer="F.Cu",
                    width_nm=180_000,
                    start_nm=start,
                    end_nm=end,
                    geometry_kind="segment",
                    start_pads=(source,),
                    end_pads=(destination,),
                    start_vias=(),
                    end_vias=(),
                    start_tracks=(),
                    end_tracks=(),
                )
            )
    return PcbConnectivitySnapshot.model_validate(
        {
            "schema_version": "8",
            "board_sha256": BOARD_SHA256,
            "kicad_version": "10.0.5",
            "image": IMAGE,
            "probe_sha256": "c" * 64,
            "zones_refilled": True,
            "pads": tuple(pads),
            "net_ties": (),
            "zones": (),
            "vias": tuple(vias),
            "access_probe_observations": (),
            "access_probe_requests_sha256": None,
            "tracks": tuple(tracks),
            "copper_layers": ("F.Cu", "B.Cu"),
        }
    )


def source_netlist() -> NetlistContract:
    return NetlistContract(
        components={},
        nets={"USB_DP": ("J1.1", "U1.1"), "USB_DN": ("J1.2", "U1.2")},
    )


def geometry_evidence(
    tmp_path: Path, snapshot: PcbConnectivitySnapshot
) -> PcbGeometrySourceEvidence:
    serialized = snapshot.model_dump_json().encode("utf-8")
    snapshot_sha256 = hashlib.sha256(serialized).hexdigest()
    return PcbGeometrySourceEvidence(
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_relative_path="build/snapshot.json",
        snapshot_path=tmp_path / "snapshot.json",
        snapshot_sha256=snapshot_sha256,
        probe_sha256=snapshot.probe_sha256,
        snapshot=snapshot,
        command=CommandEvidence(
            argv=("kicad-cli", "pcb", "export"),
            started_utc="2026-01-01T00:00:00Z",
            returncode=0,
        ),
        command_path=tmp_path / "native.command.json",
        command_sha256="e" * 64,
    )


def source_hashes() -> dict[str, str]:
    return {
        "projects/synthetic/board.kicad_pcb": BOARD_SHA256,
        "projects/synthetic/board.kicad_sch": "f" * 64,
    }
