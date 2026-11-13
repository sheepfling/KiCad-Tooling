"""Guard ownership and source boundaries for unmapped fromTo review."""

from __future__ import annotations

import ast
import json

import pytest

from tests.lint_architecture_support import HWREPO

RULE_ID = "pcb.signal_path_unmapped_from_to_length_rule"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_unmapped_from_to_rule_has_focused_owner_and_shared_source_scan() -> None:
    modules = (
        "pcb_drc_conditions.py",
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
        "unmapped_signal_path_from_to_length_rule_candidates"
    )
    assert rule["implementation_owner"] in rule["implementation_refs"]
    assert ("kicad_tooling/hwrepo/pcb_drc_conditions.py#native_exact_from_to_condition") in rule[
        "implementation_refs"
    ]
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
    assert RULE_ID in (HWREPO / "design_lint_rule_types.py").read_text(encoding="utf-8")


def test_unmapped_from_to_rule_reuses_source_bound_path_scan() -> None:
    scanner = (HWREPO / "pcb_signal_path_unmapped_rule_scan.py").read_text(encoding="utf-8")

    assert "unmapped_signal_path_from_to_length_rule_candidates" in scanner
    assert scanner.count("source_bound_drc_evidence(") == 1
