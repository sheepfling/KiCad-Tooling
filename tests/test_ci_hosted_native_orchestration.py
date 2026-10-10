"""Synthetic hosted-lane orchestration failure guards."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import DEFAULT, patch

import pytest

from kicad_tooling.ci_hosted import HostedLog, native_lane
from tests.support import initialize_git, reference_root

pytestmark = [pytest.mark.template_checkout, pytest.mark.design_lint]


@pytest.mark.skipif(
    sys.platform == "win32", reason="Hosted native orchestration uses a Unix runner"
)
def test_native_lane_cannot_pass_when_declared_electrical_fails(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    initialize_git(root)
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
    log = HostedLog(root, "native")
    with (
        patch.object(log, "run") as run,
        patch(
            "kicad_tooling.ci_hosted.connector_return_lint_fixture_lane"
        ) as connector_return_fixture,
        patch("kicad_tooling.ci_hosted.usb_data_path_fixture_lane") as usb_fixture,
        patch("kicad_tooling.ci_hosted.power_path_fixture_lane") as power_path_fixture,
        patch("kicad_tooling.ci_hosted.stm32_pin_map_fixture_lane") as stm32_fixture,
        patch("kicad_tooling.ci_hosted.led_rail_fixture_lane") as led_fixture,
        patch("kicad_tooling.ci_hosted.two_pin_component_fixture_lane") as component_fixture,
        patch(
            "kicad_tooling.ci_hosted.component_peer_power_output_fixture_lane"
        ) as peer_power_fixture,
        patch("kicad_tooling.ci_hosted.component_rating_fixtures_lane") as voltage_rating_fixture,
        patch("kicad_tooling.ci_hosted.power_sequence_fixture_lane") as sequence_fixture,
        patch("kicad_tooling.ci_hosted.ic_rail_capacitor_fixture_lane") as rail_cap_fixture,
        patch.multiple(
            "kicad_tooling.ci_hosted",
            pcb_signal_path_drc_fixture_lane=DEFAULT,
            component_peer_power_assignment_fixture_lane=DEFAULT,
            component_peer_signal_input_fixture_lane=DEFAULT,
            component_peer_signal_output_fixture_lane=DEFAULT,
            component_peer_bidirectional_fixture_lane=DEFAULT,
        ) as other_native_fixtures,
        patch("kicad_tooling.ci_hosted.pcb_return_fixture_lane") as pcb_fixture,
        patch("kicad_tooling.ci_hosted.pcb_access_fixture_lane") as access_fixture,
        patch("kicad_tooling.ci_hosted.pcb_decoupling_fixture_lane") as decoupling_fixture,
        patch("kicad_tooling.ci_hosted.pcb_switching_loop_fixture_lane") as switching_loop_fixture,
        patch(
            "kicad_tooling.ci_hosted.pcb_reference_plane_via_fixture_lane"
        ) as reference_plane_fixture,
        patch(
            "kicad_tooling.ci_hosted.pcb_reference_plane_narrow_void_fixture_lane"
        ) as narrow_void_fixture,
        patch(
            "kicad_tooling.ci_hosted.electrical_lane",
            side_effect=RuntimeError("Electrical measurement failed"),
        ) as electrical,
        pytest.raises(RuntimeError, match="Electrical measurement failed"),
    ):
        native_lane(
            root,
            project="controller",
            image="fixture@sha256:" + "a" * 64,
            pr_head="",
            fault_probes=True,
            log=log,
        )
    expected_kwargs = {
        "project": "controller",
        "image": "fixture@sha256:" + "a" * 64,
        "log": log,
    }
    electrical.assert_called_once_with(
        root, "controller", log, native_summary="build/review/controller/summary.json"
    )
    for fixture in (
        connector_return_fixture,
        usb_fixture,
        power_path_fixture,
        stm32_fixture,
        led_fixture,
        component_fixture,
        peer_power_fixture,
        other_native_fixtures["component_peer_power_assignment_fixture_lane"],
        other_native_fixtures["component_peer_signal_output_fixture_lane"],
        other_native_fixtures["component_peer_signal_input_fixture_lane"],
        other_native_fixtures["component_peer_bidirectional_fixture_lane"],
        voltage_rating_fixture,
        sequence_fixture,
        rail_cap_fixture,
        pcb_fixture,
        access_fixture,
        decoupling_fixture,
        switching_loop_fixture,
        reference_plane_fixture,
        narrow_void_fixture,
    ):
        fixture.assert_called_once_with(root, **expected_kwargs)
    stages = [call.args[0] for call in run.call_args_list]
    assert "native-check" in stages
    assert "fault-probes" not in stages
    assert stages[-2:] == ["source-diff", "index-diff"]
