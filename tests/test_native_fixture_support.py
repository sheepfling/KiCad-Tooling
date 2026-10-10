"""Regression tests for native fixture receipt safety assertions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.native_fixture_support import assert_native_fixture_mounts


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
