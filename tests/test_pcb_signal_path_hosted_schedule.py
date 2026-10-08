"""Pytest coverage for scheduling the signal-path native fixture lane."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import kicad_tooling.ci_hosted as hosted
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.synthetic_design_lint_project import synthetic_design_lint_project


@pytest.mark.skipif(
    sys.platform == "win32", reason="Hosted native orchestration uses a Unix runner"
)
def test_native_lane_schedules_pcb_signal_path_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        kicad_version="10.0.5",
    )
    for args in (
        ("init", "-q"),
        ("config", "gc.auto", "0"),
        ("config", "maintenance.auto", "false"),
        ("add", "--all"),
    ):
        subprocess.run(("git", "-C", str(root), *args), check=True, capture_output=True)
    subprocess.run(
        (
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Synthetic source",
        ),
        check=True,
        capture_output=True,
    )

    log = hosted.HostedLog(root, "native")
    monkeypatch.setattr(log, "run", Mock())
    fixture_names = (
        "connector_return_lint_fixture_lane",
        "usb_data_path_fixture_lane",
        "power_path_fixture_lane",
        "stm32_pin_map_fixture_lane",
        "led_rail_fixture_lane",
        "two_pin_component_fixture_lane",
        "component_peer_power_output_fixture_lane",
        "component_rating_fixtures_lane",
        "power_sequence_fixture_lane",
        "ic_rail_capacitor_fixture_lane",
        "pcb_return_fixture_lane",
        "pcb_access_fixture_lane",
        "pcb_decoupling_fixture_lane",
        "pcb_switching_loop_fixture_lane",
        "pcb_reference_plane_via_fixture_lane",
        "pcb_reference_plane_narrow_void_fixture_lane",
    )
    for name in fixture_names:
        monkeypatch.setattr(hosted, name, Mock())
    signal_path_fixture = Mock()
    monkeypatch.setattr(hosted, "pcb_signal_path_drc_fixture_lane", signal_path_fixture)
    monkeypatch.setattr(
        hosted,
        "electrical_lane",
        Mock(side_effect=RuntimeError("Synthetic stop after fixture lanes")),
    )

    image = selected_config(root, "controller").image
    with pytest.raises(RuntimeError, match="Synthetic stop after fixture lanes"):
        hosted.native_lane(
            root,
            project="controller",
            image=image,
            pr_head="",
            fault_probes=True,
            log=log,
        )

    signal_path_fixture.assert_called_once_with(
        root,
        project="controller",
        image=image,
        log=log,
    )
