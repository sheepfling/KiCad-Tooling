"""Guard source ownership for repeated component signal-pin findings."""

from __future__ import annotations

import ast
from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.component_repeated_signal_pins import (
    component_repeated_signal_pin_unassigned,
    component_signal_pin_net_divergences,
)
from kicad_tooling.hwrepo.design_lint_component_repeated_signal_candidate_evidence import (
    RepeatedSignalPinCandidate,
    project_repeated_signal_pin_evidence,
)
from tests.design_lint_fixtures.repeated_signal_pin_functions import (
    repeated_signal_pin_component,
    repeated_signal_pin_with_unassigned_member,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
]


def test_repeated_signal_candidates_retain_source_and_exact_wire_projection() -> None:
    divergent_source = repeated_signal_pin_component()
    (divergent,) = component_signal_pin_net_divergences(divergent_source)
    assert isinstance(divergent, RepeatedSignalPinCandidate)
    assert divergent.source_evidence.observed is divergent_source
    assert divergent.source_evidence.finding_kind == "divergent"
    assert (
        divergent.evidence
        == project_repeated_signal_pin_evidence(divergent.source_evidence).evidence
    )

    open_source = repeated_signal_pin_with_unassigned_member()
    (unassigned,) = component_repeated_signal_pin_unassigned(open_source)
    assert isinstance(unassigned, RepeatedSignalPinCandidate)
    assert unassigned.source_evidence.observed is open_source
    assert unassigned.source_evidence.finding_kind == "unassigned"
    assert unassigned.source_evidence.assigned_signal_pins == ("U1.1",)
    assert unassigned.source_evidence.unassigned_signal_pins == ("U1.2",)
    assert (
        unassigned.evidence
        == project_repeated_signal_pin_evidence(unassigned.source_evidence).evidence
    )


def test_repeated_signal_source_rejects_pin_assignments_changed_after_scan() -> None:
    observed = repeated_signal_pin_component()
    (candidate,) = component_signal_pin_net_divergences(observed)
    assert isinstance(candidate, RepeatedSignalPinCandidate)
    source = candidate.source_evidence
    changed_pins = tuple(
        replace(pin, assignments=("SYNTHETIC_OTHER_NET",)) if pin.pin == "U1.1" else pin
        for pin in source.group.pins
    )

    with pytest.raises(ValueError, match="current netlist"):
        replace(source, group=replace(source.group, pins=changed_pins))


def test_repeated_signal_adapters_use_only_the_typed_candidate_projection() -> None:
    route = HWREPO / "component_repeated_signal_pins.py"
    tree = ast.parse(route.read_text(encoding="utf-8"), filename=route.name)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert line_count(route) < IMPLEMENTATION_MAX_LINES
    for name in (
        "component_signal_pin_net_divergences",
        "component_repeated_signal_pin_unassigned",
    ):
        function = functions[name]
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(function)
        ), name
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Candidate"
            for node in ast.walk(function)
        ), name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        ), name


def test_repeated_signal_source_owner_has_a_focused_boundary() -> None:
    owner = HWREPO / "design_lint_component_repeated_signal_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert {
        "RepeatedSignalPin",
        "RepeatedSignalPinGroup",
        "RepeatedSignalPinFindingEvidence",
        "RepeatedSignalPinCandidate",
    } <= classes
    assert "project_repeated_signal_pin_evidence" in functions
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "netlist_pin_assignments"
        and any(alias.name == "netlist_pin_net_index" for alias in node.names)
        for node in tree.body
    )
