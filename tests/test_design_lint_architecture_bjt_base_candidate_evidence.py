"""Guard source ownership for BJT base-bias and direct-drive findings."""

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

OWNER_PATH = "kicad_tooling/hwrepo/design_lint_bjt_base_candidate_evidence.py"


def test_bjt_base_rules_share_a_bounded_source_evidence_owner() -> None:
    owner = HWREPO / "design_lint_bjt_base_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    rule_owners = {
        rule.rule_id: rule
        for rule in rule_catalog().rules
        if rule.rule_id
        in {
            "component.bjt_base_direct_drive",
            "component.bjt_base_without_visible_emitter_bias",
        }
    }

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert {node.name for node in tree.body if isinstance(node, ast.ClassDef)} >= {
        "BjtBaseDirectDriveEvidence",
        "BjtBaseBiasEvidence",
        "BjtBaseCandidate",
    }
    assert set(rule_owners) == {
        "component.bjt_base_direct_drive",
        "component.bjt_base_without_visible_emitter_bias",
    }
    for rule in rule_owners.values():
        assert f"{OWNER_PATH}#BjtBaseCandidate" in rule.implementation_refs


def test_bjt_predicates_delegate_wire_evidence_to_the_shared_owner() -> None:
    for module in ("component_bjt_base_bias.py", "component_bjt_base_drive.py"):
        path = HWREPO / module
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        routes = [
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "BjtBaseCandidate"
        ]

        assert routes, module
        assert not any(
            isinstance(node.func, ast.Name) and node.func.id == "Candidate" for node in calls
        ), module
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(tree)
        ), module
