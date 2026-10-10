"""Digest-pinned native acceptance for synthetic PCB probe-envelope checks."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, pcb_access_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
    reason="native PCB fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_probe_envelope_fixtures_on_supported_images(
    tmp_path: Path, project: str, version: str
) -> None:
    root = tmp_path / "reference"
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-access-{project}")
    pcb_access_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    result = next(
        item for item in events if item.get("stage") == "pcb-access-fixture/probe-envelope"
    )
    assert result["status"] == "PASS"
    assert result["kicad_version"] == version
    assert result["repeatable"] == "true"
