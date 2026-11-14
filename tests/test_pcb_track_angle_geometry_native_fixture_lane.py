"""Digest-pinned KiCad snapshots for the mapped track-angle geometry cross-check."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.contracts import repo_path
from kicad_tooling.hwrepo.design_lint_pcb_geometry_capture import capture_pcb_geometry_source
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.pcb_drc_rule_parser import read_native_pcb_drc_fixture_report
from kicad_tooling.hwrepo.pcb_return_path_capture import capture_native_pcb_connectivity_result
from kicad_tooling.hwrepo.pcb_track_angle_geometry import track_angle_geometry_violations
from kicad_tooling.hwrepo.pcb_track_angle_models import (
    PcbTrackAngleMap,
    PcbTrackAngleRequirement,
)
from kicad_tooling.hwrepo.pcb_track_angle_unmapped_geometry import (
    unmapped_acute_track_corner_candidates,
)
from kicad_tooling.hwrepo.project_source_hashes import hash_project_sources
from tests.native_kicad_support import execute_kicad_cli
from tests.pcb_native_fixture_support import NATIVE_KICAD_PROJECTS, copy_reference_checkout

RULE_ID = "pcb.track_angle_geometry_review"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-track-angle"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_TRACK_ANGLE_GEOMETRY_FIXTURES") != "1",
        reason="track-angle geometry snapshots require digest-pinned KiCad containers",
    ),
]


def _angle_map() -> PcbTrackAngleMap:
    return PcbTrackAngleMap(
        basis="Tooling-owned synthetic geometry acceptance",
        requirements=(
            PcbTrackAngleRequirement(
                id="clock-output",
                basis="Synthetic minimum for the native fault/control fixture",
                net="CLOCK_OUT",
                rule_name="clock-track-angle",
                minimum_degrees=150,
            ),
        ),
    )


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS, ids=lambda value: value)
def test_native_snapshot_angle_matches_synthetic_fault_and_control(
    tmp_path: Path, project: str, version: str
) -> None:
    requirement = _angle_map()
    observations = {}
    for case in ("fault", "control"):
        root = copy_reference_checkout(tmp_path / case)
        config = selected_config(root, project)
        assert config.kicad_version == version
        board = repo_path(root, config.project).with_suffix(".kicad_pcb")
        shutil.copyfile(FIXTURES / f"{case}.kicad_pcb", board)
        output = root / "build" / "track-angle-geometry" / project / case
        capture = capture_native_pcb_connectivity_result(root, config, output)
        assert capture.command.error is None, capture.command.model_dump_json(indent=2)
        assert capture.command.returncode == 0, capture.command.model_dump_json(indent=2)
        assert capture.snapshot is not None
        observations[case] = track_angle_geometry_violations(requirement, capture.snapshot)

    assert len(observations["fault"]) == 1
    assert observations["fault"][0].angle_millidegrees == 135_000
    assert observations["fault"][0].requirement.net == "CLOCK_OUT"
    assert observations["control"] == ()


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS, ids=lambda value: value)
@pytest.mark.design_lint_rule(rule_id="pcb.unmapped_acute_track_corner_review")
def test_native_acute_corner_is_found_without_explicit_angle_rule(
    tmp_path: Path, project: str, version: str
) -> None:
    observations = {}
    drc_observations = {}
    for case, fixture_name in (("fault", "acute-unmapped"), ("control", "control")):
        root = copy_reference_checkout(tmp_path / f"{project}-{case}")
        config = selected_config(root, project)
        assert config.kicad_version == version
        board = repo_path(root, config.project).with_suffix(".kicad_pcb")
        shutil.copyfile(FIXTURES / f"{fixture_name}.kicad_pcb", board)
        shutil.copyfile(FIXTURES / "board.kicad_pro", board.with_suffix(".kicad_pro"))
        shutil.copyfile(FIXTURES / "no-angle.kicad_dru", board.with_suffix(".kicad_dru"))

        source_hashes = hash_project_sources(root, config.source_roots)
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=config.project_id,
            project_kind=config.kind,
            source_hashes=source_hashes,
            netlist_sha256="a" * 64,
        )
        evidence = capture_pcb_geometry_source(
            root,
            config,
            coach,
            root / "build" / "design-lint" / "acute-track-corner" / case,
        )
        candidates = unmapped_acute_track_corner_candidates(None, evidence, "a" * 64)
        observations[case] = tuple(item.evidence["measured_angle_degrees"] for item in candidates)

        report_types = []
        for repetition in ("first", "repeat"):
            output = tmp_path / f"{project}-{case}-drc-{repetition}"
            output.mkdir()
            report = output / "report.json"
            command = execute_kicad_cli(
                config.image,
                (
                    "kicad-cli",
                    "pcb",
                    "drc",
                    "--format",
                    "json",
                    "--severity-all",
                    "--exit-code-violations",
                    "--output",
                    str(report),
                    str(board),
                ),
                root,
                home_directory=f"acute-track-corner-{project}-{case}-{repetition}",
                fixture_directory=root,
                output_directory=output,
            )
            assert command.error is None, command.model_dump_json(indent=2)
            assert command.returncode in {0, 5}, command.model_dump_json(indent=2)
            observed = read_native_pcb_drc_fixture_report(report)
            assert observed.kicad_version == version
            report_types.append(observed.violation_types)
        drc_observations[case] = tuple(report_types)

    assert observations["fault"] == (("45.000",),)
    assert observations["control"] == ()
    for reports in drc_observations.values():
        assert reports[0] == reports[1]
        assert "track_angle" not in reports[0]
