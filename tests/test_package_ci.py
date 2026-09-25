"""Package gates use installed module entry points, never executable overrides."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import ci


class PackageCiTests(unittest.TestCase):
    def test_markdown_check_is_an_isolated_module(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="package-ci-module-") as temporary,
            patch.object(ci, "ROOT", Path(temporary)),
            patch.object(ci.sys, "argv", ["scripts/ci.py"]),
            patch.object(ci, "stage") as stage,
            patch.object(ci, "build_distributions", side_effect=StopIteration("after checks")),
            self.assertRaisesRegex(StopIteration, "after checks"),
        ):
            stage.return_value.stdout = str(Path(temporary) / "kicad_tooling/__init__.py")
            ci.main()
        commands = {call.args[0]: call.args[1] for call in stage.call_args_list}
        self.assertEqual(commands["rumdl"],
                         (sys.executable, "-I", "-m", "kicad_tooling.markdown_check",
                          "check", ".", "--no-cache"))

    def test_stale_install_is_rejected_before_regressions(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="package-ci-install-") as temporary,
            patch.object(ci, "ROOT", Path(temporary)),
            patch.object(ci.sys, "argv", ["scripts/ci.py"]),
            patch.object(ci, "stage") as stage,
        ):
            stage.return_value.stdout = str(Path(temporary) / "other/kicad_tooling/__init__.py")
            self.assertEqual(ci.main(), 1)
        self.assertEqual([call.args[0] for call in stage.call_args_list], ["development-install"])
