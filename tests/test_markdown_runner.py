"""Native Markdown dependency execution stays behind the installed package adapter."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from importlib.metadata import PackageNotFoundError, PackagePath
from pathlib import Path
from unittest.mock import Mock, patch

from kicad_tooling.markdown_check import executable, run


class MarkdownRunnerTests(unittest.TestCase):
    def test_distribution_record_resolves_unix_and_windows_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for name in ("rumdl", "rumdl.exe"):
                binary = base / name
                binary.touch()
                installed = Mock()
                installed.files = [PackagePath(f"../../../scripts/{name}"), PackagePath("rumdl/__init__.py")]
                installed.locate_file.return_value = binary
                with patch("kicad_tooling.markdown_check.distribution", return_value=installed) as lookup:
                    self.assertEqual(executable(), binary)
                lookup.assert_called_once_with("rumdl")
                installed.locate_file.assert_called_once_with(installed.files[0])

    def test_missing_or_ambiguous_metadata_has_no_path_search_fallback(self) -> None:
        for files in (None, [], [PackagePath("bin/rumdl"), PackagePath("Scripts/rumdl.exe")]):
            with self.subTest(files=files):
                installed = Mock(files=files)
                installed.locate_file.return_value = Path("/missing/rumdl")
                with (patch("kicad_tooling.markdown_check.distribution", return_value=installed),
                      self.assertRaisesRegex(ValueError, "exactly one")):
                    executable()
        with patch("kicad_tooling.markdown_check.distribution", side_effect=PackageNotFoundError("rumdl")):
            self.assertEqual(run(["--version"]), 127)

    def test_module_ignores_checkout_shadow_and_ambient_python_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            caller = Path(temporary)
            (caller / "kicad_tooling.py").write_text("raise RuntimeError('shadow import')\n")
            (caller / "rumdl").write_text("not the installed executable\n")
            result = subprocess.run((sys.executable, "-I", "-m", "kicad_tooling.markdown_check", "--version"),
                                    cwd=caller, env=os.environ | {"PYTHONPATH": str(caller), "PATH": str(caller)},
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "rumdl 0.2.77")
