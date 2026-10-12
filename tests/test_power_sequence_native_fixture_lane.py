"""Exact-version native exports for mapped power-sequence fault controls."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, power_sequence_fixture_lane
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]

_NATIVE_FIXTURE_SOURCES = {
    "control": "f1104387c9208d6be6a608872ddc9425158b05572d351e4afbd80d72a2f447c3",
    "open-enable": "b093d3b7b7b57f7a8aa3e1fa86b4c7c6b3440ebc6c3ee5d5c4a15ee4818f99fb",
    "output-enable-cycle": "da22daa43ad104bdce3e499d651c36b5a0ed6556cd75347a07eed5a21ea22c6d",
}


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES") != "1",
    reason="native power-sequence exports run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version", "image"),
    (
        pytest.param(
            "controller",
            "10.0.0",
            "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            id="controller-kicad-10-0-0",
        ),
        pytest.param(
            "raspberry-pi-status-led",
            "10.0.5",
            "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
            id="raspberry-pi-status-led-kicad-10-0-5",
        ),
    ),
)
def test_control_fault_and_cycle_repeat_on_pinned_kicad_versions(
    project: str,
    version: str,
    image: str,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    acceptance = repository / "build/ci"
    acceptance.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="native-power-sequence-project-", dir=acceptance))
    shutil.copytree(
        reference_root(),
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    fixture_root = repository / "tests/fixtures/design_lint/power-sequence-native"
    assert {
        case: hashlib.sha256((fixture_root / f"{case}.kicad_sch").read_bytes()).hexdigest()
        for case in _NATIVE_FIXTURE_SOURCES
    } == _NATIVE_FIXTURE_SOURCES

    from kicad_tooling.hwrepo.electrical import selected_config

    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(root, f"native-power-sequence-{project}")
    power_sequence_fixture_lane(root, project=project, image=image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("power-sequence-fixture/")
    }
    assert set(results) == {
        "power-sequence-fixture/native-export",
        "power-sequence-fixture/control",
        "power-sequence-fixture/open-enable",
        "power-sequence-fixture/output-enable-cycle",
    }
    native = results["power-sequence-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["repeatable"] == "true"
    assert native["repeatability_basis"] == "canonical_native_netlist"
    assert native["source_hashes"] == ",".join(
        f"{case}:{digest}" for case, digest in _NATIVE_FIXTURE_SOURCES.items()
    )
    assert results["power-sequence-fixture/control"]["lint_status"] == "PASS"
    assert results["power-sequence-fixture/open-enable"]["lint_status"] == "REVIEW"
    cycle = results["power-sequence-fixture/output-enable-cycle"]
    assert cycle["lint_status"] == "REVIEW"
    assert cycle["observed_enable_cycle_stages"] == "rail-a,rail-b"
    for case, digest in _NATIVE_FIXTURE_SOURCES.items():
        result = results[f"power-sequence-fixture/{case}"]
        assert result["source_sha256"] == digest
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
    receipt = root / native["command_receipt"]
    assert receipt.is_file()
    command = json.loads(receipt.read_text())
    mounts = tuple(
        command["argv"][index + 1]
        for index, item in enumerate(command["argv"][:-1])
        if item == "-v"
    )
    assert len(mounts) == 2
    assert sum(item.endswith(":/fixtures:ro") for item in mounts) == 1
    assert sum(item.endswith(":/output:rw") for item in mounts) == 1
