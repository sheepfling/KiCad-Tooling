"""Guard typed source ownership for diode and polarized-capacitor polarity."""

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

_ROUTES = {
    "component.diode_anode_below_cathode_on_named_rails": (
        "component_diode_rail_orientation.py",
        "diodes_with_anode_below_cathode_on_named_rails",
        "DiodeRailOrientationEvidence",
        "component_diode_symbols.py",
        "DiodeTerminalNumbers",
        "diode_terminal_numbers",
    ),
    "component.polarized_capacitor_reversed_on_named_rails": (
        "component_polarized_capacitor_orientation.py",
        "polarized_capacitors_on_reversed_named_rails",
        "PolarizedCapacitorRailOrientationEvidence",
        "component_polarized_capacitor_symbols.py",
        "PolarizedCapacitorTerminalNumbers",
        "polarized_capacitor_terminal_numbers",
    ),
}


def test_polarity_source_owners_and_symbol_services_stay_focused() -> None:
    source_path = HWREPO / "design_lint_component_polarity_candidate_evidence.py"
    source_tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=source_path.name)
    shared_terminal = HWREPO / "component_named_rail_terminal.py"
    assert line_count(source_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(shared_terminal) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_component_polarity_evidence"
        for node in source_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
        for node in source_tree.body
    )

    for rule_id, (
        scanner_filename,
        scanner_name,
        evidence_name,
        symbols_filename,
        symbols_type,
        symbols_name,
    ) in _ROUTES.items():
        scanner_path = HWREPO / scanner_filename
        symbols_path = HWREPO / symbols_filename
        scanner_tree = ast.parse(
            scanner_path.read_text(encoding="utf-8"), filename=scanner_filename
        )
        symbols_tree = ast.parse(
            symbols_path.read_text(encoding="utf-8"), filename=symbols_filename
        )
        scanner = next(
            node
            for node in scanner_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == scanner_name
        )
        assert line_count(scanner_path) < IMPLEMENTATION_MAX_LINES
        assert line_count(symbols_path) < IMPLEMENTATION_MAX_LINES
        assert any(
            isinstance(node, ast.FunctionDef) and node.name == symbols_name
            for node in symbols_tree.body
        )
        assert any(
            isinstance(node, ast.ClassDef) and node.name == symbols_type
            for node in symbols_tree.body
        )
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
        assert rule.implementation_owner.endswith(f"{scanner_filename}#{scanner_name}")
        assert (
            "kicad_tooling/hwrepo/design_lint_component_polarity_candidate_evidence.py"
            f"#{evidence_name}"
        ) in rule.implementation_refs
        assert (
            "kicad_tooling/hwrepo/component_named_rail_terminal.py#validate_named_rail_terminal"
            in rule.implementation_refs
        )
        assert f"kicad_tooling/hwrepo/{symbols_filename}#{symbols_name}" in (
            rule.implementation_refs
        )
        assert f"kicad_tooling/hwrepo/{symbols_filename}#{symbols_type}" in (
            rule.implementation_refs
        )
