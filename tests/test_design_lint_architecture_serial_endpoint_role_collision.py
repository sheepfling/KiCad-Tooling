"""Keep serial endpoint role collision analysis in its theme-owned service."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

ROOT = Path(__file__).resolve().parents[1]
OWNER = "kicad_tooling/hwrepo/serial_endpoint_role_collision.py"
OWNER_FUNCTION = "serial_endpoint_role_collision_candidates"
RULE_ID = "bus.serial_endpoint_role_collision"


def test_catalog_points_to_bounded_serial_role_owner_and_dispatches_it() -> None:
    catalog = json.loads((ROOT / "kicad_tooling/hwrepo/design-lint-rules.json").read_text())
    rule = next(item for item in catalog["rules"] if item["rule_id"] == RULE_ID)
    owner_path = ROOT / OWNER
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    owner_names = {
        node.name for node in owner_tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    dispatcher_path = ROOT / "kicad_tooling/hwrepo/design_lint_serial_signal_candidates.py"
    dispatcher = ast.parse(dispatcher_path.read_text(encoding="utf-8"))

    assert len(owner_path.read_text(encoding="utf-8").splitlines()) < 500
    assert rule["theme"] == "interfaces"
    assert rule["implementation_owner"] == f"{OWNER}#{OWNER_FUNCTION}"
    assert rule["implementation_owner"] in rule["implementation_refs"]
    assert OWNER_FUNCTION in owner_names
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "serial_endpoint_role_collision"
        and any(alias.name == OWNER_FUNCTION for alias in node.names)
        for node in dispatcher.body
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == OWNER_FUNCTION
        for node in ast.walk(dispatcher)
    )
