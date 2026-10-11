"""Synthetic hosted-lane orchestration failure guards."""

from __future__ import annotations

import shutil
import subprocess
import sys
from contextlib import ExitStack
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
    fixture_symbols = (
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
        "pcb_component_inventory_fixture_lane",
        "pcb_decoupling_fixture_lane",
        "pcb_switching_loop_fixture_lane",
        "pcb_reference_plane_via_fixture_lane",
        "pcb_reference_plane_narrow_void_fixture_lane",
    )
    with ExitStack() as stack:
        run = stack.enter_context(patch.object(log, "run"))
        fixture_mocks = {
            name: stack.enter_context(patch(f"kicad_tooling.ci_hosted.{name}"))
            for name in fixture_symbols
        }
        other_native_fixtures = stack.enter_context(
            patch.multiple(
                "kicad_tooling.ci_hosted",
                pcb_signal_path_drc_fixture_lane=DEFAULT,
                component_peer_power_assignment_fixture_lane=DEFAULT,
                component_peer_signal_input_fixture_lane=DEFAULT,
                component_peer_signal_output_fixture_lane=DEFAULT,
                component_peer_bidirectional_fixture_lane=DEFAULT,
            )
        )
        electrical = stack.enter_context(
            patch(
                "kicad_tooling.ci_hosted.electrical_lane",
                side_effect=RuntimeError("Electrical measurement failed"),
            )
        )
        stack.enter_context(pytest.raises(RuntimeError, match="Electrical measurement failed"))
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
        *fixture_mocks.values(),
        other_native_fixtures["component_peer_power_assignment_fixture_lane"],
        other_native_fixtures["component_peer_signal_output_fixture_lane"],
        other_native_fixtures["component_peer_signal_input_fixture_lane"],
        other_native_fixtures["component_peer_bidirectional_fixture_lane"],
    ):
        fixture.assert_called_once_with(root, **expected_kwargs)
    stages = [call.args[0] for call in run.call_args_list]
    assert "native-check" in stages
    assert "fault-probes" not in stages
    assert stages[-2:] == ["source-diff", "index-diff"]
