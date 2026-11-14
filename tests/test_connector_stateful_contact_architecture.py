"""Keep stateful connector lint and native pin indexing in focused owners."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import connector_stateful_contacts, netlist_pin_assignments
from kicad_tooling.hwrepo.design_lint_connector_stateful_contact_candidate_evidence import (
    StatefulConnectorContactCandidate,
    project_stateful_contact_evidence,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
    pytest.mark.evidence_lint,
]


def _imports_module(path: Path, module_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module_name:
            return True
        if isinstance(node, ast.Import) and any(alias.name == module_name for alias in node.names):
            return True
    return False


def test_stateful_contact_rule_and_shared_pin_index_have_bounded_owners() -> None:
    assert line_count(HWREPO / "connector_stateful_contacts.py") < IMPLEMENTATION_MAX_LINES
    assert line_count(HWREPO / "connector_stateful_contact_models.py") < IMPLEMENTATION_MAX_LINES
    assert (
        line_count(HWREPO / "design_lint_connector_stateful_contact_candidate_evidence.py")
        < IMPLEMENTATION_MAX_LINES
    )
    assert line_count(HWREPO / "netlist_pin_assignments.py") < IMPLEMENTATION_MAX_LINES
    assert hasattr(connector_stateful_contacts, "stateful_connector_contact_findings")
    assert set(vars(netlist_pin_assignments)) >= {"netlist_pin_net_index"}
    assert StatefulConnectorContactCandidate.__module__.endswith(
        "design_lint_connector_stateful_contact_candidate_evidence"
    )
    assert callable(project_stateful_contact_evidence)


def test_native_pin_assignment_index_has_two_theme_consumers() -> None:
    helper_module = "netlist_pin_assignments"
    assert _imports_module(HWREPO / "connector_stateful_contacts.py", helper_module)
    assert _imports_module(
        HWREPO / "connector_stateful_contacts.py",
        "design_lint_connector_stateful_contact_candidate_evidence",
    )
    assert _imports_module(HWREPO / "connector_contact_ratings.py", helper_module)
    assert _imports_module(
        HWREPO / "design_lint_connector_candidate_dispatch.py", "connector_stateful_contacts"
    )


def test_stateful_contact_adapter_routes_both_findings_through_typed_evidence() -> None:
    route = HWREPO / "connector_stateful_contacts.py"
    tree = ast.parse(route.read_text(encoding="utf-8"), filename=route.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "stateful_connector_contact_findings"
    )

    calls = tuple(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
    )
    assert len(calls) == 2
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(function)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
    )
