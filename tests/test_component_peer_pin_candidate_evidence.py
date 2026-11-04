"""Generic component-peer findings retain typed, immutable scan evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.component_peer_pin_evaluation import (
    component_peer_pin_assignment_scans,
)
from kicad_tooling.hwrepo.component_peer_pin_findings import (
    component_peer_power_pin_assignment_divergences,
)
from kicad_tooling.hwrepo.component_peer_pin_scan import PeerPinAssignmentOutlier
from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_component_peer_candidate_evidence import (
    GenericPeerPinCandidate,
    GenericPowerInputDivergenceEvidence,
    NamedPowerInputAllOpenEvidence,
    NamedPowerInputDivergenceEvidence,
    NamedPowerInputOpenEvidence,
    PeerPowerPinDivergenceCandidate,
    PeerUnconnectedPinEvidence,
    PowerInputPeerCandidate,
    UnconnectedPeerPinCandidate,
    project_peer_power_pin_divergence,
    project_peer_unconnected_pin_evidence,
    project_power_input_peer_evidence,
)
from kicad_tooling.hwrepo.design_lint_component_peer_candidates import (
    component_peer_candidates,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.component_peer_pin_support import (
    BIDIRECTIONAL_RULE_ID,
    INPUT_RULE_ID,
    SIGNAL_RULE_ID,
    peer_component_pin_netlist,
)
from tests.component_peer_pin_support import (
    RULE_ID as POWER_OUTPUT_RULE_ID,
)
from tests.component_peer_power_assignment_support import RULE_ID as POWER_PIN_DIVERGENCE_RULE_ID
from tests.component_peer_power_assignment_support import peer_power_netlist
from tests.component_peer_power_input_support import (
    GENERIC_PEER_POWER_INPUT_RULE_ID,
    NAMED_PEER_POWER_INPUT_ALL_OPEN_RULE_ID,
    NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID,
    NAMED_PEER_POWER_INPUT_OPEN_RULE_ID,
    generic_peer_power_input_netlist,
    named_peer_power_input_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def test_generic_peer_finding_retains_its_scan_record_and_public_projection() -> None:
    observed = peer_component_pin_netlist(
        references=("U1", "U2", "U3"),
        pin_nets=("PEER_DATA", "PEER_DATA", "OTHER_DATA"),
        default_symbol="Synthetic:PeerModule",
        pin_electrical_types=("passive", "passive", "passive"),
        pin_function="Pin_2",
    )
    scans = component_peer_pin_assignment_scans(observed)
    candidate = next(
        item
        for item in component_peer_candidates(observed, peer_pin_scans=scans)
        if item.rule_id == "component.generic_peer_pin_assignment_outlier"
    )

    assert isinstance(candidate, GenericPeerPinCandidate)
    assert candidate.source_evidence == scans.generic_assignment_outlier.outliers[0]
    assert candidate.evidence == {
        "U1.2": ("PEER_DATA",),
        "U2.2": ("PEER_DATA",),
        "U3.2": ("OTHER_DATA",),
        "peer_group_basis": ("exact_symbol",),
        "peer_group_identity": ("Synthetic:PeerModule",),
        "peer_group_symbols": ("Synthetic:PeerModule",),
        "symbol": ("Synthetic:PeerModule",),
        "pin_number": ("2",),
        "pin_function": ("Pin_2",),
        "pin_electrical_type": ("passive",),
        "majority_net": ("PEER_DATA",),
        "outlier_pins": ("U3.2",),
        "shared_anchor_contacts": ("U1.1 / U2.1 / U3.1 -> DATA",),
    }
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_peer_scan_record_copies_and_freezes_assignments() -> None:
    assignments = {"U1.2": ("NET_A",), "U2.2": ("NET_B",)}
    source = PeerPinAssignmentOutlier(
        symbol="Synthetic:PeerModule",
        pin_number="2",
        electrical_type="passive",
        assignments=assignments,
        peer_identity_basis="exact_symbol",
        peer_identity="Synthetic:PeerModule",
        peer_symbols=("Synthetic:PeerModule",),
        shared_anchor_contacts=("U1.1 / U2.1 -> DATA",),
        majority_net="NET_A",
        outlier_pins=("U2.2",),
    )
    assignments["U1.2"] = ("CHANGED",)

    assert source.assignments["U1.2"] == ("NET_A",)
    with pytest.raises(TypeError):
        source.assignments["U1.2"] = ("CHANGED",)  # type: ignore[index]


def test_generic_peer_candidate_rejects_evidence_that_drifted_from_source() -> None:
    source = PeerPinAssignmentOutlier(
        symbol="Synthetic:PeerModule",
        pin_number="2",
        electrical_type="passive",
        assignments={"U1.2": ("NET_A",), "U2.2": ("NET_B",)},
        peer_identity_basis="exact_symbol",
        peer_identity="Synthetic:PeerModule",
        peer_symbols=("Synthetic:PeerModule",),
        shared_anchor_contacts=("U1.1 / U2.1 -> DATA",),
        majority_net="NET_A",
        outlier_pins=("U2.2",),
    )
    candidate = GenericPeerPinCandidate.from_source_evidence(
        source,
        subject="synthetic subject",
        message="synthetic review",
    )

    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"majority_net": ("OTHER",)})


@pytest.mark.power_lint
@pytest.mark.evidence_lint
@pytest.mark.parametrize(
    ("observed", "rule_id", "scan_name", "source_type"),
    (
        (
            generic_peer_power_input_netlist(),
            GENERIC_PEER_POWER_INPUT_RULE_ID,
            "power_input_assignment_divergence",
            GenericPowerInputDivergenceEvidence,
        ),
        (
            named_peer_power_input_netlist(assignments=("RAIL_A", "RAIL_B")),
            NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID,
            "named_power_input_assignment_divergence",
            NamedPowerInputDivergenceEvidence,
        ),
        (
            named_peer_power_input_netlist(),
            NAMED_PEER_POWER_INPUT_OPEN_RULE_ID,
            "power_input_open_assignment",
            NamedPowerInputOpenEvidence,
        ),
        (
            named_peer_power_input_netlist(assignments=(None, None)),
            NAMED_PEER_POWER_INPUT_ALL_OPEN_RULE_ID,
            "named_power_input_all_open",
            NamedPowerInputAllOpenEvidence,
        ),
    ),
    ids=("generic-split", "named-split", "named-open", "named-all-open"),
)
def test_power_input_candidates_retain_their_typed_scan_records(
    observed: NetlistContract,
    rule_id: str,
    scan_name: str,
    source_type: type[object],
) -> None:
    scans = component_peer_pin_assignment_scans(observed)
    candidate = next(
        item
        for item in component_peer_candidates(observed, peer_pin_scans=scans)
        if item.rule_id == rule_id
    )

    assert isinstance(candidate, PowerInputPeerCandidate)
    assert isinstance(candidate.source_evidence, source_type)
    assert candidate.source_evidence.outlier is getattr(scans, scan_name).outliers[0]
    assert (
        candidate.evidence == project_power_input_peer_evidence(candidate.source_evidence).evidence
    )
    legacy_projection = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(legacy_projection)
    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"pin_number": ("forged",)})


@pytest.mark.evidence_lint
@pytest.mark.parametrize(
    ("kind", "scan_name", "rule_id", "electrical_type", "pin_function"),
    (
        ("power_output", "power_output", POWER_OUTPUT_RULE_ID, "power_out", "OUT"),
        ("signal_output", "signal_output", SIGNAL_RULE_ID, "output", "OUT"),
        ("signal_input", "signal_input", INPUT_RULE_ID, "input", "IN"),
        ("bidirectional", "bidirectional", BIDIRECTIONAL_RULE_ID, "bidirectional", "DATA_IO"),
    ),
)
def test_unconnected_peer_candidates_retain_their_role_specific_scan_records(
    kind: str,
    scan_name: str,
    rule_id: str,
    electrical_type: str,
    pin_function: str,
) -> None:
    observed = peer_component_pin_netlist(
        references=("U1", "U2"),
        pin_nets=("SYNTHETIC_NET", None),
        default_symbol="Synthetic:UnconnectedPeer",
        pin_electrical_types=(electrical_type, electrical_type),
        pin_function=pin_function,
    )
    scans = component_peer_pin_assignment_scans(observed)
    candidate = next(
        item
        for item in component_peer_candidates(observed, peer_pin_scans=scans)
        if item.rule_id == rule_id
    )

    assert isinstance(candidate, UnconnectedPeerPinCandidate)
    assert isinstance(candidate.source_evidence, PeerUnconnectedPinEvidence)
    assert candidate.source_evidence.kind == kind
    assert candidate.source_evidence.outlier is getattr(scans, scan_name).outliers[0]
    assert (
        candidate.evidence
        == project_peer_unconnected_pin_evidence(candidate.source_evidence).evidence
    )
    legacy_projection = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(legacy_projection)
    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"pin_number": ("forged",)})


@pytest.mark.evidence_lint
@pytest.mark.power_lint
def test_recognized_power_pin_candidates_retain_divergence_records() -> None:
    observed = peer_power_netlist()
    scans = component_peer_pin_assignment_scans(observed)
    expected_sources = component_peer_power_pin_assignment_divergences(observed)
    candidates = tuple(
        item
        for item in component_peer_candidates(observed, peer_pin_scans=scans)
        if item.rule_id == POWER_PIN_DIVERGENCE_RULE_ID
    )

    assert len(candidates) == len(expected_sources)
    for candidate in candidates:
        assert isinstance(candidate, PeerPowerPinDivergenceCandidate)
        assert candidate.source_evidence.divergence in expected_sources
        assert (
            candidate.evidence
            == project_peer_power_pin_divergence(candidate.source_evidence).evidence
        )
        legacy_projection = Candidate(
            rule_id=candidate.rule_id,
            subject=candidate.subject,
            message=candidate.message,
            evidence=candidate.evidence,
        )
        assert fingerprint(candidate) == fingerprint(legacy_projection)
        with pytest.raises(ValueError, match="typed source projection"):
            replace(candidate, evidence={"peer_role": ("forged",)})
