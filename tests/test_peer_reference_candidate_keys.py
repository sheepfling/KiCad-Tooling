"""Peer coverage receives typed candidate identities and rejects evidence drift."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.component_peer_pin_candidate_types import (
    ComponentPeerPinFindingCounts,
)
from kicad_tooling.hwrepo.connector_peer_pin_candidate_results import (
    ConnectorPeerPinFindingCounts,
)
from kicad_tooling.hwrepo.design_lint_bus_candidates import BusCandidateResult
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_candidate_results import DesignLintCandidateScanResult
from kicad_tooling.hwrepo.design_lint_mapped_topology_results import (
    MappedTopologyFindingCounts,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.peer_reference_candidate_keys import (
    CanPeerBusKey,
    I2cPeerBusKey,
    PeerReferenceCandidate,
    PeerReferenceCandidateKeys,
    Rs485PeerPairKey,
    SpiPeerClockKey,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _candidates() -> tuple[PeerReferenceCandidate, ...]:
    return (
        PeerReferenceCandidate(
            rule_id="bus.i2c_peer_reference_review",
            identity=I2cPeerBusKey("I2C_SDA", "I2C_SCL"),
            subject="I2C bus",
            message="Review",
            evidence={"SDA": ("I2C_SDA",), "SCL": ("I2C_SCL",)},
        ),
        PeerReferenceCandidate(
            rule_id="bus.spi_peer_reference_review",
            identity=SpiPeerClockKey("SPI_CLK"),
            subject="SPI clock",
            message="Review",
            evidence={"SCK": ("SPI_CLK",)},
        ),
        PeerReferenceCandidate(
            rule_id="bus.can_peer_reference_review",
            identity=CanPeerBusKey("CAN_H", "CAN_L"),
            subject="CAN bus",
            message="Review",
            evidence={"CANH": ("CAN_H",), "CANL": ("CAN_L",)},
        ),
        PeerReferenceCandidate(
            rule_id="bus.rs485_peer_reference_review",
            identity=Rs485PeerPairKey("Main", "A"),
            subject="RS-485 pair",
            message="Review",
            evidence={"bus": ("Main",), "pair": ("A",)},
        ),
    )


def test_peer_candidate_keys_are_typed_and_case_normalized() -> None:
    keys = PeerReferenceCandidateKeys.from_candidates(_candidates())

    assert keys.i2c_buses == frozenset({("i2c_sda", "i2c_scl")})
    assert keys.spi_clocks == frozenset({"spi_clk"})
    assert keys.can_buses == frozenset({("can_h", "can_l")})
    assert keys.rs485_pairs == frozenset({("main", "a")})


def test_peer_candidate_keys_merge_theme_results() -> None:
    items = _candidates()
    first = PeerReferenceCandidateKeys.from_candidates(items[:2])
    second = PeerReferenceCandidateKeys.from_candidates(items[2:])

    assert first.merge(second) == PeerReferenceCandidateKeys.from_candidates(items)


def test_typed_peer_identity_projects_the_same_public_evidence_and_fingerprints() -> None:
    legacy = _candidates()
    projected = tuple(
        PeerReferenceCandidate.from_identity(
            identity=item.identity,
            subject=item.subject,
            message=item.message,
            evidence={},
        )
        for item in legacy
    )

    assert projected == legacy
    assert tuple(fingerprint(item) for item in projected) == tuple(
        fingerprint(item) for item in legacy
    )


def test_peer_identity_fields_cannot_be_overridden_by_supplemental_evidence() -> None:
    with pytest.raises(ValueError, match="supplied by identity: SDA"):
        PeerReferenceCandidate.from_identity(
            identity=I2cPeerBusKey("I2C_SDA", "I2C_SCL"),
            subject="I2C bus",
            message="Review",
            evidence={"SDA": ("OTHER_NET",)},
        )


def test_typed_scan_results_reject_unmatched_peer_keys() -> None:
    items = _candidates()
    empty = PeerReferenceCandidateKeys.from_candidates(())

    with pytest.raises(ValueError, match="Bus candidate peer keys"):
        BusCandidateResult(candidates=items, peer_reference_keys=empty)
    with pytest.raises(ValueError, match="Candidate scan peer keys"):
        DesignLintCandidateScanResult(
            candidates=items,
            peer_reference_keys=empty,
            connector_peer_pin_finding_counts=ConnectorPeerPinFindingCounts(),
            component_peer_pin_finding_counts=ComponentPeerPinFindingCounts(),
            mapped_topology_finding_counts=MappedTopologyFindingCounts(),
        )


def test_aggregate_scan_result_rejects_connector_counts_that_disagree_with_findings() -> None:
    items = _candidates()

    with pytest.raises(ValueError, match="connector counts must match typed candidates"):
        DesignLintCandidateScanResult(
            candidates=items,
            peer_reference_keys=PeerReferenceCandidateKeys.from_candidates(items),
            connector_peer_pin_finding_counts=ConnectorPeerPinFindingCounts(
                peer_pin_outlier_finding_count=1
            ),
            component_peer_pin_finding_counts=ComponentPeerPinFindingCounts(),
            mapped_topology_finding_counts=MappedTopologyFindingCounts(),
        )


@pytest.mark.parametrize(("index", "field"), ((0, "SDA"), (1, "SCK"), (2, "CANL"), (3, "pair")))
def test_missing_peer_identity_fails_before_coverage(index: int, field: str) -> None:
    candidate = _candidates()[index]
    evidence = dict(candidate.evidence)
    del evidence[field]

    with pytest.raises(ValueError, match=f"needs one {field} value"):
        PeerReferenceCandidateKeys.from_candidates((replace(candidate, evidence=evidence),))


def test_ambiguous_peer_identity_fails_before_coverage() -> None:
    candidate = _candidates()[0]
    with pytest.raises(ValueError, match="needs one SDA value"):
        PeerReferenceCandidateKeys.from_candidates(
            (replace(candidate, evidence={**candidate.evidence, "SDA": ("A", "B")}),)
        )


def test_untyped_peer_candidate_cannot_claim_coverage() -> None:
    source = _candidates()[0]
    untyped = Candidate(
        rule_id=source.rule_id,
        subject=source.subject,
        message=source.message,
        evidence=source.evidence,
    )

    with pytest.raises(TypeError, match="needs a typed peer identity"):
        PeerReferenceCandidateKeys.from_candidates((untyped,))


def test_internal_peer_identity_does_not_change_public_fingerprint() -> None:
    typed = _candidates()[0]
    public_candidate = Candidate(
        rule_id=typed.rule_id,
        subject=typed.subject,
        message=typed.message,
        evidence=typed.evidence,
    )

    assert fingerprint(typed) == fingerprint(public_candidate)


def test_candidate_evidence_is_copied_and_immutable() -> None:
    original = {"SDA": ("SDA_A",), "SCL": ("SCL_A",), "peers": ("J1",)}
    candidate = PeerReferenceCandidate(
        rule_id="bus.i2c_peer_reference_review",
        subject="J1/J2",
        message="Review I2C peers",
        evidence=original,
        identity=I2cPeerBusKey(sda_net="SDA_A", scl_net="SCL_A"),
    )
    expected_fingerprint = fingerprint(candidate)

    original["SDA"] = ("OTHER_NET",)
    assert candidate.evidence["SDA"] == ("SDA_A",)
    assert fingerprint(candidate) == expected_fingerprint
    with pytest.raises(TypeError):
        candidate.evidence["SDA"] = ("OTHER_NET",)  # type: ignore[index]
    assert PeerReferenceCandidateKeys.from_candidates((candidate,)).i2c_buses == frozenset(
        {("sda_a", "scl_a")}
    )
