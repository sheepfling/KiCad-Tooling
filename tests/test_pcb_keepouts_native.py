"""Exact-version native extraction of synthetic PCB keepout rule areas."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ComponentIdentity,
    IgnoredChecks,
    NetlistContract,
    PcbRfAntennaKeepout,
    PcbRfAntennaPolygon,
    PcbRfModuleAntennaMap,
    PcbRfModuleAntennaRequirement,
    PcbRuleAreaObservation,
    PcbValidationContract,
    ProjectConfig,
    ProjectKind,
)
from kicad_tooling.hwrepo.pcb_return_path_capture import (
    capture_native_pcb_connectivity,
    expected_probe_sha256,
)
from kicad_tooling.hwrepo.pcb_rf_antenna import pcb_rf_module_antenna_entries

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.native_kicad,
    pytest.mark.pcb_lint,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]

FIXTURE = Path(__file__).parent / "fixtures/design_lint/pcb-keepout-rule-area.kicad_pcb"


@pytest.mark.parametrize(
    ("expected_version", "image"),
    (
        (
            "10.0.0",
            (
                "ghcr.io/kicad/kicad:10.0.0@sha256:"
                "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
            ),
        ),
        (
            "10.0.5",
            (
                "ghcr.io/kicad/kicad:10.0.5@sha256:"
                "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
            ),
        ),
    ),
)
def test_native_schema_12_snapshot_records_keepout_and_footprint_evidence(
    tmp_path: Path, expected_version: str, image: str
) -> None:
    root = tmp_path / "project"
    board_relative = "projects/synthetic/kicad/board.kicad_pcb"
    board = root / board_relative
    board.parent.mkdir(parents=True)
    board.write_bytes(FIXTURE.read_bytes())
    project_path = root / "projects/synthetic/kicad/board.kicad_pro"
    project_path.write_text("{}\n", encoding="utf-8")
    config = ProjectConfig(
        schema_version="1",
        kind=ProjectKind.PCB,
        assurance_profile="training",
        not_for_manufacture=True,
        project_id="synthetic-keepout",
        component_identity=ComponentIdentity(required=False, part_ids=()),
        toolchain_id=f"kicad-{expected_version}",
        kicad_version=expected_version,
        image=image,
        project="projects/synthetic/kicad/board.kicad_pro",
        source_roots=("projects/synthetic",),
        required_inputs=(board_relative,),
        validation=PcbValidationContract(
            kind=ProjectKind.PCB,
            components={},
            nets={},
            expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
        ),
    )

    command, snapshot = capture_native_pcb_connectivity(
        root, config, root / "build/tests/native-keepout" / expected_version
    )

    assert command.returncode == 0, command.stderr or command.error
    assert snapshot is not None
    assert snapshot.kicad_version == expected_version
    assert snapshot.schema_version == "12"
    assert snapshot.board_sha256
    assert snapshot.probe_sha256 == expected_probe_sha256()
    assert len(snapshot.rule_areas) == 3
    footprints = {item.reference: item for item in snapshot.footprints}
    assert tuple(item.reference for item in snapshot.footprints) == ("U1", "U2", "U3")
    assert set(footprints) == {"U1", "U2", "U3"}
    assert footprints["U1"].footprint == "RF_Module:Probe_Module"
    assert footprints["U1"].dnp is False
    assert footprints["U1"].position_nm == (20_000_000, 20_000_000)
    assert footprints["U1"].orientation_microdegrees == 90_000_000
    assert footprints["U1"].side == "F.Cu"
    assert footprints["U2"].footprint == "RF_Module:Probe_Module"
    assert footprints["U2"].dnp is False
    assert footprints["U2"].position_nm == (30_000_000, 25_000_000)
    assert footprints["U2"].orientation_microdegrees == 270_000_000
    assert footprints["U2"].side == "B.Cu"
    assert footprints["U3"].footprint == "RF_Module:Probe_Module"
    assert footprints["U3"].dnp is False
    assert footprints["U3"].position_nm == (40_000_000, 40_000_000)
    assert footprints["U3"].orientation_microdegrees == 30_000_000
    assert footprints["U3"].side == "F.Cu"
    assert {item.pad for item in snapshot.pads} == {"U1.1", "U2.1", "U3.1"}
    pads = {item.pad: item for item in snapshot.pads}
    assert pads["U1.1"].positions_nm == ((20_000_000, 19_000_000),)
    assert pads["U2.1"].positions_nm == ((30_000_000, 24_000_000),)
    assert pads["U3.1"].positions_nm == ((40_866_025, 39_500_000),)
    assert all(
        item.footprint == footprints[item.pad.split(".")[0]].footprint for item in snapshot.pads
    )
    assert all(item.dnp == footprints[item.pad.split(".")[0]].dnp for item in snapshot.pads)
    areas: dict[str, PcbRuleAreaObservation] = {item.name: item for item in snapshot.rule_areas}
    front_area = areas["SYNTHETIC_ANTENNA_KEEPOUT"]
    assert front_area.layers == ("F.Cu", "B.Cu")
    assert front_area.net is None
    assert len(front_area.polygons) == 1
    assert set(front_area.polygons[0].outline_nm) == {
        (10_000_000, 10_000_000),
        (10_000_000, 12_000_000),
        (13_000_000, 12_000_000),
        (13_000_000, 10_000_000),
    }
    angled_area = areas["SYNTHETIC_ANTENNA_KEEPOUT_ANGLED"]
    assert set(angled_area.polygons[0].outline_nm) == {
        (40_000_000, 40_000_000),
        (42_598_076, 38_500_000),
        (43_098_076, 39_366_025),
        (40_500_000, 40_866_025),
    }
    for keepout in areas.values():
        assert keepout.net is None
        assert keepout.forbids_tracks
        assert keepout.forbids_vias
        assert keepout.forbids_pads
        assert keepout.forbids_zone_fills
        assert not keepout.forbids_footprints

    module_identity = {
        "expected_symbol": "RF_Module:Probe_Module",
        "expected_footprint": "RF_Module:Probe_Module",
        "expected_part_id": "RF-PROBE",
        "rf_feed_net": "RF_FEED",
    }
    requirements = PcbRfModuleAntennaMap(
        basis="Synthetic native placement-relative RF keepout fixture",
        requirements=(
            PcbRfModuleAntennaRequirement(
                id="front-module",
                basis="Synthetic front-side module-local polygon",
                reference="U1",
                rf_feed_pad="U1.1",
                keepout=PcbRfAntennaKeepout(
                    name="SYNTHETIC_ANTENNA_KEEPOUT",
                    local_polygons=(
                        PcbRfAntennaPolygon(
                            outline_nm=(
                                (10_000_000, -10_000_000),
                                (8_000_000, -10_000_000),
                                (8_000_000, -7_000_000),
                                (10_000_000, -7_000_000),
                            )
                        ),
                    ),
                    layers=("F.Cu", "B.Cu"),
                    forbids_tracks=True,
                    forbids_vias=True,
                    forbids_pads=True,
                    forbids_zone_fills=True,
                    forbids_footprints=False,
                ),
                **module_identity,
                disposition="onboard_antenna",
            ),
            PcbRfModuleAntennaRequirement(
                id="back-module",
                basis="Synthetic back-side module-local polygon",
                reference="U2",
                rf_feed_pad="U2.1",
                keepout=PcbRfAntennaKeepout(
                    name="SYNTHETIC_ANTENNA_KEEPOUT_BACK",
                    local_polygons=(
                        PcbRfAntennaPolygon(
                            outline_nm=(
                                (0, 0),
                                (3_000_000, 0),
                                (3_000_000, 2_000_000),
                                (0, 2_000_000),
                            )
                        ),
                    ),
                    layers=("F.Cu", "B.Cu"),
                    forbids_tracks=True,
                    forbids_vias=True,
                    forbids_pads=True,
                    forbids_zone_fills=True,
                    forbids_footprints=False,
                ),
                **module_identity,
                disposition="onboard_antenna",
            ),
            PcbRfModuleAntennaRequirement(
                id="angled-module",
                basis="Synthetic 30-degree module-local polygon",
                reference="U3",
                rf_feed_pad="U3.1",
                keepout=PcbRfAntennaKeepout(
                    name="SYNTHETIC_ANTENNA_KEEPOUT_ANGLED",
                    local_polygons=(
                        PcbRfAntennaPolygon(
                            outline_nm=(
                                (0, 0),
                                (3_000_000, 0),
                                (3_000_000, 1_000_000),
                                (0, 1_000_000),
                            )
                        ),
                    ),
                    layers=("F.Cu", "B.Cu"),
                    forbids_tracks=True,
                    forbids_vias=True,
                    forbids_pads=True,
                    forbids_zone_fills=True,
                    forbids_footprints=False,
                ),
                **module_identity,
                disposition="onboard_antenna",
            ),
        ),
    )
    netlist = NetlistContract(
        components={
            "U1": ComponentContract(
                value="Probe_Module",
                footprint="RF_Module:Probe_Module",
                part_id="RF-PROBE",
            ),
            "U2": ComponentContract(
                value="Probe_Module",
                footprint="RF_Module:Probe_Module",
                part_id="RF-PROBE",
            ),
            "U3": ComponentContract(
                value="Probe_Module",
                footprint="RF_Module:Probe_Module",
                part_id="RF-PROBE",
            ),
        },
        nets={"RF_FEED": ("U1.1", "U2.1", "U3.1")},
        component_symbols={
            "U1": "RF_Module:Probe_Module",
            "U2": "RF_Module:Probe_Module",
            "U3": "RF_Module:Probe_Module",
        },
    )
    rf_entries = pcb_rf_module_antenna_entries(requirements, netlist, snapshot)
    assert tuple(item.id for item in rf_entries) == (
        "angled-module",
        "back-module",
        "front-module",
    )
    assert all(item.status == "COMPLETE" for item in rf_entries)
    assert {item.id: item.observed_keepout_uuids for item in rf_entries} == {
        "angled-module": ("32345678-1234-5678-1234-567812345678",),
        "back-module": ("22345678-1234-5678-1234-567812345678",),
        "front-module": ("12345678-1234-5678-1234-567812345678",),
    }
