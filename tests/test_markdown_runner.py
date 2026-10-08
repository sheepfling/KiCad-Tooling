"""Native Markdown dependency execution stays behind the installed package adapter."""

from __future__ import annotations

import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, PackagePath
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kicad_tooling.markdown_check import executable, run


@pytest.mark.parametrize("name", ("rumdl", "rumdl.exe"))
def test_distribution_record_resolves_unix_and_windows_binaries(tmp_path: Path, name: str) -> None:
    binary = tmp_path / name
    binary.touch()
    installed = Mock()
    installed.files = [
        PackagePath(f"../../../scripts/{name}"),
        PackagePath("rumdl/__init__.py"),
    ]
    installed.locate_file.return_value = binary
    with patch("kicad_tooling.markdown_check.distribution", return_value=installed) as lookup:
        assert executable() == binary
    lookup.assert_called_once_with("rumdl")
    installed.locate_file.assert_called_once_with(installed.files[0])


@pytest.mark.parametrize(
    "files",
    (None, [], [PackagePath("bin/rumdl"), PackagePath("Scripts/rumdl.exe")]),
    ids=("missing-metadata", "empty-metadata", "ambiguous-metadata"),
)
def test_missing_or_ambiguous_metadata_has_no_path_search_fallback(files: list | None) -> None:
    installed = Mock(files=files)
    installed.locate_file.return_value = Path("/missing/rumdl")
    with (
        patch("kicad_tooling.markdown_check.distribution", return_value=installed),
        pytest.raises(ValueError, match="exactly one"),
    ):
        executable()
    with patch(
        "kicad_tooling.markdown_check.distribution", side_effect=PackageNotFoundError("rumdl")
    ):
        assert run(["--version"]) == 127


def test_module_ignores_checkout_shadow_and_ambient_python_path(tmp_path: Path) -> None:
    caller = tmp_path
    (caller / "kicad_tooling.py").write_text("raise RuntimeError('shadow import')\n")
    (caller / "rumdl").write_text("not the installed executable\n")
    result = subprocess.run(
        (sys.executable, "-I", "-m", "kicad_tooling.markdown_check", "--version"),
        cwd=caller,
        env=os.environ | {"PYTHONPATH": str(caller), "PATH": str(caller)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "rumdl 0.2.77"
