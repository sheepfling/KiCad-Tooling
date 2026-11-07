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
) -> PcbConnectivitySnapshot:
    """Construct a minimal native schema-8 board with two exact straight routes."""
    endpoints = (
        ("J1.1", "USB_DP", "U1.1", (0, 0), (positive_length_nm, 0)),
        ("J1.2", "USB_DN", "U1.2", (0, 100_000), (negative_length_nm, 100_000)),
    )
    pads: list[PcbPadConnectivityObservation] = []
    tracks: list[PcbTrackObservation] = []
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
        if net not in missing_nets:
            tracks.append(
                PcbTrackObservation(
                    uuid=f"00000000-0000-0000-0000-00000000010{index}",
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
            "vias": (),
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
