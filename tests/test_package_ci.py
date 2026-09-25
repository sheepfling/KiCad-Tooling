"""Checks for package CI orchestration independent of native project fixtures."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import ci


class PackageCiTests(unittest.TestCase):
    def test_markdown_default_uses_active_python_scripts_directory(self) -> None:
        for platform, scripts, executable in (
            ("win32", "C:/hostedtoolcache/windows/Python/3.11.9/x64/Scripts", "rumdl.exe"),
            ("win32", "C:/work/venv/Scripts", "rumdl.exe"),
            ("linux", "/opt/venv/bin", "rumdl"),
        ):
            with self.subTest(platform=platform, scripts=scripts):
                self.assert_rumdl_command(platform, scripts, (), str(Path(scripts) / executable))

    def test_explicit_markdown_tool_override_is_preserved(self) -> None:
        override = str(Path("custom tools") / "rumdl-custom")
        self.assert_rumdl_command("linux", "/opt/venv/bin", ("--rumdl-path", override), override)

    def assert_rumdl_command(self, platform: str, scripts: str,
                             arguments: tuple[str, ...], expected: str) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="package-ci-path-") as temporary,
            patch.object(ci, "ROOT", Path(temporary)),
            patch.object(ci.sys, "argv", ["scripts/ci.py", *arguments]),
            patch.object(ci.sys, "platform", platform),
            patch.object(ci.sysconfig, "get_path", return_value=scripts) as lookup,
            patch.object(ci, "stage") as stage,
            patch.object(ci, "build_distributions", side_effect=StopIteration("after checks")),
            self.assertRaisesRegex(StopIteration, "after checks"),
        ):
            ci.main()
        lookup.assert_called_once_with("scripts")
        commands = {call.args[0]: call.args[1] for call in stage.call_args_list}
        self.assertEqual(commands["rumdl"], (expected, "check", ".", "--no-cache"))


if __name__ == "__main__":
    unittest.main()
