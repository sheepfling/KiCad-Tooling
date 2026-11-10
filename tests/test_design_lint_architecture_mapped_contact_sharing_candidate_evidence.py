"""Guard typed evidence ownership for source-mapped connector contacts sharing nets."""

from __future__ import annotations

import ast
from dataclasses import replace
from typing import cast

import pytest

from kicad_tooling.hwrepo.connector_mapped_shield_signal_sharing import (
    mapped_shields_sharing_signal_nets,
    mapped_signals_sharing_return_nets,
)
from kicad_tooling.hwrepo.connector_mapped_supply_signal_sharing import (
    mapped_supply_signal_sharing_net_candidates,
)
from kicad_tooling.hwrepo.connector_peer_pin_models import ConnectorPinRole
from kicad_tooling.hwrepo.design_lint_connector_mapped_contact_sharing_candidate_evidence import (
    MappedConnectorContactSharingCandidate,
    MappedContactSharingRole,
    project_mapped_connector_contact_sharing_evidence,
)
from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


@pytest.mark.parametrize(
    ("roles", "primary_role"),
    (
        (("shield", "signal"), "shield"),
        (("return", "signal"), "return"),
        (("supply", "signal"), "supply"),
    ),
)
def test_mapped_role_candidate_retains_current_catalog_and_pin_records(
    roles: tuple[ConnectorPinRole, ConnectorPinRole],
    primary_role: MappedContactSharingRole,
) -> None:
    observed = signal_sharing_netlist()
    coverage = signal_sharing_coverage(
        observed,
        signal_names=("PRIMARY_ROLE", "UART_RX"),
        roles=roles,
    )

    if primary_role == "supply":
        (candidate,) = mapped_supply_signal_sharing_net_candidates(observed, coverage)
        assert candidate.rule_id == "connector.mapped_supply_signal_share_net"
        assert candidate.evidence["supply_component_pin"] == ("J1.1",)
        assert candidate.evidence["signal_component_pin"] == ("J1.2",)
        assert candidate.evidence["interface_catalog_sha256"] == ("c" * 64,)
        return
    if primary_role == "shield":
        (candidate,) = mapped_shields_sharing_signal_nets(observed, coverage)
    else:
        (candidate,) = mapped_signals_sharing_return_nets(observed, coverage)

    assert isinstance(candidate, MappedConnectorContactSharingCandidate)
    assert candidate.source_evidence.observed is observed
    assert candidate.source_evidence.coverage == coverage
    assert candidate.source_evidence.contacts.primary_role == primary_role
    assert candidate.source_evidence.contacts.primary_contacts[0].component_pin == "J1.1"
    assert candidate.source_evidence.contacts.signal_contacts[0].component_pin == "J1.2"
    assert (
        candidate.evidence
        == project_mapped_connector_contact_sharing_evidence(candidate.source_evidence).evidence
    )


def test_mapped_role_adapters_only_use_typed_candidate_projection() -> None:
    route = HWREPO / "connector_mapped_shield_signal_sharing.py"
    tree = ast.parse(route.read_text(encoding="utf-8"), filename=route.name)

    assert line_count(route) < IMPLEMENTATION_MAX_LINES
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name in (
        "mapped_shields_sharing_signal_nets",
        "mapped_signals_sharing_return_nets",
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


def test_mapped_source_rejects_tampered_net_and_unknown_role() -> None:
    observed = signal_sharing_netlist()
    coverage = signal_sharing_coverage(
        observed,
        signal_names=("CABLE_SHIELD", "UART_RX"),
        roles=("shield", "signal"),
    )
    (candidate,) = mapped_shields_sharing_signal_nets(observed, coverage)
    assert isinstance(candidate, MappedConnectorContactSharingCandidate)
    source = candidate.source_evidence

    with pytest.raises(ValueError, match="share one assigned native net"):
        replace(
            source,
            contacts=replace(source.contacts, net_name="SYNTHETIC_OTHER_NET"),
        )
    with pytest.raises(ValueError, match="primary role must be shield, return, or supply"):
        replace(source.contacts, primary_role=cast(MappedContactSharingRole, "power"))


def test_mapped_role_candidate_owner_checks_size_and_canonical_source_records() -> None:
    owner = HWREPO / "design_lint_connector_mapped_contact_sharing_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {
        "MappedConnectorContactsAtNet",
        "MappedConnectorContactSharingFindingEvidence",
        "MappedConnectorContactSharingCandidate",
    } <= classes
    assert "project_mapped_connector_contact_sharing_evidence" in functions
    imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "connector_coverage_models"
        for alias in node.names
    }
    assert "ConnectorMappedPinEvidence" in imports
