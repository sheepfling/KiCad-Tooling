"""Guard explicit PCB ownership of native and authored rule candidates."""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo.design_lint_candidate_inputs import DesignLintCandidateInputs
from kicad_tooling.hwrepo.design_lint_evaluation_types import DesignLintEvaluationPreparation
from kicad_tooling.hwrepo.design_lint_pcb_inputs import PcbCandidateInputs
from kicad_tooling.hwrepo.design_lint_rule_models import DesignLintRuleCatalog
from kicad_tooling.hwrepo.design_lint_types import Candidate

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]

_ROOT = Path(__file__).parents[1]


def test_scanner_has_no_unowned_additional_candidate_collection() -> None:
    input_names = {item.name for item in fields(DesignLintCandidateInputs)}
    pcb_types = get_type_hints(PcbCandidateInputs)

    assert "additional_candidates" not in input_names
    assert get_type_hints(DesignLintCandidateInputs)["catalog"] is DesignLintRuleCatalog
    assert pcb_types["dru_rule_candidates"] == tuple[Candidate, ...]
    assert pcb_types["native_drc_candidates"] == tuple[Candidate, ...]
    assert get_type_hints(DesignLintEvaluationPreparation)["candidate_inputs"] is (
        DesignLintCandidateInputs
    )


def test_preparation_owns_candidate_groups_and_scanner_consumes_prepared_bundle() -> None:
    preparation_path = _ROOT / "kicad_tooling/hwrepo/design_lint_evaluation_preparation.py"
    preparation_tree = ast.parse(
        preparation_path.read_text(encoding="utf-8"), filename=preparation_path.as_posix()
    )
    candidate_input_calls = [
        node
        for node in ast.walk(preparation_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "DesignLintCandidateInputs"
    ]
    assert len(candidate_input_calls) == 1
    assert {keyword.arg for keyword in candidate_input_calls[0].keywords} == {
        item.name for item in fields(DesignLintCandidateInputs)
    }
    assert any(
        keyword.arg == "pcb" and ast.unparse(keyword.value) == "pcb_candidate_inputs"
        for keyword in candidate_input_calls[0].keywords
    )

    pcb_input_calls = [
        node
        for node in ast.walk(preparation_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "PcbCandidateInputs"
    ]
    assert len(pcb_input_calls) == 1
    pcb_keywords = {
        keyword.arg: ast.unparse(keyword.value) for keyword in pcb_input_calls[0].keywords
    }
    assert pcb_keywords["dru_rule_candidates"] == "request.pcb_dru_rule_candidates"
    assert pcb_keywords["native_drc_candidates"] == "request.pcb_native_drc_candidates"

    candidates_path = _ROOT / "kicad_tooling/hwrepo/design_lint_evaluation_candidates.py"
    candidates_tree = ast.parse(
        candidates_path.read_text(encoding="utf-8"), filename=candidates_path.as_posix()
    )
    scanner_calls = [
        node
        for node in ast.walk(candidates_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "scan_candidate_result"
    ]
    assert any(
        len(call.args) == 1 and ast.unparse(call.args[0]) == "candidate_inputs"
        for call in scanner_calls
    )
    candidate_bindings = {
        node.targets[0].id: node.value
        for node in ast.walk(candidates_tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    assert ast.unparse(candidate_bindings["candidate_inputs"]) == "prepared.candidate_inputs"
    assert "DesignLintCandidateInputs" not in candidates_path.read_text(encoding="utf-8")
