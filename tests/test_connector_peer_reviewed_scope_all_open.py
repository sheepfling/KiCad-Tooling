"""Reviewed peer groups scope all-open generic connector contact review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_comparison_scope_types import ConnectorComparisonScope
from kicad_tooling.hwrepo.connector_peer_pin_all_open import (
    all_open_generic_connector_peer_pin_candidates,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.connector_peer_pin_all_open import (
    generic_open_part_id_peer_netlist,
    generic_open_peer_coverage,
    generic_open_peer_netlist,
    review_generic_peer_pin_policy,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]

_RULE_ID = "connector.generic_peer_pin_all_open"


def test_reviewed_peer_group_prompts_without_a_shared_anchor_and_stays_opt_in() -> None:
    source = generic_open_peer_netlist(
        references=("J1", "J2"),
        anchor_nets=("PORT_A", "PORT_B"),
    )
    shared_group_coverage = generic_open_peer_coverage(
        source,
        groups=("serial-peers", "serial-peers"),
    )
    assert shared_group_coverage.status == "COMPLETE"

    default = evaluate(
        "synthetic-reviewed-peer-open-contact",
        coach(source),
        DesignLintPolicy(),
        connector_coverage=shared_group_coverage,
    )
    default_finding = next(item for item in default.findings if item.rule_id == _RULE_ID)
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"

    reviewed = evaluate(
        "synthetic-reviewed-peer-open-contact",
        coach(source),
        review_generic_peer_pin_policy(),
        connector_coverage=shared_group_coverage,
    )
    finding = next(item for item in reviewed.findings if item.rule_id == _RULE_ID)
    assert finding.mode == "review"
    assert finding.disposition != "RULE_OFF"
    assert finding.evidence["J1.2"] == ()
    assert finding.evidence["J2.2"] == ()
    assert finding.evidence["shared_anchor_contacts"] == ()
    assert finding.evidence["peer_assignment_group"] == ("serial-peers",)
    assert "no other shared-net anchor" in finding.message
    assert "peer similarity does not establish that it must connect" in finding.message

    separate_coverage = generic_open_peer_coverage(
        source,
        groups=("serial-port-1", "serial-port-2"),
    )
    separate = evaluate(
        "synthetic-reviewed-peer-open-contact-control",
        coach(source),
        review_generic_peer_pin_policy(),
        connector_coverage=separate_coverage,
    )
    assert _RULE_ID not in {item.rule_id for item in separate.findings}


def test_reviewed_part_id_peer_group_can_scope_unanchored_contacts() -> None:
    source = generic_open_part_id_peer_netlist(
        references=("J1", "J2"),
        anchor_nets=("PORT_A", "PORT_B"),
    )
    groups = {
        reference: ConnectorComparisonScope(
            "reviewed-serial-peers",
            f"Reviewed {reference} in one cross-symbol serial group",
        )
        for reference in ("J1", "J2")
    }

    (candidate,) = all_open_generic_connector_peer_pin_candidates(
        source,
        peer_assignment_groups=groups,
    )
    assert candidate.source_evidence.identity_basis == "part_id"
    assert candidate.source_evidence.shared_anchors == ()
    assert candidate.evidence["peer_assignment_group"] == ("reviewed-serial-peers",)
    assert all_open_generic_connector_peer_pin_candidates(source) == ()
    assert all_open_generic_connector_peer_pin_candidates(
        source,
        peer_assignment_groups={
            "J1": ConnectorComparisonScope("port-1", "Reviewed separate port"),
            "J2": ConnectorComparisonScope("port-2", "Reviewed separate port"),
        },
    ) == ()

    coverage = generic_open_peer_coverage(source, groups=("serial-peers", "serial-peers"))
    report = evaluate(
        "synthetic-reviewed-part-id-open-contact",
        coach(source),
        review_generic_peer_pin_policy(),
        connector_coverage=coverage,
    )
    findings = tuple(item for item in report.findings if item.rule_id == _RULE_ID)
    assert len(findings) == 1
    assert findings[0].evidence["peer_identity_basis"] == ("part_id",)
    assert findings[0].evidence["shared_anchor_contacts"] == ()


def test_reviewed_peer_group_candidate_is_stable_under_input_reordering() -> None:
    source = generic_open_peer_netlist(anchor_nets=("PORT_A", "PORT_B", "PORT_C"))
    groups = {
        reference: ConnectorComparisonScope(
            "reviewed-peer-set",
            f"Reviewed {reference} as a member of one peer set",
        )
        for reference in ("J1", "J2", "J3")
    }
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(
                reversed(tuple(source.component_pin_numbers.items()))
            ),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )

    (candidate,) = all_open_generic_connector_peer_pin_candidates(
        source,
        peer_assignment_groups=groups,
    )
    (reordered_candidate,) = all_open_generic_connector_peer_pin_candidates(
        reordered,
        peer_assignment_groups=groups,
    )
    assert reordered_candidate == candidate
    assert fingerprint(reordered_candidate) == fingerprint(candidate)
