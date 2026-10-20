"""Native PCB geometry capture inside the already pinned KiCad container."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    DesignLintPolicy,
    PcbAccessProbeRequest,
    PcbAccessProbeRequestSet,
)
from kicad_tooling.hwrepo.native_container_context import NATIVE_CONTAINER_IMAGE_ENV
from kicad_tooling.hwrepo.pcb_connectivity_observations import PcbAccessProbeObservation
from kicad_tooling.hwrepo.pcb_return_path_capture import (
    capture_native_pcb_connectivity,
    native_pcb_command_matches,
)
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceObservation,
    PcbTouchPadClearanceRequestSet,
    PcbTouchPadClearanceRequirement,
)
from tests.design_lint_fixtures.pcb_component_inventory import snapshot
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_geometry_probe_uses_current_pinned_container_without_nested_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    config = load_config(root, "projects/controller/project.json")
    board = (root / config.project).with_suffix(".kicad_pcb")
    output = root / "build/design-lint/pcb-geometry-0123456789ab"
    observed = snapshot("R1", schema_version="13").model_copy(
        update={"board_sha256": digest(board)}
    )
    calls: list[tuple[str, ...]] = []

    def run_probe(_root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert timeout == 600
        calls.append(argv)
        (output / "snapshot.json").write_text(observed.model_dump_json(), encoding="utf-8")
        return CommandEvidence(argv=argv, started_utc="synthetic fixture", returncode=0)

    monkeypatch.setenv(NATIVE_CONTAINER_IMAGE_ENV, config.image)
    monkeypatch.setattr("kicad_tooling.hwrepo.pcb_return_path_capture.run_command", run_probe)

    command, captured = capture_native_pcb_connectivity(root, config, output)

    assert len(calls) == 1
    assert calls[0][:5] == (
        "/usr/bin/env",
        f"{NATIVE_CONTAINER_IMAGE_ENV}={config.image}",
        "/usr/bin/python3",
        "-I",
        "-B",
    )
    assert calls[0][6] == f"/work/{Path(config.project).with_suffix('.kicad_pcb').as_posix()}"
    assert calls[0][7].endswith("/snapshot.json")
    assert captured is not None
    assert captured.kicad_version == config.kicad_version
    assert captured.board_sha256 == digest(board)
    assert captured.image == config.image
    assert native_pcb_command_matches(command, config)

    forged = command.model_copy(
        update={
            "argv": (
                command.argv[0],
                f"{NATIVE_CONTAINER_IMAGE_ENV}=other@sha256:{'b' * 64}",
                *command.argv[2:],
            )
        }
    )
    assert not native_pcb_command_matches(forged, config)


def test_geometry_probe_rejects_a_container_marker_for_another_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    config = load_config(root, "projects/controller/project.json")
    monkeypatch.setenv(NATIVE_CONTAINER_IMAGE_ENV, "other@sha256:" + "b" * 64)

    with pytest.raises(ValueError, match="marker differs from the project's pinned image"):
        capture_native_pcb_connectivity(root, config, root / "build/tests/wrong-image")


def test_in_container_probe_binds_optional_access_and_touch_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    config = load_config(root, "projects/controller/project.json")
    board = (root / config.project).with_suffix(".kicad_pcb")
    output = root / "build/design-lint/pcb-geometry-abcdef012345"
    access = PcbAccessProbeRequestSet(
        requests=(PcbAccessProbeRequest(endpoint="R1.1", net="SIGNAL", side="front"),)
    )
    touch = PcbTouchPadClearanceRequestSet(
        requests=(
            PcbTouchPadClearanceRequirement(
                id="signal-pad-clearance",
                pad="R1.1",
                expected_pad_net="SIGNAL",
                reference_net="GND",
                layer="F.Cu",
                minimum_clearance_nm=1_000_000,
            ),
        )
    )
    calls: list[tuple[str, ...]] = []

    def run_probe(_root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert timeout == 600
        calls.append(argv)
        observed = snapshot(
            "R1", schema_version="14", pad_net_by_reference={"R1.1": "SIGNAL"}
        ).model_copy(
            update={
                "board_sha256": digest(board),
                "access_probe_requests_sha256": digest(output / "access-probe-requests.json"),
                "access_probe_observations": (
                    PcbAccessProbeObservation(
                        endpoint="R1.1",
                        side="front",
                        target_net="SIGNAL",
                        target_exposed=True,
                        obstacle=None,
                        obstacle_net=None,
                        distance_nm=None,
                    ),
                ),
                "touch_pad_clearance_requests_sha256": digest(
                    output / "touch-pad-clearance-requests.json"
                ),
                "touch_pad_clearance_observations": (
                    PcbTouchPadClearanceObservation(
                        requirement_id="signal-pad-clearance",
                        pad="R1.1",
                        expected_pad_net="SIGNAL",
                        observed_pad_net="SIGNAL",
                        reference_net="GND",
                        layer="F.Cu",
                        matching_zone_count=0,
                        closest_zone_uuid=None,
                        distance_nm=None,
                        status="NO_REFERENCE_ZONE",
                    ),
                ),
            }
        )
        (output / "snapshot.json").write_text(observed.model_dump_json(), encoding="utf-8")
        return CommandEvidence(argv=argv, started_utc="synthetic fixture", returncode=0)

    monkeypatch.setenv(NATIVE_CONTAINER_IMAGE_ENV, config.image)
    monkeypatch.setattr("kicad_tooling.hwrepo.pcb_return_path_capture.run_command", run_probe)

    command, captured = capture_native_pcb_connectivity(
        root,
        config,
        output,
        access_probe_requests=access,
        touch_pad_clearance_requests=touch,
    )

    assert captured is not None
    assert calls[0][8:] == (
        "/work/build/design-lint/pcb-geometry-abcdef012345/access-probe-requests.json",
        "/work/build/design-lint/pcb-geometry-abcdef012345/touch-pad-clearance-requests.json",
    )
    assert native_pcb_command_matches(
        command,
        config,
        access_probes=True,
        touch_pad_clearance_probes=True,
    )
