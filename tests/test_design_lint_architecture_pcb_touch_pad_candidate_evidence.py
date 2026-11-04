"""Guard the source owner and service adapter for touch-pad findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_touch_pad_clearance_candidate_evidence import (
    PcbBlockedTouchPadClearanceCandidate,
    PcbTouchPadClearanceCandidate,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_touch_pad_candidates_have_one_source_owner_and_a_compatibility_adapter() -> None:
    owner_path = HWREPO / "design_lint_pcb_touch_pad_clearance_candidate_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    service_path = HWREPO / "pcb_touch_pad_clearance.py"
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"))
    translator_path = HWREPO / "design_lint_pcb_requirement_candidates.py"
    translator_tree = ast.parse(translator_path.read_text(encoding="utf-8"))

    assert PcbTouchPadClearanceCandidate.__module__ == (
        "kicad_tooling.hwrepo.design_lint_pcb_touch_pad_clearance_candidate_evidence"
    )
    assert PcbBlockedTouchPadClearanceCandidate.__module__ == (
        PcbTouchPadClearanceCandidate.__module__
    )
    for path in (owner_path, service_path, translator_path):
        assert line_count(path) < IMPLEMENTATION_MAX_LINES
    for projector in (
        "project_blocked_touch_pad_clearance_evidence",
        "project_touch_pad_clearance_evidence",
    ):
        assert any(
            isinstance(node, ast.FunctionDef) and node.name == projector for node in owner_tree.body
        )

    service_adapter = next(
        node
        for node in service_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "touch_pad_clearance_violations"
    )
    assert any(isinstance(node, ast.ImportFrom) for node in ast.walk(service_adapter))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(service_tree)
    )

    translator_imports_owner = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_pcb_touch_pad_clearance_candidate_evidence"
        and any(alias.name == "touch_pad_clearance_violations" for alias in node.names)
        for node in translator_tree.body
    )
    assert translator_imports_owner
