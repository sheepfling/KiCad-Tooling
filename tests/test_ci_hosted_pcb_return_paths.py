"""Source-bound hosted PCB return fixture orchestration regressions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from kicad_tooling.ci_hosted import HostedLog
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    PcbConnectivitySnapshot,
    PcbNetTieObservation,
    PcbPadConnectivityObservation,
    PcbTrackObservation,
    PcbViaObservation,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
    PcbZoneObservation,
    ProjectConfig,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
    pytest.mark.template_checkout,
]


def test_pcb_return_fixture_checks_native_connectivity_zone_via_and_net_tie_evidence(
    hosted_reference_root: Path,
) -> None:
    from kicad_tooling.ci_hosted import pcb_return_fixture_lane
    from kicad_tooling.hwrepo.contracts import repo_path
    from kicad_tooling.hwrepo.electrical import selected_config
    from kicad_tooling.hwrepo.evidence import digest
    from kicad_tooling.hwrepo.pcb_return_path_capture import expected_probe_sha256

    config = selected_config(hosted_reference_root, "controller")
    observed_boards: list[Path] = []

    def capture(
        root: Path, selected: ProjectConfig, output: Path
    ) -> tuple[CommandEvidence, PcbConnectivitySnapshot]:
        assert root == hosted_reference_root.resolve()
        assert selected.image == config.image
        assert selected.kicad_version == config.kicad_version
        board = repo_path(root, selected.project).with_suffix(".kicad_pcb")
        content = board.read_text(encoding="utf-8")
        assert output.is_relative_to(root)
        output.mkdir()
        observed_boards.append(board)
        fixture_id = Path(selected.project).stem
        is_via_fixture = fixture_id.startswith("alternate-layer-")
        is_plane_fixture = fixture_id in {"unstitched-planes", "stitched-planes"}
        is_zone_fixture = fixture_id.startswith("zone-") or is_plane_fixture
        is_unanchored_zone = fixture_id == "zone-unanchored-island"
        is_tie_fixture = fixture_id.startswith("net-tie-")
        is_isolation_fixture = fixture_id.startswith("isolation-")
        is_isolation_bridge = fixture_id == "isolation-bridged"
        tie_dnp = fixture_id == "net-tie-dnp"
        expected_connected = fixture_id in {
            "alternate-layer-via",
            "stitched-planes",
            "zone-connected",
            "zone-unanchored-island",
            "net-tie-connected",
            "isolation-open",
            "isolation-bridged",
        }
        is_split_zone = is_zone_fixture and ("split" in fixture_id or is_unanchored_zone)
        expected_islands = 2 if is_split_zone else 1
        expected_island_indices = (
            (0, 0) if is_unanchored_zone else (0, 1) if is_split_zone else (0, 0)
        )
        if is_via_fixture:
            assert '(layers "F.Cu" "B.Cu")' in content
            assert '(layer "F.Cu") (net 1)' in content
            if expected_connected:
                assert "(segment (start 10 5) (end 15 5)" in content
            else:
                assert "(segment (start 10 5) (end 15 5)" not in content
        if is_zone_fixture:
            assert '(zone (net 1) (net_name "RETURN")' in content
            if expected_islands == 2:
                if is_unanchored_zone:
                    assert "(segment (start -1 7) (end 21 7)" in content
                    assert "(island_removal_mode 1)" in content
                else:
                    assert "(segment (start 10 -1) (end 10 11)" in content
        if is_plane_fixture:
            assert content.count('(zone (net 1) (net_name "RETURN") (layer "F.Cu")') == 1
            assert content.count('(zone (net 1) (net_name "RETURN") (layer "B.Cu")') == 1
            if fixture_id == "stitched-planes":
                assert "(via (at 10 5) (size 0.8) (drill 0.3)" in content
            else:
                assert "(via " not in content
        if is_tie_fixture:
            assert '(net_tie_pad_groups "1,2")' in content
            if tie_dnp:
                assert "(attr smd dnp)" in content
        if is_isolation_fixture:
            assert '(net 1 "RETURN_A")' in content
            assert '(net 2 "RETURN_B")' in content
            if is_isolation_bridge:
                assert '(net_tie_pad_groups "1,2")' in content
        connected_pads = ("J1.1", "J2.1") if expected_connected else ("J1.1",)
        connected_j2 = ("J1.1", "J2.1") if expected_connected else ("J2.1",)
        via_id = "d" * 64
        first_connected_vias = (
            (via_id,) if is_via_fixture or (is_plane_fixture and expected_connected) else ()
        )
        second_connected_vias = (
            (via_id,) if expected_connected and (is_via_fixture or is_plane_fixture) else ()
        )
        via_inventory = (
            (
                PcbViaObservation(
                    id=via_id,
                    net="RETURN",
                    x_nm=10_000_000,
                    y_nm=5_000_000,
                    start_layer="F.Cu",
                    end_layer="B.Cu",
                    diameter_nm=800_000,
                    drill_nm=300_000,
                    kind="through",
                    multiplicity=1,
                ),
            )
            if is_via_fixture or (is_plane_fixture and expected_connected)
            else ()
        )
        track_inventory = (
            (
                PcbTrackObservation(
                    uuid="00000000-0000-0000-0000-000000000011",
                    net="RETURN",
                    layer="F.Cu",
                    width_nm=300_000,
                    start_nm=(5_000_000, 5_000_000),
                    end_nm=(10_000_000, 5_000_000),
                    geometry_kind="segment",
                    start_pads=("J1.1",),
                    end_pads=(),
                    start_vias=(),
                    end_vias=(via_id,),
                ),
                *(
                    (
                        PcbTrackObservation(
                            uuid="00000000-0000-0000-0000-000000000012",
                            net="RETURN",
                            layer="B.Cu",
                            width_nm=300_000,
                            start_nm=(10_000_000, 5_000_000),
                            end_nm=(15_000_000, 5_000_000),
                            geometry_kind="segment",
                            start_pads=(),
                            end_pads=("J2.1",),
                            start_vias=(via_id,),
                            end_vias=(),
                        ),
                    )
                    if expected_connected
                    else ()
                ),
            )
            if is_via_fixture
            else ()
        )
        zone_identity = PcbZoneIdentity(
            uuid="00000000-0000-0000-0000-000000000001",
            layer="F.Cu",
        )
        back_zone_identity = PcbZoneIdentity(
            uuid="00000000-0000-0000-0000-000000000002",
            layer="B.Cu",
        )
        second_zone_identity = back_zone_identity if is_plane_fixture else zone_identity
        first_island = PcbZoneIslandIdentity(
            uuid=zone_identity.uuid,
            layer=zone_identity.layer,
            island_index=expected_island_indices[0],
        )
        second_island = PcbZoneIslandIdentity(
            uuid=second_zone_identity.uuid,
            layer=second_zone_identity.layer,
            island_index=expected_island_indices[1],
        )
        if is_tie_fixture:
            endpoint_pads = (
                PcbPadConnectivityObservation(
                    pad="J1.1",
                    net="RETURN_A",
                    footprint="Synthetic:TestPad",
                    dnp=False,
                    connected_pads=("J1.1", "NT1.1"),
                    connected_zones=(),
                    connected_islands=(),
                    connected_vias=(),
                ),
                PcbPadConnectivityObservation(
                    pad="J2.1",
                    net="RETURN_B",
                    footprint="Synthetic:TestPad",
                    dnp=False,
                    connected_pads=("J2.1", "NT1.2"),
                    connected_zones=(),
                    connected_islands=(),
                    connected_vias=(),
                ),
            )
            tie_pads = (
                PcbPadConnectivityObservation(
                    pad="NT1.1",
                    net="RETURN_A",
                    footprint="Synthetic:NetTie-2",
                    dnp=tie_dnp,
                    connected_pads=("J1.1", "NT1.1"),
                    connected_zones=(),
                    connected_islands=(),
                    connected_vias=(),
                ),
                PcbPadConnectivityObservation(
                    pad="NT1.2",
                    net="RETURN_B",
                    footprint="Synthetic:NetTie-2",
                    dnp=tie_dnp,
                    connected_pads=("J2.1", "NT1.2"),
                    connected_zones=(),
                    connected_islands=(),
                    connected_vias=(),
                ),
            )
        elif is_isolation_fixture:
            a_members = ("J1.1", "J3.1") + (("NT1.1",) if is_isolation_bridge else ())
            b_members = ("J2.1", "J4.1") + (("NT1.2",) if is_isolation_bridge else ())
            endpoint_pads = tuple(
                PcbPadConnectivityObservation(
                    pad=reference,
                    net="RETURN_A" if reference in {"J1.1", "J3.1"} else "RETURN_B",
                    footprint="Synthetic:TestPad",
                    dnp=False,
                    connected_pads=members,
                    connected_zones=(),
                    connected_islands=(),
                    connected_vias=(),
                )
                for members, references in (
                    (a_members, ("J1.1", "J3.1")),
                    (b_members, ("J2.1", "J4.1")),
                )
                for reference in references
            )
            tie_pads = (
                (
                    PcbPadConnectivityObservation(
                        pad="NT1.1",
                        net="RETURN_A",
                        footprint="Synthetic:NetTie-2",
                        dnp=False,
                        connected_pads=a_members,
                        connected_zones=(),
                        connected_islands=(),
                        connected_vias=(),
                    ),
                    PcbPadConnectivityObservation(
                        pad="NT1.2",
                        net="RETURN_B",
                        footprint="Synthetic:NetTie-2",
                        dnp=False,
                        connected_pads=b_members,
                        connected_zones=(),
                        connected_islands=(),
                        connected_vias=(),
                    ),
                )
                if is_isolation_bridge
                else ()
            )
        else:
            endpoint_pads = (
                PcbPadConnectivityObservation(
                    pad="J1.1",
                    net="RETURN",
                    footprint="Synthetic:TestPad",
                    dnp=False,
                    connected_pads=connected_pads,
                    connected_zones=(zone_identity,) if is_zone_fixture else (),
                    connected_islands=(first_island,) if is_zone_fixture else (),
                    connected_vias=first_connected_vias,
                ),
                PcbPadConnectivityObservation(
                    pad="J2.1",
                    net="RETURN",
                    footprint="Synthetic:TestPad",
                    dnp=False,
                    connected_pads=connected_j2,
                    connected_zones=(second_zone_identity,) if is_zone_fixture else (),
                    connected_islands=(second_island,) if is_zone_fixture else (),
                    connected_vias=second_connected_vias,
                ),
            )
            tie_pads = ()
        if is_plane_fixture:
            zone_observations = (
                PcbZoneObservation(
                    uuid=zone_identity.uuid,
                    layer=zone_identity.layer,
                    name="",
                    net="RETURN",
                    filled_island_count=1,
                    unanchored_pad_island_indexes=(),
                ),
                PcbZoneObservation(
                    uuid=back_zone_identity.uuid,
                    layer=back_zone_identity.layer,
                    name="",
                    net="RETURN",
                    filled_island_count=1,
                    unanchored_pad_island_indexes=(),
                ),
            )
        elif is_zone_fixture:
            zone_observations = (
                PcbZoneObservation(
                    uuid=zone_identity.uuid,
                    layer=zone_identity.layer,
                    name="",
                    net="RETURN",
                    filled_island_count=expected_islands,
                    unanchored_pad_island_indexes=(1,) if is_unanchored_zone else (),
                ),
            )
        else:
            zone_observations = ()
        snapshot = PcbConnectivitySnapshot(
            board_sha256=digest(board),
            kicad_version=selected.kicad_version,
            image=selected.image,
            probe_sha256=expected_probe_sha256(),
            zones_refilled=True,
            pads=(*endpoint_pads, *tie_pads),
            net_ties=(
                PcbNetTieObservation(
                    reference="NT1",
                    footprint="Synthetic:NetTie-2",
                    dnp=tie_dnp,
                    pad_groups=(("NT1.1", "NT1.2"),),
                ),
            )
            if is_tie_fixture or is_isolation_bridge
            else (),
            zones=zone_observations,
            vias=via_inventory,
            tracks=track_inventory,
        )
        board_argument = "/work/" + Path(selected.project).with_suffix(".kicad_pcb").as_posix()
        return (
            CommandEvidence(
                argv=(
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "--network",
                    "none",
                    "--read-only",
                    "--tmpfs",
                    "/tmp:rw,nosuid,nodev,size=64m",
                    "-v",
                    f"{root}:/work:ro",
                    "-v",
                    f"{output}:/output:rw",
                    "-w",
                    "/work",
                    "--entrypoint",
                    "/usr/bin/python3",
                    selected.image,
                    "-I",
                    "-B",
                    "/output/native_pcb_probe.py",
                    board_argument,
                    "/output/snapshot.json",
                ),
                started_utc="2026-01-01T00:00:00Z",
                returncode=0,
            ),
            snapshot,
        )

    log = HostedLog(hosted_reference_root, "native-pcb-fixture")
    with patch(
        "kicad_tooling.hwrepo.pcb_return_path_capture.capture_native_pcb_connectivity",
        side_effect=capture,
    ) as run_probe:
        pcb_return_fixture_lane(
            hosted_reference_root, project="controller", image=config.image, log=log
        )

    assert run_probe.call_count == 14
    assert len(observed_boards) == 14
    assert all(board.is_file() for board in observed_boards)
    events = [json.loads(line) for line in log.events.read_text().splitlines()]
    results = {
        event["stage"]: event
        for event in events
        if event["stage"].startswith("pcb-return-fixture/")
    }
    for fixture_id, connectivity in (
        ("alternate-layer-via", "connected"),
        ("alternate-layer-open", "open"),
        ("zone-connected", "connected"),
        ("unstitched-planes", "open"),
        ("stitched-planes", "connected"),
        ("zone-unanchored-island", "connected"),
        ("zone-split", "open"),
        ("zone-through-hole-split", "open"),
        ("net-tie-connected", "connected"),
        ("net-tie-dnp", "open"),
        ("isolation-open", "connected"),
        ("isolation-bridged", "connected"),
    ):
        result = results[f"pcb-return-fixture/{fixture_id}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == config.kicad_version
        assert result["expected_connectivity"] == connectivity
        if fixture_id == "alternate-layer-via":
            assert result["via_identity_repeatable"] == "true"
        if fixture_id == "stitched-planes":
            assert result["plane_stitch_repeatable"] == "true"
            assert result["zone_layers"] == "F.Cu,B.Cu"
        if fixture_id.startswith("isolation-"):
            assert result["expected_isolation"] == (
                "separate" if fixture_id == "isolation-open" else "bridged"
            )
        assert (hosted_reference_root / result["receipt"]).is_relative_to(hosted_reference_root)
