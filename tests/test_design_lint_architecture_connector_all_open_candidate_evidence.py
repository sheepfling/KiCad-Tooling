"""Guard typed evidence ownership for all-open generic connector peers."""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import replace

import pytest

from kicad_tooling.hwrepo import (
    connector_peer_pin_all_open,
    design_lint_connector_all_open_candidate_evidence,
)
from kicad_tooling.hwrepo.connector_comparison_scope_types import ConnectorComparisonScope
from kicad_tooling.hwrepo.connector_peer_pin_all_open import (
    all_open_generic_connector_peer_pin_candidates,
)
from kicad_tooling.hwrepo.design_lint_connector_all_open_candidate_evidence import (
    ConnectorAllOpenPeerPinCandidate,
    project_connector_all_open_peer_pin_evidence,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.connector_peer_pin_all_open import (
    generic_open_part_id_peer_netlist,
    generic_open_peer_netlist,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.architecture,
    pytest.mark.evidence_lint,
]


@pytest.mark.parametrize(
    ("source_factory", "identity_basis"),
    (
        (generic_open_peer_netlist, "exact_symbol"),
        (generic_open_part_id_peer_netlist, "part_id"),
    ),
)
def test_all_open_candidates_retain_typed_source_and_stable_projection(
    source_factory: Callable[[], NetlistContract],
    identity_basis: str,
) -> None:
    observed = source_factory()
    (candidate,) = all_open_generic_connector_peer_pin_candidates(observed)

    assert isinstance(candidate, ConnectorAllOpenPeerPinCandidate)
    assert candidate.source_evidence.observed is observed
    assert candidate.source_evidence.identity_basis == identity_basis
    assert (
        candidate.evidence
        == project_connector_all_open_peer_pin_evidence(candidate.source_evidence).evidence
    )
    assert candidate.evidence["shared_anchor_contacts"]
    assert all(not pin.assignments for pin in candidate.source_evidence.open_pins)


def test_all_open_source_rejects_a_pin_that_is_now_assigned() -> None:
    (candidate,) = all_open_generic_connector_peer_pin_candidates(generic_open_peer_netlist())
    assert isinstance(candidate, ConnectorAllOpenPeerPinCandidate)
    source = candidate.source_evidence
    changed = source.observed.model_copy(
        update={"nets": {**source.observed.nets, "NEW_NATIVE_NET": ("J1.2",)}}
    )

    with pytest.raises(ValueError, match="remain unassigned"):
        replace(source, observed=changed)


def test_all_open_source_rejects_a_stale_shared_anchor() -> None:
    (candidate,) = all_open_generic_connector_peer_pin_candidates(generic_open_peer_netlist())
    assert isinstance(candidate, ConnectorAllOpenPeerPinCandidate)
    source = candidate.source_evidence
    stale_anchor = replace(source.shared_anchors[0], net="STALE_NATIVE_NET")

    with pytest.raises(ValueError, match="current native net"):
        replace(source, shared_anchors=(stale_anchor,))


def test_reviewed_peer_group_can_replace_the_shared_anchor_evidence() -> None:
    observed = generic_open_peer_netlist(
        references=("J1", "J2"),
        anchor_nets=("PORT_A", "PORT_B"),
    )
    groups = {
        reference: ConnectorComparisonScope(
            "reviewed-serial-peers",
            f"Reviewed {reference} as a serial peer",
        )
        for reference in ("J1", "J2")
    }
    (candidate,) = all_open_generic_connector_peer_pin_candidates(
        observed,
        peer_assignment_groups=groups,
    )

    assert candidate.source_evidence.shared_anchors == ()
    assert candidate.source_evidence.peer_assignment_group == "reviewed-serial-peers"
    assert candidate.evidence["shared_anchor_contacts"] == ()
    with pytest.raises(ValueError, match="shared anchor or reviewed peer group"):
        replace(
            candidate.source_evidence,
            peer_assignment_group=None,
            peer_assignment_basis=(),
        )


def test_all_open_candidate_evidence_has_one_focused_owner() -> None:
    route_path = HWREPO / "connector_peer_pin_all_open.py"
    owner_path = HWREPO / "design_lint_connector_all_open_candidate_evidence.py"
    route_tree = ast.parse(route_path.read_text(encoding="utf-8"), filename=route_path.name)
    route_function = next(
        node
        for node in route_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "all_open_generic_connector_peer_pin_candidates"
    )
    from_source_calls = tuple(
        node
        for node in ast.walk(route_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
    )
    direct_candidates = tuple(
        node
        for node in ast.walk(route_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
    )

    assert line_count(route_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert len(from_source_calls) == 2
    assert not direct_candidates
    assert connector_peer_pin_all_open.ConnectorAllOpenPeerPinCandidate is (
        design_lint_connector_all_open_candidate_evidence.ConnectorAllOpenPeerPinCandidate
    )


def test_active_rule_catalog_names_the_source_evidence_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "connector.generic_peer_pin_all_open"
    )

    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/design_lint_connector_all_open_candidate_evidence.py#"
        "project_connector_all_open_peer_pin_evidence"
    ) in rule.implementation_refs


def test_named_footprint_all_open_rules_use_one_typed_source_projection() -> None:
    owner_path = HWREPO / "design_lint_connector_footprint_all_open_candidate_evidence.py"
    owner_reference = (
        "kicad_tooling/hwrepo/design_lint_connector_footprint_all_open_candidate_evidence.py#"
        "ConnectorFootprintAllOpenCandidate"
    )
    route_functions = (
        (
            "connector_footprint_named_power_input_all_open.py",
            "evaluate_footprint_named_power_input_all_open",
            "connector.footprint_named_power_input_all_open",
        ),
        (
            "connector_footprint_named_power_output_all_open.py",
            "evaluate_footprint_named_power_output_all_open",
            "connector.footprint_named_power_output_all_open",
        ),
        (
            "connector_footprint_named_signal_all_open.py",
            "evaluate_footprint_named_signal_all_open",
            "connector.footprint_named_signal_all_open",
        ),
    )
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    catalog = {item.rule_id: item for item in rule_catalog().rules}
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    for filename, function_name, rule_id in route_functions:
        route_path = HWREPO / filename
        route_tree = ast.parse(route_path.read_text(encoding="utf-8"), filename=filename)
        route_function = next(
            node
            for node in route_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        calls_source_projection = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(route_function)
        )
        direct_candidates = tuple(
            node
            for node in ast.walk(route_function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Candidate"
        )
        rule = catalog[rule_id]

        assert line_count(route_path) < IMPLEMENTATION_MAX_LINES
        assert calls_source_projection
        assert not direct_candidates
        assert owner_reference in rule.implementation_refs
        assert rule.implementation_owner == f"kicad_tooling/hwrepo/{filename}#{function_name}"
