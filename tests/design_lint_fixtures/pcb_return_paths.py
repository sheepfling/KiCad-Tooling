"""Small synthetic inputs shared by PCB return-path regressions."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import (
    ElectricalCheck,
    PcbConnectivitySnapshot,
    PcbNetTieObservation,
    PcbPadConnectivityObservation,
    PcbReturnBondRequirement,
    PcbReturnDomainRequirement,
    PcbReturnEndpointRequirement,
    PcbReturnPathsAnalysis,
    PcbViaObservation,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
    PcbZoneObservation,
)
from kicad_tooling.hwrepo.pcb_return_path_checks import pcb_return_path_checks

BOARD = "a" * 64
PROBE = "b" * 64
IMAGE = "registry.example/ki:10.0.5@sha256:" + "c" * 64
VERSION = "10.0.5"
FOOTPRINT = "Synthetic:DB9"
NET_TIE = "Synthetic:NetTie"


def endpoint(pad: str, net: str = "0V_PWM") -> PcbReturnEndpointRequirement:
    return PcbReturnEndpointRequirement(pad=pad, net=net, footprint=FOOTPRINT)


def domain(
    identifier: str = "pwm-return",
    *,
    topology: Literal["direct", "bonded"] = "direct",
    endpoints: tuple[PcbReturnEndpointRequirement, ...] | None = None,
    bonds: tuple[PcbReturnBondRequirement, ...] = (),
) -> PcbReturnDomainRequirement:
    return PcbReturnDomainRequirement(
        id=identifier,
        basis="Synthetic independently stated connector return requirement",
        topology=topology,
        endpoints=endpoints or (endpoint("J1.7"), endpoint("J2.7")),
        bonds=bonds,
    )


def pad(
    reference: str,
    net: str | None = "0V_PWM",
    *,
    connected: tuple[str, ...] | None = None,
    connected_zones: tuple[PcbZoneIdentity, ...] = (),
    connected_islands: tuple[PcbZoneIslandIdentity, ...] = (),
    connected_vias: tuple[str, ...] = (),
    footprint: str = FOOTPRINT,
    dnp: bool = False,
    positions_nm: tuple[tuple[int, int], ...] = (),
) -> PcbPadConnectivityObservation:
    return PcbPadConnectivityObservation(
        pad=reference,
        net=net,
        footprint=footprint,
        dnp=dnp,
        connected_pads=connected or (reference,),
        connected_zones=connected_zones,
        connected_islands=connected_islands,
        connected_vias=connected_vias,
        positions_nm=positions_nm,
    )


def snapshot(
    pads: tuple[PcbPadConnectivityObservation, ...],
    *,
    ties: tuple[PcbNetTieObservation, ...] = (),
    board_sha256: str = BOARD,
    zones_refilled: bool = True,
    zones: tuple[PcbZoneObservation, ...] = (),
    vias: tuple[PcbViaObservation, ...] = (),
) -> PcbConnectivitySnapshot:
    return PcbConnectivitySnapshot(
        board_sha256=board_sha256,
        kicad_version=VERSION,
        image=IMAGE,
        probe_sha256=PROBE,
        zones_refilled=zones_refilled,
        pads=pads,
        net_ties=ties,
        zones=zones,
        vias=vias,
    )


def checks_for(
    requirement: PcbReturnPathsAnalysis,
    evidence: PcbConnectivitySnapshot,
    *,
    board_sha256: str = BOARD,
    kicad_version: str = VERSION,
    image: str = IMAGE,
    probe_sha256: str = PROBE,
) -> dict[str, ElectricalCheck]:
    return {
        row.id: row
        for row in check_rows(
            requirement,
            evidence,
            board_sha256=board_sha256,
            kicad_version=kicad_version,
            image=image,
            probe_sha256=probe_sha256,
        )
    }


def check_rows(
    requirement: PcbReturnPathsAnalysis,
    evidence: PcbConnectivitySnapshot,
    *,
    board_sha256: str = BOARD,
    kicad_version: str = VERSION,
    image: str = IMAGE,
    probe_sha256: str = PROBE,
) -> tuple[ElectricalCheck, ...]:
    """Retain the ordered service result without collapsing rows by identifier."""
    return pcb_return_path_checks(
        requirement,
        evidence,
        board_sha256=board_sha256,
        kicad_version=kicad_version,
        image=image,
        probe_sha256=probe_sha256,
    )
