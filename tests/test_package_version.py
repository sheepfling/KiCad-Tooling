"""The installed tooling version is independent of the caller's project and policy."""
from __future__ import annotations

import contextlib
import io
import unittest
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

from kicad_tooling import package_version
from kicad_tooling.__main__ import main
from kicad_tooling.hwrepo import __version__ as policy_version


class PackageVersionTest(unittest.TestCase):
    def test_reads_distribution_metadata_without_conflating_policy_version(self) -> None:
        with patch("kicad_tooling.version", return_value="2.0.0") as metadata:
            self.assertEqual("2.0.0", package_version())
        metadata.assert_called_once_with("kicad-team-tooling")
        self.assertEqual("1.3.2", policy_version)

    def test_version_cli_does_not_require_a_project_checkout(self) -> None:
        output = io.StringIO()
        with patch("sys.argv", ["kicad-team", "--version"]), \
                patch("kicad_tooling.__main__.package_version", return_value="2.0.0"), \
                contextlib.redirect_stdout(output):
            self.assertEqual(0, main())
        self.assertEqual("kicad-team-tooling 2.0.0\n", output.getvalue())

    def test_uninstalled_source_does_not_fabricate_a_version(self) -> None:
        error = io.StringIO()
        with patch("sys.argv", ["kicad-team", "--version"]), \
                patch("kicad_tooling.__main__.package_version",
                      side_effect=PackageNotFoundError("kicad-team-tooling")), \
                contextlib.redirect_stderr(error):
            self.assertEqual(1, main())
        self.assertIn("install kicad-team-tooling", error.getvalue())


if __name__ == "__main__":
    unittest.main()
