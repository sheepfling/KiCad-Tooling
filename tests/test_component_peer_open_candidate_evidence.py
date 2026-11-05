"""Source and report contracts for generic component peer open-pin findings."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.component_peer_pin_scan import (
    GENERIC_COMPONENT_MIXED_PIN_TYPES,
    GENERIC_COMPONENT_PIN_TYPES,
    PeerPinAssignmentScan,
    scan_component_peer_pin_assignments,
)
from kicad_tooling.hwrepo.design_lint_component_peer_open_candidate_evidence import (
    ComponentPeerOpenRuleId,
    GenericComponentPeerOpenCandidate,
    GenericComponentPeerOpenScanEvidence,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.component_peer_pin_all_open import (
    generic_component_peer_mixed_netlist,
    generic_component_peer_netlist,
)

RULE_ALL_OPEN: ComponentPeerOpenRuleId = "component.generic_peer_pin_all_open"
RULE_MIXED_OPEN: ComponentPeerOpenRuleId = "component.generic_peer_pin_mixed_open"


def _scan(observed: NetlistContract, rule_id: ComponentPeerOpenRuleId) -> PeerPinAssignmentScan:
    if rule_id == RULE_ALL_OPEN:
        return scan_component_peer_pin_assignments(
            observed,
            electrical_types=GENERIC_COMPONENT_PIN_TYPES,
            require_generic_pin_functions=True,
            assignment_pattern="all_open",
            require_shared_anchor=True,
        )
    return scan_component_peer_pin_assignments(
        observed,
        electrical_types=GENERIC_COMPONENT_MIXED_PIN_TYPES,
        require_generic_pin_functions=True,
        require_shared_anchor=True,
        minimum_peer_count=3,
        minimum_assigned_peer_count=2,
        require_assigned_peers_on_same_net=True,
    )


def _candidate(
    observed: NetlistContract,
    rule_id: ComponentPeerOpenRuleId,
) -> GenericComponentPeerOpenCandidate:
    scan = _scan(observed, rule_id)
    source_scan = GenericComponentPeerOpenScanEvidence.from_scan(
        observed=observed,
        scan=scan,
        declared_references=(),
        rule_id=rule_id,
    )
    identity = scan.outliers[0]
    return GenericComponentPeerOpenCandidate.from_source_evidence(
        source_scan.for_outlier(identity),
        subject="synthetic peer open",
        message="synthetic review prompt",
    )


def test_all_open_candidate_retains_source_and_existing_projection_fields() -> None:
    observed = generic_component_peer_netlist()
    candidate = _candidate(observed, RULE_ALL_OPEN)

    assert candidate.source_evidence.scan_evidence.observed == observed
    assert candidate.source_evidence.scan_evidence.scan == _scan(observed, RULE_ALL_OPEN)
    assert candidate.rule_id == RULE_ALL_OPEN
    assert candidate.evidence["U1.2"] == ()
    assert candidate.evidence["U2.2"] == ()
    assert candidate.evidence["unassigned_pins"] == ("U1.2", "U2.2")
    assert candidate.evidence["shared_anchor_contacts"] == ("U1.1 / U2.1 -> SHARED",)


def test_mixed_open_candidate_retains_source_and_existing_projection_fields() -> None:
    observed = generic_component_peer_mixed_netlist()
    candidate = _candidate(observed, RULE_MIXED_OPEN)

    assert candidate.source_evidence.scan_evidence.observed == observed
    assert candidate.source_evidence.scan_evidence.scan == _scan(observed, RULE_MIXED_OPEN)
    assert candidate.rule_id == RULE_MIXED_OPEN
    assert candidate.evidence["assigned_pins"] == ("U1.2", "U2.2")
    assert candidate.evidence["unassigned_pins"] == ("U3.2",)
    assert candidate.evidence["shared_assignment_net"] == ("LOAD",)
    assert candidate.evidence["shared_anchor_contacts"] == ("U1.1 / U2.1 / U3.1 -> SHARED",)


@pytest.mark.parametrize(
    ("rule_id", "observed", "changed"),
    (
        (
            RULE_ALL_OPEN,
            generic_component_peer_netlist(),
            generic_component_peer_netlist(target_nets=("LOAD", "LOAD")),
        ),
        (
            RULE_MIXED_OPEN,
            generic_component_peer_mixed_netlist(),
            generic_component_peer_mixed_netlist(target_nets=("LOAD_A", "LOAD_B", None)),
        ),
    ),
)
def test_scan_rejects_a_different_current_netlist(
    rule_id: ComponentPeerOpenRuleId,
    observed: NetlistContract,
    changed: NetlistContract,
) -> None:
    with pytest.raises(ValueError, match="current netlist"):
        GenericComponentPeerOpenScanEvidence.from_scan(
            observed=changed,
            scan=_scan(observed, rule_id),
            declared_references=(),
            rule_id=rule_id,
        )


def test_candidate_rejects_an_outlier_from_another_scan() -> None:
    observed = generic_component_peer_netlist()
    scan = _scan(observed, RULE_ALL_OPEN)
    source_scan = GenericComponentPeerOpenScanEvidence.from_scan(
        observed=observed,
        scan=scan,
        declared_references=(),
        rule_id=RULE_ALL_OPEN,
    )
    foreign = _scan(
        generic_component_peer_netlist(references=("U3", "U4")),
        RULE_ALL_OPEN,
    ).outliers[0]

    with pytest.raises(ValueError, match="belong to its source scan"):
        source_scan.for_outlier(foreign)
