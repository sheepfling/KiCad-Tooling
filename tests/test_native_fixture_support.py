"""Regression tests for native fixture receipt safety assertions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.pcb_native_fixture_support import lane_event


def test_native_fixture_receipt_accepts_separate_read_only_inputs_and_outputs(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "build/command.json"
    receipt.parent.mkdir()
    receipt.write_text(
        json.dumps(
            {
                "argv": [
                    "docker",
                    "run",
                    "-v",
                    "/synthetic/fixtures:/fixtures:ro",
                    "-v",
                    "/synthetic/output:/output:rw",
                ]
            }
        ),
        encoding="utf-8",
    )

    assert_native_fixture_mounts(tmp_path, "build/command.json")


@pytest.mark.parametrize(
    "mounts",
    (
        pytest.param(("/synthetic/fixtures:/fixtures:rw", "/synthetic/output:/output:rw")),
        pytest.param(("/synthetic/fixtures:/fixtures:ro", "/synthetic/output:/output:ro")),
        pytest.param(
            (
                "/synthetic/fixtures:/fixtures:ro",
                "/synthetic/output:/output:rw",
                "/synthetic/extra:/extra:rw",
            )
        ),
    ),
)
def test_native_fixture_receipt_rejects_writable_inputs_or_unbounded_mounts(
    tmp_path: Path, mounts: tuple[str, ...]
) -> None:
    receipt = tmp_path / "build/command.json"
    receipt.parent.mkdir()
    receipt.write_text(
        json.dumps({"argv": ["docker", "run", *sum((("-v", item) for item in mounts), ())]}),
        encoding="utf-8",
    )

    with pytest.raises(AssertionError):
        assert_native_fixture_mounts(tmp_path, "build/command.json")


def test_lane_event_selects_a_terminal_status_after_start(tmp_path: Path) -> None:
    log = HostedLog(tmp_path, "synthetic-native-lane")
    log.event("native-export", "START")
    log.event("native-export", "PASS", fixture_count=2)

    event = lane_event(log, "native-export", status="PASS")

    assert event["fixture_count"] == 2
    with pytest.raises(AssertionError):
        lane_event(log, "native-export")
