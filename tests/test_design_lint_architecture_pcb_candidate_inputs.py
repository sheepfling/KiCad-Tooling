"""Guard explicit PCB ownership of native and authored rule candidates."""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo.design_lint_candidate_inputs import DesignLintCandidateInputs
from kicad_tooling.hwrepo.design_lint_pcb_inputs import PcbCandidateInputs
from kicad_tooling.hwrepo.design_lint_types import Candidate

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]

_ROOT = Path(__file__).parents[1]


def test_scanner_has_no_unowned_additional_candidate_collection() -> None:
    input_names = {item.name for item in fields(DesignLintCandidateInputs)}
    pcb_types = get_type_hints(PcbCandidateInputs)

    assert "additional_candidates" not in input_names
    assert pcb_types["dru_rule_candidates"] == tuple[Candidate, ...]
    assert pcb_types["native_drc_candidates"] == tuple[Candidate, ...]


def test_prepared_candidates_route_both_sources_into_the_pcb_group() -> None:
    path = _ROOT / "kicad_tooling/hwrepo/design_lint_evaluation_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    calls = [
        {keyword.arg: ast.unparse(keyword.value) for keyword in node.keywords}
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "PcbCandidateInputs"
    ]

    assert any(
        call.get("dru_rule_candidates") == "request.pcb_dru_rule_candidates"
        and call.get("native_drc_candidates") == "request.pcb_native_drc_candidates"
        for call in calls
    )
