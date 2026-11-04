"""Guard the typed USB data-polarity evidence owner and adapter boundary."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def test_usb_data_polarity_evidence_has_a_focused_owner() -> None:
    owner = HWREPO / "design_lint_usb_data_polarity_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_usb_data_polarity_evidence"
        for node in tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "UsbDataPolarityCandidate"
        for node in tree.body
    )


def test_usb_data_polarity_predicate_routes_through_typed_evidence() -> None:
    path = HWREPO / "design_lint_interfaces_usb_data_polarity.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "usb_data_polarity_label_candidates"
    )

    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "UsbDataPolarityCandidate"
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(function)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
    )
