"""Guard the typed source route for generic component peer open findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
    pytest.mark.architecture,
]

RULE_IDS = (
    "component.generic_peer_pin_all_open",
    "component.generic_peer_pin_mixed_open",
)
OWNER = "kicad_tooling/hwrepo/design_lint_component_peer_open_candidate_evidence.py"


def test_generic_component_peer_open_rules_use_the_typed_source_owner() -> None:
    owner_path = HWREPO / "design_lint_component_peer_open_candidate_evidence.py"
    catalog = rule_catalog()
    rules = tuple(rule for rule in catalog.rules if rule.rule_id in RULE_IDS)
    required_refs = {
        f"{OWNER}#GenericComponentPeerOpenScanEvidence",
        f"{OWNER}#GenericComponentPeerOpenEvidence",
        f"{OWNER}#GenericComponentPeerOpenCandidate",
        f"{OWNER}#_current_scan",
        f"{OWNER}#_validate_open_peer_outlier",
        f"{OWNER}#project_generic_component_peer_open_evidence",
        "kicad_tooling/hwrepo/component_peer_pin_scan.py#scan_component_peer_pin_assignments",
    }

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert len(rules) == len(RULE_IDS)
    for rule in rules:
        assert rule.theme == "components"
        assert rule.implementation_owner in rule.implementation_refs
        assert required_refs <= set(rule.implementation_refs)

    for filename, function_name in (
        ("component_peer_pin_all_open.py", "all_open_generic_component_peer_pin_candidates"),
        ("component_peer_pin_mixed_open.py", "mixed_open_generic_component_peer_pin_candidates"),
    ):
        path = HWREPO / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=filename)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        calls = tuple(node for node in ast.walk(function) if isinstance(node, ast.Call))
        assert not any(
            isinstance(node.func, ast.Name) and node.func.id == "Candidate" for node in calls
        )
        assert any(
            isinstance(node.func, ast.Attribute) and node.func.attr == "from_source_evidence"
            for node in calls
        )
