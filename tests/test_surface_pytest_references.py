"""Surface parity declarations can target pytest functions and legacy test methods."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.models import ToolSurfacesCatalog
from kicad_tooling.hwrepo.surface import CATALOG, _test_exists, parity_issues
from tests.support import SOURCE_ROOT


def test_surface_parity_resolves_pytest_functions_without_importing_them(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_contract.py").write_text(
        "raise AssertionError('test modules must not be imported')\n"
        "def test_behavior():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    assert _test_exists(tmp_path, "tests.test_contract.test_behavior")
    assert not _test_exists(tmp_path, "tests.test_contract.test_missing")


def test_surface_parity_still_resolves_unittest_methods(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_contract.py").write_text(
        "class ContractTests:\n    def test_behavior(self):\n        assert True\n",
        encoding="utf-8",
    )

    assert _test_exists(tmp_path, "tests.test_contract.ContractTests.test_behavior")


def test_surface_parity_parses_each_referenced_module_once() -> None:
    catalog = read_model(SOURCE_ROOT / CATALOG, ToolSurfacesCatalog)

    with patch("kicad_tooling.hwrepo.surface.ast.parse", wraps=ast.parse) as parse:
        assert not parity_issues(SOURCE_ROOT, catalog.capabilities)

    parsed_paths = tuple(call.kwargs["filename"] for call in parse.call_args_list)
    assert len(parsed_paths) == len(set(parsed_paths))
