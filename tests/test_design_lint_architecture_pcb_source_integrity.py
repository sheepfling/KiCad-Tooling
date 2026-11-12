"""Keep PCB UUID source integrity in a small PCB-owned lint module."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.catalog_lint,
    pytest.mark.architecture,
    pytest.mark.rule_gate_integrity,
]

ROOT = Path(__file__).resolve().parents[1]
OWNER = "kicad_tooling/hwrepo/pcb_object_uuid_integrity.py#duplicate_pcb_object_uuid_candidates"
RULE_ID = "pcb.duplicate_object_uuid"


def test_rule_owner_is_a_bounded_pcb_predicate() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    owner_path, owner_name = OWNER.split("#", maxsplit=1)
    owner = ROOT / owner_path
    tree = ast.parse(owner.read_text(encoding="utf-8"))
    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert rule.theme == "pcb"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert owner_name in functions
    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert "pcb_object_uuid_integrity" not in (
        ROOT / "kicad_tooling/hwrepo/design_lint.py"
    ).read_text(encoding="utf-8")


def test_pcb_uuid_candidate_flow_stays_explicit_and_bounded() -> None:
    paths = (
        "kicad_tooling/hwrepo/pcb_object_uuid_integrity.py",
        "kicad_tooling/hwrepo/design_lint_project_inspection.py",
        "kicad_tooling/hwrepo/design_lint_evaluation_types.py",
        "kicad_tooling/hwrepo/design_lint_candidate_inputs.py",
        "kicad_tooling/hwrepo/design_lint_evaluation_preparation.py",
        "kicad_tooling/hwrepo/design_lint_candidate_aggregation.py",
        "tests/test_pcb_duplicate_object_uuid.py",
        "tests/test_design_lint_mcp_parity_pcb_duplicate_object_uuid.py",
        "tests/test_pcb_duplicate_object_uuid_native.py",
        "tests/hashseed_probe_cases/pcb_uuid_integrity.py",
    )
    oversized = {
        path: len((ROOT / path).read_text(encoding="utf-8").splitlines())
        for path in paths
        if len((ROOT / path).read_text(encoding="utf-8").splitlines()) >= 500
    }
    request_source = (ROOT / paths[2]).read_text(encoding="utf-8")
    input_source = (ROOT / paths[3]).read_text(encoding="utf-8")
    preparation_source = (ROOT / paths[4]).read_text(encoding="utf-8")
    aggregation_source = (ROOT / paths[5]).read_text(encoding="utf-8")
    inspection_source = (ROOT / paths[1]).read_text(encoding="utf-8")

    assert not oversized
    assert "pcb_source_candidates" in request_source
    assert "pcb_source_candidates" in input_source
    assert "pcb_source_candidates=request.pcb_source_candidates" in preparation_source
    assert "found.extend(inputs.pcb_source_candidates)" in aggregation_source
    assert "duplicate_pcb_object_uuid_candidates" in inspection_source
