"""Guard typed evidence ownership for named connector power aliases."""

from __future__ import annotations

import ast
from typing import cast

import pytest

from kicad_tooling.hwrepo.connector_peer_named_power_aliases import (
    ConnectorPowerElectricalType,
    connector_named_power_alias_peers,
)
from kicad_tooling.hwrepo.design_lint_connector_named_power_alias_candidate_evidence import (
    ConnectorNamedPowerAliasCandidate,
    ConnectorNamedPowerAliasRuleId,
    connector_named_power_alias_candidate,
    project_connector_named_power_alias_evidence,
)
from tests.design_lint_fixtures.connector_named_power_aliases import (
    named_connector_power_alias_netlist,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
    pytest.mark.evidence_lint,
]

_RULE_CASES: tuple[
    tuple[
        ConnectorNamedPowerAliasRuleId,
        ConnectorPowerElectricalType,
        tuple[str | None, str | None],
    ],
    ...,
] = (
    ("connector.peer_power_input_open_assignment", "power_in", ("RAIL", None)),
    ("connector.peer_power_input_named_all_open", "power_in", (None, None)),
    ("connector.peer_power_input_named_assignment_divergence", "power_in", ("A", "B")),
    ("connector.peer_power_output_open_assignment", "power_out", ("RAIL", None)),
    ("connector.peer_power_output_named_all_open", "power_out", (None, None)),
    (
        "connector.peer_power_output_named_assignment_divergence",
        "power_out",
        ("A", "B"),
    ),
)


def test_named_power_alias_candidate_source_and_wire_projection_stay_aligned() -> None:
    for rule_id, electrical_type, assignments in _RULE_CASES:
        source = named_connector_power_alias_netlist(
            assignments=assignments,
            target_functions=("BIAS_OUT", "BIAS_OUT")
            if electrical_type == "power_out"
            else ("BIAS_IN", "BIAS_IN"),
            target_types=(electrical_type, electrical_type),
        )
        (peer,) = connector_named_power_alias_peers(source, electrical_type)

        candidate = connector_named_power_alias_candidate(
            peer,
            rule_id,
            subject="synthetic named power alias",
            message="synthetic review",
        )

        assert isinstance(candidate, ConnectorNamedPowerAliasCandidate)
        assert candidate.source_evidence.peer == peer
        assert candidate.rule_id == rule_id
        assert (
            candidate.evidence
            == project_connector_named_power_alias_evidence(candidate.source_evidence).evidence
        )


def test_part_id_peer_assignment_source_is_immutable() -> None:
    source = named_connector_power_alias_netlist()
    (peer,) = connector_named_power_alias_peers(source, "power_in")

    with pytest.raises(TypeError):
        cast(dict[str, tuple[str, ...]], peer.group.assignments)["J1.1"] = ("SYNTHETIC_CHANGED",)


def test_candidate_adapters_delegate_all_six_rules_to_the_typed_owner() -> None:
    for filename, expected_functions in (
        (
            "connector_peer_power_input.py",
            {
                "connector_named_power_input_open_assignments",
                "connector_named_power_input_all_open",
                "connector_named_power_input_assignment_divergence",
            },
        ),
        (
            "connector_peer_power_output.py",
            {
                "connector_named_power_output_open_assignments",
                "connector_named_power_output_all_open",
                "connector_named_power_output_assignment_divergence",
            },
        ),
    ):
        route = HWREPO / filename
        tree = ast.parse(route.read_text(encoding="utf-8"), filename=route.name)
        assert line_count(route) < IMPLEMENTATION_MAX_LINES
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        assert expected_functions <= functions.keys()
        for name in expected_functions:
            function = functions[name]
            assert any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "connector_named_power_alias_candidate"
                for node in ast.walk(function)
            ), name
            assert not any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Candidate"
                for node in ast.walk(function)
            ), name
            assert not any(
                isinstance(node, ast.keyword) and node.arg == "evidence"
                for node in ast.walk(function)
            ), name


def test_candidate_owner_and_shared_peer_source_have_clear_boundaries() -> None:
    owner = HWREPO / "design_lint_connector_named_power_alias_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {
        "ConnectorNamedPowerAliasFindingEvidence",
        "ConnectorNamedPowerAliasCandidate",
    } <= classes
    assert {
        "project_connector_named_power_alias_evidence",
        "connector_named_power_alias_candidate",
    } <= functions

    shared = HWREPO / "connector_peer_named_power_aliases.py"
    shared_tree = ast.parse(shared.read_text(encoding="utf-8"), filename=shared.name)
    assert line_count(shared) < IMPLEMENTATION_MAX_LINES
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name == "connector_named_power_alias_evidence"
        for node in shared_tree.body
    )

    scan = HWREPO / "connector_peer_pin_scan.py"
    scan_tree = ast.parse(scan.read_text(encoding="utf-8"), filename=scan.name)
    group = next(
        node
        for node in scan_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ConnectorPartIdPeerPinGroup"
    )
    assert any(
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "assignments"
        and isinstance(node.annotation, ast.Subscript)
        and isinstance(node.annotation.value, ast.Name)
        and node.annotation.value.id == "Mapping"
        for node in group.body
    )
