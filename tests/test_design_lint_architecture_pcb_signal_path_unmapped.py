"""Guard ownership and source boundaries for signal-path scope review."""

from __future__ import annotations

import ast
import json

import pytest

from tests.lint_architecture_support import HWREPO

RULE_ID = "pcb.signal_path_unmapped_native_rule"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_signal_path_unmapped_rule_has_focused_owner_and_source_scan() -> None:
    modules = (
        "pcb_signal_path_unmapped_native.py",
        "pcb_signal_path_unmapped_rule_scan.py",
    )
    assert all(
        len((HWREPO / name).read_text(encoding="utf-8").splitlines()) < 500 for name in modules
    )

    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(item for item in catalog["rules"] if item["rule_id"] == RULE_ID)
    assert rule["theme"] == "pcb"
    assert rule["default_mode"] == "review"
    assert rule["implementation_owner"] == (
        "kicad_tooling/hwrepo/pcb_signal_path_unmapped_native.py#"
        "unmapped_signal_path_length_rule_candidates"
    )
    assert rule["implementation_owner"] in rule["implementation_refs"]
    assert (
        "kicad_tooling/hwrepo/pcb_signal_path_unmapped_rule_scan.py#"
        "scan_unmapped_signal_path_native_rules"
    ) in rule["implementation_refs"]

    inspection = ast.parse((HWREPO / "design_lint_project_inspection.py").read_text())
    scanner_imported = any(
        node.module == "pcb_signal_path_unmapped_rule_scan"
        and any(alias.name == "scan_unmapped_signal_path_native_rules" for alias in node.names)
        for node in inspection.body
        if isinstance(node, ast.ImportFrom)
    )
    assert scanner_imported
    assert "pcb.signal_path_unmapped_native_rule" in (
        HWREPO / "design_lint_rule_types.py"
    ).read_text(encoding="utf-8")


def test_signal_path_unmapped_lint_is_not_reexported_as_a_shared_model() -> None:
    shared_models = (HWREPO / "models.py").read_text(encoding="utf-8")

    assert "SignalPathUnmapped" not in shared_models
