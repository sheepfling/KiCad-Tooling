"""Keep USB unmapped-topology lint in its theme-owned source boundary."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from kicad_tooling.hwrepo.design_lint_usb_unmapped_topology_candidate_evidence import (
    UsbUnmappedMultiPinTopologyCandidate,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def test_usb_unmapped_multi_pin_rule_points_to_its_topology_predicate() -> None:
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.usb_unmapped_multi_pin_topology"
    )
    owner = "kicad_tooling/hwrepo/usb_peer_unsupported_topology.py#unsupported_usb_multi_pin_path_candidates"
    candidate_evidence_owner = (
        "kicad_tooling/hwrepo/design_lint_usb_unmapped_topology_candidate_evidence.py"
        "#UsbUnmappedMultiPinTopologyCandidate"
    )

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert candidate_evidence_owner in rule.implementation_refs
    assert line_count(HWREPO / "usb_peer_unsupported_topology.py") < IMPLEMENTATION_MAX_LINES
    assert line_count(HWREPO / "design_lint_usb_unmapped_topology.py") < IMPLEMENTATION_MAX_LINES
    candidate_module = HWREPO / "design_lint_usb_unmapped_topology_candidate_evidence.py"
    assert UsbUnmappedMultiPinTopologyCandidate.__module__ == (
        "kicad_tooling.hwrepo.design_lint_usb_unmapped_topology_candidate_evidence"
    )
    assert line_count(candidate_module) < IMPLEMENTATION_MAX_LINES

    adapter_tree = ast.parse(
        (HWREPO / "design_lint_usb_unmapped_topology.py").read_text(encoding="utf-8")
    )
    candidate_builder = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "usb_unmapped_multi_pin_topology_candidates"
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(candidate_builder)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(candidate_builder)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence"
        for node in ast.walk(candidate_builder)
    )
