"""Shared assertions for read-only native fixture command receipts."""

from __future__ import annotations

import json
from pathlib import Path


def assert_native_fixture_mounts(project_root: Path, command_receipt: str) -> None:
    """Require a fixture-only read mount and a separate writable output mount."""
    receipt = project_root / command_receipt
    assert receipt.is_file()
    command = json.loads(receipt.read_text(encoding="utf-8"))
    mounts = tuple(
        command["argv"][index + 1]
        for index, item in enumerate(command["argv"][:-1])
        if item == "-v"
    )
    assert len(mounts) == 2
    assert sum(item.endswith(":/fixtures:ro") for item in mounts) == 1
    assert sum(item.endswith(":/output:rw") for item in mounts) == 1
