"""Source-bound synthetic PCB return-path fault and control reports."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.models import (
    PcbConnectivitySnapshot,
    PcbNetTieObservation,
    PcbReturnBondRequirement,
    PcbReturnPathsAnalysis,
    PcbViaObservation,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
    PcbZoneObservation,
)
from tests.design_lint_fixtures.pcb_return_paths import (
    BOARD,
    IMAGE,
    NET_TIE,
    PROBE,
    VERSION,
    check_rows,
    domain,
    endpoint,
    pad,
    snapshot,
)


def _requirement() -> PcbReturnPathsAnalysis:
    return PcbReturnPathsAnalysis(
        basis="Synthetic independently reviewed direct connector-return requirement",
        domains=(domain(),),
    )


def _report(
    requirement: PcbReturnPathsAnalysis,
    evidence: PcbConnectivitySnapshot,
) -> dict[str, object]:
    board_sha256 = evidence.board_sha256
    checks = check_rows(
        requirement,
        evidence,
        board_sha256=board_sha256,
        kicad_version=VERSION,
        image=IMAGE,
        probe_sha256=PROBE,
    )
    if len({row.id for row in checks}) != len(checks):
        raise ValueError("PCB return-path check identifiers must be unique")
    return {
        "status": "FAIL" if any(row.status == "FAIL" for row in checks) else "PASS",
        "board_sha256": board_sha256,
        "requirement_sha256": hashlib.sha256(
            requirement.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "snapshot_sha256": hashlib.sha256(evidence.model_dump_json().encode("utf-8")).hexdigest(),
        "kicad_version": VERSION,
        "image": IMAGE,
        "probe_sha256": PROBE,
        "checks": [row.model_dump(mode="json") for row in checks],
    }


def return_path_report(*, connected: bool) -> dict[str, object]:
    """Serialize direct-disconnect checks and their synthetic source provenance."""
    board_sha256 = "d" * 64 if connected else BOARD
    requirement = _requirement()
    connected_pads = ("J1.7", "J2.7") if connected else None
    evidence = snapshot(
        (
            pad("J1.7", connected=connected_pads),
            pad("J2.7", connected=connected_pads),
        ),
        board_sha256=board_sha256,
    )
    return _report(requirement, evidence)


def split_plane_report(*, split: bool) -> dict[str, object]:
    """Serialize a same-net copper-island fault and continuous-plane control."""
    identity = PcbZoneIdentity(
        uuid="00000000-0000-0000-0000-000000000001",
        layer="F.Cu",
    )
    island_zero = PcbZoneIslandIdentity(
        uuid=identity.uuid,
        layer=identity.layer,
        island_index=0,
    )
    island_one = PcbZoneIslandIdentity(
        uuid=identity.uuid,
        layer=identity.layer,
        island_index=1,
    )
    connected_pads = None if split else ("J1.7", "J2.7")
    second_island = island_one if split else island_zero
    zone = PcbZoneObservation(
        uuid=identity.uuid,
        layer=identity.layer,
        name="synthetic return plane",
        net="0V_PWM",
        filled_island_count=2 if split else 1,
        unanchored_pad_island_indexes=(),
    )
    evidence = snapshot(
        (
            pad(
                "J1.7",
                connected=connected_pads,
                connected_zones=(identity,),
                connected_islands=(island_zero,),
            ),
            pad(
                "J2.7",
                connected=connected_pads,
                connected_zones=(identity,),
                connected_islands=(second_island,),
            ),
        ),
        board_sha256="e" * 64 if split else "f" * 64,
        zones=(zone,),
    )
    return _report(_requirement(), evidence)


def bonded_return_report(*, fitted: bool) -> dict[str, object]:
    """Serialize exact bonded-return contract checks for a fitted or DNP net tie."""
    bond = PcbReturnBondRequirement(
        reference="NT1",
        footprint=NET_TIE,
        pad_groups=(("NT1.1", "NT1.2"),),
    )
    requirement = PcbReturnPathsAnalysis(
        basis="Synthetic independently reviewed bonded-return requirement",
        domains=(
            domain(
                topology="bonded",
                endpoints=(endpoint("J1.7", "DGND_A"), endpoint("J2.7", "DGND_B")),
                bonds=(bond,),
            ),
        ),
    )
    evidence = snapshot(
        (
            pad("J1.7", "DGND_A", connected=("J1.7", "NT1.1")),
            pad(
                "NT1.1",
                "DGND_A",
                footprint=NET_TIE,
                dnp=not fitted,
                connected=("J1.7", "NT1.1"),
            ),
            pad("J2.7", "DGND_B", connected=("J2.7", "NT1.2")),
            pad(
                "NT1.2",
                "DGND_B",
                footprint=NET_TIE,
                dnp=not fitted,
                connected=("J2.7", "NT1.2"),
            ),
        ),
        ties=(
            PcbNetTieObservation(
                reference="NT1",
                footprint=NET_TIE,
                dnp=not fitted,
                pad_groups=(("NT1.1", "NT1.2"),),
            ),
        ),
        board_sha256="1" * 64 if fitted else "0" * 64,
    )
    return _report(requirement, evidence)


def via_stitch_report(*, stitched: bool) -> dict[str, object]:
    """Serialize separate front/back return planes with and without a stitch via."""
    front = PcbZoneIdentity(
        uuid="00000000-0000-0000-0000-000000000011",
        layer="F.Cu",
    )
    back = PcbZoneIdentity(
        uuid="00000000-0000-0000-0000-000000000012",
        layer="B.Cu",
    )
    front_island = PcbZoneIslandIdentity(
        uuid=front.uuid,
        layer=front.layer,
        island_index=0,
    )
    back_island = PcbZoneIslandIdentity(
        uuid=back.uuid,
        layer=back.layer,
        island_index=0,
    )
    via = PcbViaObservation(
        id="2" * 64,
        net="0V_PWM",
        x_nm=5_000_000,
        y_nm=7_000_000,
        start_layer="F.Cu",
        end_layer="B.Cu",
        diameter_nm=600_000,
        drill_nm=300_000,
        kind="through",
        multiplicity=1,
    )
    connected_pads = ("J1.7", "J2.7") if stitched else None
    evidence = snapshot(
        (
            pad(
                "J1.7",
                connected=connected_pads,
                connected_zones=(front,),
                connected_islands=(front_island,),
                connected_vias=(via.id,) if stitched else (),
            ),
            pad(
                "J2.7",
                connected=connected_pads,
                connected_zones=(back,),
                connected_islands=(back_island,),
                connected_vias=(via.id,) if stitched else (),
            ),
        ),
        board_sha256="3" * 64 if stitched else "2" * 64,
        zones=(
            PcbZoneObservation(
                uuid=front.uuid,
                layer=front.layer,
                name="synthetic front return plane",
                net="0V_PWM",
                filled_island_count=1,
                unanchored_pad_island_indexes=(),
            ),
            PcbZoneObservation(
                uuid=back.uuid,
                layer=back.layer,
                name="synthetic back return plane",
                net="0V_PWM",
                filled_island_count=1,
                unanchored_pad_island_indexes=(),
            ),
        ),
        vias=(via,) if stitched else (),
    )
    return _report(_requirement(), evidence)


def report_cases() -> dict[str, object]:
    return {
        "pcb_return_path_disconnected_fault": return_path_report(connected=False),
        "pcb_return_path_connected_control": return_path_report(connected=True),
        "pcb_return_path_split_plane_fault": split_plane_report(split=True),
        "pcb_return_path_single_plane_control": split_plane_report(split=False),
        "pcb_return_path_unfitted_bond_fault": bonded_return_report(fitted=False),
        "pcb_return_path_fitted_bond_control": bonded_return_report(fitted=True),
        "pcb_return_path_unstitched_layer_fault": via_stitch_report(stitched=False),
        "pcb_return_path_via_stitch_control": via_stitch_report(stitched=True),
    }
