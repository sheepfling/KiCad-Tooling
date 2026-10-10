"""Unit checks for the async runner used by pytest parity functions."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

pytestmark = pytest.mark.parity_lint


def test_async_parity_runner_cleans_up_temporary_workspace(tmp_path: Path) -> None:
    captured: dict[str, Path] = {}

    class ProbeCase(McpParityHarness):
        def setUp(self) -> None:
            self.temporary = tempfile.TemporaryDirectory(dir=tmp_path)

        async def exercise(self) -> None:
            self.assertEqual(2 + 2, 4)
            with self.subTest(value="synthetic"):
                self.assertTrue(True)
            captured["workspace"] = Path(self.temporary.name)

    run_mcp_parity(ProbeCase, "exercise")

    assert not captured["workspace"].exists()
