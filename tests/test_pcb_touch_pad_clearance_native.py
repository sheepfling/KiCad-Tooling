"""Exact-version KiCad acceptance for touch-pad-to-filled-zone measurements."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contract_coach import docker_prefix, pinned_image, run_command
from kicad_tooling.hwrepo.models import (
    ComponentIdentity,
    IgnoredChecks,
    PcbValidationContract,
    ProjectConfig,
    ProjectKind,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import read_native_pcb_drc_fixture_report
from kicad_tooling.hwrepo.pcb_return_path_capture import (
    capture_native_pcb_connectivity,
    expected_probe_sha256,
    native_pcb_command_matches,
)
from kicad_tooling.hwrepo.pcb_touch_pad_clearance import touch_pad_clearance_entries
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceMap,
    PcbTouchPadClearanceRequestSet,
)
from tests.pcb_touch_pad_clearance_support import native_pad_shapes_netlist, requirement

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]

FIXTURE = Path(__file__).parent / "fixtures/design_lint/pcb-touch-pad-clearance/board.kicad_pcb"
NATIVE_IMAGES = (
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
)


@pytest.mark.parametrize(("expected_version", "image"), NATIVE_IMAGES, ids=lambda value: value)
def test_native_measurement_is_bound_to_exact_pad_zone_and_authored_request(
    tmp_path: Path,
    expected_version: str,
    image: str,
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
        project_id="synthetic-touch-clearance",
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
    authored_requirements = (
        requirement(
            minimum_clearance_nm=1_500_000,
            requirement_id="J1-round-pad-clearance",
            pad="J1.1",
        ),
        requirement(
            minimum_clearance_nm=3_000_000,
            requirement_id="J1-oval-pad-clearance",
            pad="J1.2",
        ),
        requirement(
            minimum_clearance_nm=1_500_000,
            requirement_id="J1-horizontal-oval-clearance",
            pad="J1.3",
        ),
        requirement(
            minimum_clearance_nm=2_000_000,
            requirement_id="J1-rotated-oval-clearance",
            pad="J1.4",
        ),
        requirement(
            minimum_clearance_nm=1_500_000,
            requirement_id="J1-through-hole-fault-clearance",
            pad="J1.5",
        ),
        requirement(
            minimum_clearance_nm=1_000_000,
            requirement_id="J1-through-hole-boundary-clearance",
            pad="J1.6",
        ),
    )
    authored = PcbTouchPadClearanceMap(
        basis=(
            "Synthetic native fixture checks round, oval, rotated oval, and "
            "through-hole pads against ground fills"
        ),
        requirements=authored_requirements,
    )
    requests = PcbTouchPadClearanceRequestSet(requests=authored.requirements)

    command, observed = capture_native_pcb_connectivity(
        root,
        config,
        root / "build/tests/touch-pad-clearance" / expected_version,
        touch_pad_clearance_requests=requests,
    )

    assert command.returncode == 0, command.stderr or command.error
    assert observed is not None
    assert observed.kicad_version == expected_version
    assert observed.schema_version == "14"
    assert observed.probe_sha256 == expected_probe_sha256()
    assert native_pcb_command_matches(
        command,
        config,
        touch_pad_clearance_probes=True,
    )
    measurements = {item.pad: item for item in observed.touch_pad_clearance_observations}
    assert set(measurements) == {"J1.1", "J1.2", "J1.3", "J1.4", "J1.5", "J1.6"}
    for authored_requirement in authored_requirements:
        measurement = measurements[authored_requirement.pad]
        assert measurement.requirement_id == authored_requirement.id
        assert measurement.observed_pad_net == authored_requirement.expected_pad_net
        assert measurement.reference_net == authored_requirement.reference_net
        assert measurement.layer == authored_requirement.layer
        assert measurement.matching_zone_count == 5
        assert measurement.status == "MEASURED"
        assert measurement.closest_zone_uuid is not None
        assert measurement.distance_nm is not None

    # The two oval pads have matching center-to-zone-edge offsets. Rotating one
    # changes its horizontal half-extent by 0.5 mm, which must change the native
    # clearance by the same amount.
    assert measurements["J1.3"].closest_zone_uuid == "87654321-4321-8765-4321-876543210001"
    assert measurements["J1.4"].closest_zone_uuid == "87654321-4321-8765-4321-876543210002"
    assert measurements["J1.3"].distance_nm == 1_000_000
    assert measurements["J1.4"].distance_nm == 1_500_000
    assert measurements["J1.5"].closest_zone_uuid == "87654321-4321-8765-4321-876543210003"
    assert measurements["J1.5"].distance_nm == 1_000_000
    assert measurements["J1.6"].closest_zone_uuid == "87654321-4321-8765-4321-876543210004"
    assert measurements["J1.6"].distance_nm == 1_000_000

    entries = touch_pad_clearance_entries(authored, observed, native_pad_shapes_netlist())
    assert {item.pad for item in entries} == {
        "J1.1",
        "J1.2",
        "J1.3",
        "J1.4",
        "J1.5",
        "J1.6",
    }
    assert all(item.status == "COMPLETE" for item in entries)
    assert {item.pad for item in entries if item.violates_minimum_clearance} == {
        "J1.1",
        "J1.2",
        "J1.3",
        "J1.4",
        "J1.5",
    }
    assert {item.pad for item in entries if not item.violates_minimum_clearance} == {"J1.6"}

    # Confirm native DRC reports no clearance issue for the same board while
    # the authored minima produce lint candidates from exact pad geometry.
    drc_output = root / "build/tests/touch-pad-clearance-drc" / expected_version
    drc_output.mkdir(parents=True)
    drc_reports = []
    for run in ("first", "repeat"):
        drc_argv = (
            *docker_prefix(),
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m",
            "-v",
            f"{board.parent.resolve()}:/project:ro",
            "-v",
            f"{drc_output.resolve()}:/reports:rw",
            pinned_image(image),
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--exit-code-violations",
            "--output",
            f"/reports/drc.{run}.json",
            "/project/board.kicad_pcb",
        )
        drc_command = run_command(root, drc_argv, timeout=600)
        assert drc_command.returncode in {0, 5}, drc_command.stderr or drc_command.error
        drc_reports.append(read_native_pcb_drc_fixture_report(drc_output / f"drc.{run}.json"))

    first_drc, repeat_drc = drc_reports
    assert first_drc.kicad_version == expected_version
    assert repeat_drc.kicad_version == expected_version
    assert Path(first_drc.source).name == board.name
    assert Path(repeat_drc.source).name == board.name
    assert "clearance" not in first_drc.violation_types, first_drc.violation_types
    assert (first_drc.violation_types, first_drc.violation_records_sha256) == (
        repeat_drc.violation_types,
        repeat_drc.violation_records_sha256,
    )
