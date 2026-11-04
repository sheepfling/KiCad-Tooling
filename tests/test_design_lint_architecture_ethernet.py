"""Keep Ethernet protocol predicates in focused theme-owned modules."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.bus_ethernet_pair_labels import (
    ethernet_data_label_mismatch_candidates,
    ethernet_management_label_mismatch_candidates,
)
from kicad_tooling.hwrepo.design_lint_bus_ethernet_label_candidate_evidence import (
    EthernetLabelMismatchCandidate,
    project_ethernet_label_mismatch_evidence,
)
from tests.design_lint_fixtures.ethernet_data_labels import ethernet_data_label_netlist
from tests.design_lint_fixtures.ethernet_management_labels import ethernet_management_netlist
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
    pytest.mark.evidence_lint,
]


def test_ethernet_data_label_rule_uses_a_focused_predicate_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "bus.ethernet_data_label_mismatch"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/bus_ethernet_pair_labels.py#ethernet_data_label_mismatch_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/bus_signal_pairs.py#ethernet_data_pair_function_role"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/design_lint_bus_ethernet_label_candidate_evidence.py#"
        "project_ethernet_label_mismatch_evidence"
    ) in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/design_lint_bus_ethernet_label_candidate_evidence.py#"
        "ethernet_data_net_label_role"
    ) in rule.implementation_refs


def test_ethernet_management_label_rule_uses_a_focused_predicate_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.ethernet_management_label_mismatch"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/bus_ethernet_pair_labels.py#"
        "ethernet_management_label_mismatch_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/design_lint_bus_ethernet_label_candidate_evidence.py#"
        "project_ethernet_label_mismatch_evidence"
    ) in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/design_lint_bus_ethernet_label_candidate_evidence.py#"
        "ethernet_management_net_label_role"
    ) in rule.implementation_refs


def test_ethernet_management_unconnected_rule_has_a_bounded_theme_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.ethernet_management_unconnected_pin"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/bus_ethernet_unconnected_management.py#"
        "ethernet_management_unconnected_pin_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/bus_signal_pairs.py#ethernet_management_function_role"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/casefold_mapping_lookup.py#lookup_unique_casefold"
        in rule.implementation_refs
    )
    assert line_count(HWREPO / "bus_ethernet_unconnected_management.py") < IMPLEMENTATION_MAX_LINES


def test_ethernet_label_adapters_retain_the_native_source_and_project_typed_evidence() -> None:
    owner_path = HWREPO / "design_lint_bus_ethernet_label_candidate_evidence.py"
    route_path = HWREPO / "bus_ethernet_pair_labels.py"
    route_tree = ast.parse(route_path.read_text(encoding="utf-8"), filename=route_path.name)
    route_functions = {
        node.name: node for node in route_tree.body if isinstance(node, ast.FunctionDef)
    }

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    for name in (
        "ethernet_data_label_mismatch_candidates",
        "ethernet_management_label_mismatch_candidates",
    ):
        function = route_functions[name]
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(function)
        ), name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        ), name

    data_source = ethernet_data_label_netlist(
        ("TDP", "TDN", "RDP", "RDN"),
        ("ETH_RX_P", "ETH_RX_N", "ETH_TX_P", "ETH_TX_N"),
    )
    management_source = ethernet_management_netlist(labels=("ETH_MDIO", "ETH_MDC"))
    (data_candidate, *_more_data) = ethernet_data_label_mismatch_candidates(data_source)
    (management_candidate, *_more_management) = ethernet_management_label_mismatch_candidates(
        management_source
    )

    for candidate, source in (
        (data_candidate, data_source),
        (management_candidate, management_source),
    ):
        assert isinstance(candidate, EthernetLabelMismatchCandidate)
        assert candidate.source_evidence.observed is source
        assert (
            candidate.evidence
            == project_ethernet_label_mismatch_evidence(candidate.source_evidence).evidence
        )


def test_ethernet_data_unconnected_rule_has_a_bounded_theme_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "bus.ethernet_data_unconnected_pin"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/bus_ethernet_unconnected_data.py#"
        "ethernet_data_unconnected_pin_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/design_lint_ethernet_unconnected_candidates.py#"
        "ethernet_unconnected_pin_candidates" in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/bus_signal_pairs.py#ethernet_data_pair_function_role"
        in rule.implementation_refs
    )
    assert line_count(HWREPO / "bus_ethernet_unconnected_data.py") < IMPLEMENTATION_MAX_LINES
    assert (
        line_count(HWREPO / "design_lint_ethernet_unconnected_candidates.py")
        < IMPLEMENTATION_MAX_LINES
    )
