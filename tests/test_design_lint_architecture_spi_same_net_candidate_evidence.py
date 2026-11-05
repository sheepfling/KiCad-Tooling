"""Guard typed evidence ownership for SPI same-net findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]

OWNER = "design_lint_spi_same_net_candidate_evidence.py"
PREDICATES = {
    "spi_same_net.py": (
        "spi_data_input_output_same_net_candidates",
        "bus.spi_data_input_output_same_net",
    ),
    "spi_clock_data_same_net.py": (
        "spi_clock_control_data_same_net_candidates",
        "bus.spi_clock_control_data_same_net",
    ),
    "spi_control_same_net.py": (
        "spi_clock_chip_select_same_net_candidates",
        "bus.spi_clock_chip_select_same_net",
    ),
}


def _tree(filename: str) -> ast.Module:
    path = HWREPO / filename
    return ast.parse(path.read_text(encoding="utf-8"), filename=filename)


def test_spi_same_net_source_owner_has_three_explicit_variants() -> None:
    owner = HWREPO / OWNER
    tree = _tree(OWNER)
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert classes >= {
        "SpiDataRolesSameNetEvidence",
        "SpiClockDataSameNetEvidence",
        "SpiClockSelectSameNetEvidence",
        "SpiSameNetCandidate",
    }


def test_spi_same_net_predicates_delegate_projection_and_catalog_routes_to_owner() -> None:
    rules = {rule.rule_id: rule for rule in rule_catalog().rules}
    for filename, (predicate_name, rule_id) in PREDICATES.items():
        tree = _tree(filename)
        assert any(
            isinstance(node, ast.FunctionDef) and node.name == predicate_name for node in tree.body
        )
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]

        assert any(
            isinstance(node.func, ast.Attribute) and node.func.attr == "from_source_evidence"
            for node in calls
        ), filename
        assert not any(
            isinstance(node.func, ast.Name) and node.func.id == "Candidate" for node in calls
        ), filename
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(tree)
        ), filename

        rule = rules[rule_id]
        assert rule.implementation_owner == f"kicad_tooling/hwrepo/{filename}#{predicate_name}"
        assert f"kicad_tooling/hwrepo/{OWNER}#SpiSameNetCandidate" in rule.implementation_refs
