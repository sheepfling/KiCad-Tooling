"""The installed tooling version is independent of the caller's project and policy."""

from __future__ import annotations

import contextlib
import io
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kicad_tooling import package_version
from kicad_tooling.__main__ import main
from kicad_tooling.hwrepo import __version__ as policy_version


def test_reads_distribution_metadata_without_conflating_policy_version() -> None:
    with (
        patch("kicad_tooling.distributions", return_value=()),
        patch("kicad_tooling.version", return_value="2.0.0") as metadata,
    ):
        assert package_version() == "2.0.0"
    metadata.assert_called_once_with("kicad-team-tooling")
    assert policy_version == "1.3.2"


def test_prefers_installed_dist_info_to_stale_checkout_egg_info() -> None:
    stale_checkout = SimpleNamespace(files=(Path("README.md"),), version="0.1.old")
    installed = SimpleNamespace(
        files=(Path("kicad_team_tooling-0.1.dist-info/METADATA"),),
        version="0.1.current",
    )
    with (
        patch("kicad_tooling.distributions", return_value=(stale_checkout, installed)),
        patch("kicad_tooling.version", side_effect=AssertionError("fallback used")),
    ):
        assert package_version() == "0.1.current"


def test_version_cli_does_not_require_a_project_checkout() -> None:
    output = io.StringIO()
    with (
        patch("sys.argv", ["kicad-team", "--version"]),
        patch("kicad_tooling.__main__.package_version", return_value="2.0.0"),
        contextlib.redirect_stdout(output),
    ):
        assert main() == 0
    assert output.getvalue() == "kicad-team-tooling 2.0.0\n"


def test_uninstalled_source_does_not_fabricate_a_version() -> None:
    error = io.StringIO()
    with (
        patch("sys.argv", ["kicad-team", "--version"]),
        patch(
            "kicad_tooling.__main__.package_version",
            side_effect=PackageNotFoundError("kicad-team-tooling"),
        ),
        contextlib.redirect_stderr(error),
    ):
        assert main() == 1
    assert "install kicad-team-tooling" in error.getvalue()
