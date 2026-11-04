"""Guard typed ownership of mapped PCB requirement candidate evidence."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_keepout_candidate_evidence import PcbKeepoutCandidate
from kicad_tooling.hwrepo.design_lint_pcb_rf_antenna_candidate_evidence import (
    PcbRfAntennaCandidate,
)
from kicad_tooling.hwrepo.design_lint_pcb_switching_loop_candidate_evidence import (
    PcbSwitchingLoopCandidate,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]

OWNER_CLASSES = {
    "pcb.switching_loop_geometry": (
        PcbSwitchingLoopCandidate,
        "design_lint_pcb_switching_loop_candidate_evidence.py",
        "project_pcb_switching_loop_evidence",
    ),
    "pcb.keepout_intent_coverage": (
        PcbKeepoutCandidate,
        "design_lint_pcb_keepout_candidate_evidence.py",
        "project_pcb_keepout_evidence",
    ),
    "pcb.rf_module_antenna_keepout_coverage": (
        PcbRfAntennaCandidate,
        "design_lint_pcb_rf_antenna_candidate_evidence.py",
        "project_pcb_rf_antenna_evidence",
    ),
}


def test_mapped_pcb_requirement_candidates_have_theme_owned_projections() -> None:
    translator_path = HWREPO / "design_lint_pcb_requirement_candidates.py"
    translator_tree = ast.parse(translator_path.read_text(encoding="utf-8"))
    translator_function = next(
        node
        for node in translator_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "pcb_requirement_coverage_candidates"
    )
    assert line_count(translator_path) < IMPLEMENTATION_MAX_LINES

    for candidate_type, owner_filename, projector_name in OWNER_CLASSES.values():
        owner_path = HWREPO / owner_filename
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
        assert candidate_type.__module__ == ("kicad_tooling.hwrepo." + Path(owner_filename).stem)
        assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
        assert any(
            isinstance(node, ast.FunctionDef) and node.name == projector_name
            for node in owner_tree.body
        )

    typed_owner_names = {
        node.func.value.id
        for node in ast.walk(translator_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        and isinstance(node.func.value, ast.Name)
    }
    assert typed_owner_names >= {
        candidate_type.__name__ for candidate_type, _, _ in OWNER_CLASSES.values()
    }

    opaque_rule_candidates = [
        node
        for node in ast.walk(translator_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        and any(
            keyword.arg == "rule_id"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value in OWNER_CLASSES
            for keyword in node.keywords
        )
    ]
    assert opaque_rule_candidates == []
