"""Guard typed ownership of named-rail BJT and MOSFET terminal findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
]

_RULE_OWNERS = {
    "component.bjt_terminal_order_on_named_rails": (
        "component_bjt_terminal_order.py",
        "bjts_with_unusual_collector_emitter_rail_order",
        "BjtTerminalOrderEvidence",
    ),
    "component.mosfet_terminal_order_on_named_rails": (
        "component_mosfet_terminal_order.py",
        "mosfets_with_unusual_drain_source_rail_order",
        "MosfetTerminalOrderEvidence",
    ),
}


def test_typed_terminal_order_owner_and_scanners_stay_focused() -> None:
    source_path = HWREPO / "design_lint_component_terminal_order_candidate_evidence.py"
    source_tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=source_path.name)
    assert line_count(source_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_component_terminal_order_evidence"
        for node in source_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
        for node in source_tree.body
    )

    for rule_id, (filename, scanner_name, evidence_name) in _RULE_OWNERS.items():
        scanner_path = HWREPO / filename
        scanner_tree = ast.parse(scanner_path.read_text(encoding="utf-8"), filename=filename)
        scanner = next(
            node
            for node in scanner_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == scanner_name
        )
        assert line_count(scanner_path) < IMPLEMENTATION_MAX_LINES
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(scanner)
        ), scanner_name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(scanner)
        ), scanner_name

        rule = rule_catalog(rule_id=rule_id).rules[0]
        assert rule.implementation_owner.endswith(f"{filename}#{scanner_name}")
        assert (
            "kicad_tooling/hwrepo/design_lint_component_terminal_order_candidate_evidence.py"
            f"#{evidence_name}"
        ) in rule.implementation_refs
        assert (
            "kicad_tooling/hwrepo/design_lint_component_terminal_order_candidate_evidence.py"
            "#project_component_terminal_order_evidence"
        ) in rule.implementation_refs
        assert (
            "kicad_tooling/hwrepo/netlist_pin_assignments.py#netlist_pin_net_assignments"
            in rule.implementation_refs
        )
