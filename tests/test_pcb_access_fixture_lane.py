"""Synthetic orchestration checks for the PCB access native fixture lane."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted import HostedLog, pcb_access_fixture_lane
from kicad_tooling.hwrepo import electrical
from kicad_tooling.hwrepo import pcb_return_path_capture as pcb_capture
from tests.pcb_access_fixture_support import capture_synthetic_access_probe

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.template_checkout,
]


def test_probe_envelope_fixture_uses_repeatable_source_bound_requests(
    hosted_reference_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = hosted_reference_root
    config = electrical.selected_config(root, "controller")
    captured: list[tuple[Path, tuple[tuple[str, str], ...]]] = []

    def capture(root: Path, selected, output: Path, requests):
        command, snapshot, board = capture_synthetic_access_probe(
            root,
            selected,
            output,
            requests,
        )
        captured.append(
            (board, tuple((request.endpoint, request.side) for request in requests.requests))
        )
        return command, snapshot

    monkeypatch.setattr(pcb_capture, "capture_native_pcb_connectivity", capture)
    log = HostedLog(root, "native-pcb-access-fixture")
    pcb_access_fixture_lane(root, project="controller", image=config.image, log=log)

    assert len(captured) == 2
    assert captured[0][0].read_bytes() == captured[1][0].read_bytes()
    assert captured[0][1] == captured[1][1]
    assert set(captured[0][1]) == {
        ("J1.1", "front"),
        ("J1.1", "back"),
        ("J7.1", "front"),
        ("J9.1", "front"),
        ("J9.1", "back"),
        ("J11.1", "front"),
        ("J12.1", "front"),
        ("J13.1", "front"),
        ("J14.1", "front"),
    }
    result = next(
        json.loads(line)
        for line in log.events.read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("stage") == "pcb-access-fixture/probe-envelope"
    )
    assert result["status"] == "PASS"
    assert result["kicad_version"] == config.kicad_version
    assert result["repeatable"] == "true"
    assert (root / result["receipt"]).is_relative_to(root)


def test_unsupported_kicad_minor_fails_before_native_access(tmp_path: Path, monkeypatch) -> None:
    image = "fixture.invalid/kicad@sha256:" + "a" * 64
    config = SimpleNamespace(image=image, kicad_version="10.0.6")
    monkeypatch.setattr(electrical, "selected_config", lambda root, project: config)
    monkeypatch.setattr(
        pcb_capture,
        "capture_native_pcb_connectivity",
        lambda *args, **kwargs: pytest.fail("unsupported version reached native capture"),
    )
    log = SimpleNamespace(directory=tmp_path)

    with pytest.raises(ValueError, match="do not cover KiCad 10.0.6"):
        pcb_access_fixture_lane(tmp_path, project="synthetic", image=image, log=log)
