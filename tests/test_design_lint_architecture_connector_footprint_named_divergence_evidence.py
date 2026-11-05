"""Guard source ownership for footprint-similar named connector divergences."""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import replace
from typing import cast

import pytest

from kicad_tooling.hwrepo.connector_comparison_scope_types import ConnectorComparisonScope
from kicad_tooling.hwrepo.connector_footprint_peer_pins import (
    scan_connector_footprint_peer_pin_assignments,
)
from kicad_tooling.hwrepo.design_lint_connector_footprint_named_divergence_evidence import (
    ConnectorFootprintNamedDivergenceCandidate,
    ConnectorFootprintNamedDivergenceRuleId,
    connector_footprint_named_divergence_candidate,
    project_connector_footprint_named_divergence,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.connector_footprint_peer_support import (
    named_passive_contact_divergence_netlist,
    named_power_input_divergence_netlist,
    named_power_output_divergence_netlist,
    peer_netlist,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def named_signal_divergence_netlist(*, function: str) -> NetlistContract:
    return peer_netlist(
        assignments=(("GND", "GND"), ("TX_A", "TX_B")),
        functions=("Pin_1", function),
        electrical_types=("passive", "output"),
    )


_RULE_CASES: tuple[
    tuple[ConnectorFootprintNamedDivergenceRuleId, str, Callable[..., NetlistContract], str], ...
] = (
    (
        "connector.footprint_named_power_input_assignment_divergence",
        "power_in",
        named_power_input_divergence_netlist,
        "AUX_IN",
    ),
    (
        "connector.footprint_named_power_output_assignment_divergence",
        "power_out",
        named_power_output_divergence_netlist,
        "AUX_OUT",
    ),
    (
        "connector.footprint_named_signal_assignment_divergence",
        "output",
        named_signal_divergence_netlist,
        "UART_TX",
    ),
    (
        "connector.footprint_named_passive_assignment_divergence",
        "passive",
        named_passive_contact_divergence_netlist,
        "AUX_DETECT",
    ),
)


def test_named_divergences_retain_current_scan_source_and_projection() -> None:
    groups = {
        "J1": ConnectorComparisonScope("reviewed-port", "same source connector map"),
        "J2": ConnectorComparisonScope("reviewed-port", "same source connector map"),
    }
    for rule_id, electrical_type, netlist_factory, function in _RULE_CASES:
        observed = netlist_factory(function=function)
        scan = scan_connector_footprint_peer_pin_assignments(
            observed,
            declared_references=("J1", "J2"),
            peer_assignment_groups=groups,
        )
        matching = tuple(
            item
            for item in scan.named_divergences
            if item.pin_electrical_type.strip().casefold() == electrical_type
        )
        assert len(matching) == 1
        divergence = matching[0]
        candidate = connector_footprint_named_divergence_candidate(
            divergence,
            rule_id,
            subject="synthetic named divergence",
            message="synthetic review",
        )

        assert isinstance(candidate, ConnectorFootprintNamedDivergenceCandidate)
        assert scan.source.observed is observed
        assert divergence.source is scan.source
        assert divergence.peer_assignment_group == "reviewed-port"
        assert divergence.peer_assignment_basis == (
            "J1: reviewed-port; same source connector map",
            "J2: reviewed-port; same source connector map",
        )
        assert candidate.source_evidence.divergence is divergence
        assert (
            candidate.evidence
            == project_connector_footprint_named_divergence(candidate.source_evidence).evidence
        )


def test_named_divergence_rejects_assignments_stale_against_source() -> None:
    observed = named_power_input_divergence_netlist()
    scan = scan_connector_footprint_peer_pin_assignments(observed)
    (divergence,) = tuple(item for item in scan.named_divergences if item.pin_number == "2")
    changed = named_power_input_divergence_netlist(target_assignments=("BIAS", "BIAS"))
    stale = replace(divergence, source=replace(divergence.source, observed=changed))

    with pytest.raises(ValueError, match="distinct current native nets"):
        connector_footprint_named_divergence_candidate(
            stale,
            "connector.footprint_named_power_input_assignment_divergence",
            subject="stale source",
            message="stale source",
        )


def test_scan_source_copies_and_freezes_authored_peer_group_scope() -> None:
    observed = named_power_input_divergence_netlist()
    groups = {
        "J1": ConnectorComparisonScope("port-a", "Reviewed interface map"),
        "J2": ConnectorComparisonScope("port-a", "Reviewed interface map"),
    }
    scan = scan_connector_footprint_peer_pin_assignments(
        observed,
        peer_assignment_groups=groups,
    )
    groups["J1"] = ConnectorComparisonScope("changed", "changed")

    assert scan.source.peer_assignment_groups == {
        "J1": ConnectorComparisonScope("port-a", "Reviewed interface map"),
        "J2": ConnectorComparisonScope("port-a", "Reviewed interface map"),
    }
    with pytest.raises(TypeError):
        cast(dict[str, ConnectorComparisonScope], scan.source.peer_assignment_groups)["J1"] = (
            ConnectorComparisonScope("changed", "changed")
        )


def test_named_divergence_predicates_delegate_to_the_source_owner() -> None:
    owner = HWREPO / "design_lint_connector_footprint_named_divergence_evidence.py"
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(HWREPO / "connector_footprint_peer_pins.py") < IMPLEMENTATION_MAX_LINES
    for filename, function_name in (
        (
            "connector_footprint_named_power_input_divergence.py",
            "evaluate_footprint_named_power_input_assignment_divergence",
        ),
        (
            "connector_footprint_named_power_output_divergence.py",
            "evaluate_footprint_named_power_output_assignment_divergence",
        ),
        (
            "connector_footprint_named_signal_divergence.py",
            "evaluate_footprint_named_signal_assignment_divergence",
        ),
        (
            "connector_footprint_named_passive_divergence.py",
            "evaluate_footprint_named_passive_assignment_divergence",
        ),
    ):
        route = HWREPO / filename
        tree = ast.parse(route.read_text(encoding="utf-8"), filename=route.name)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        assert line_count(route) < IMPLEMENTATION_MAX_LINES
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "connector_footprint_named_divergence_candidate"
            for node in ast.walk(function)
        )
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Candidate"
            for node in ast.walk(function)
        )
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        )


def test_all_named_divergence_rules_catalog_the_shared_evidence_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    expected_owner = (
        "kicad_tooling/hwrepo/design_lint_connector_footprint_named_divergence_evidence.py#"
        "project_connector_footprint_named_divergence"
    )
    assignment_refs = {
        "kicad_tooling/hwrepo/connector_footprint_peer_assignments.py#connector_footprint_peer_pin_net_map",
        "kicad_tooling/hwrepo/connector_footprint_peer_assignments.py#connector_footprint_peer_pin_assignments",
    }
    rule_ids = {case[0] for case in _RULE_CASES}
    rules = {rule.rule_id: rule for rule in rule_catalog().rules if rule.rule_id in rule_ids}

    assert set(rules) == rule_ids
    for rule in rules.values():
        assert rule.implementation_owner in rule.implementation_refs
        assert expected_owner in rule.implementation_refs
        assert (
            "kicad_tooling/hwrepo/connector_footprint_peer_pin_types.py#"
            "ConnectorFootprintPeerPinScanSource"
        ) in rule.implementation_refs
        assert assignment_refs <= set(rule.implementation_refs)
