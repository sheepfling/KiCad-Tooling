"""Typed source evidence for I2C address-map candidates."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_i2c_address_candidate_evidence import (
    I2cAddressCandidate,
    I2cAddressCollisionEvidence,
    I2cAddressMismatchEvidence,
    I2cUnmappedResponderEvidence,
    project_i2c_address_evidence,
)
from kicad_tooling.hwrepo.design_lint_i2c_candidates import (
    i2c_address_candidates,
    i2c_responder_coverage_candidates,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.i2c_address_models import I2cAddressCoverageReport
from kicad_tooling.hwrepo.i2c_addressing import scan_i2c_address_map
from tests.design_lint_fixtures.i2c_addresses import (
    _NETLIST_HASH,
    address_map,
    address_netlist,
    responder,
    unmapped_responder_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _assert_public_projection_is_stable(candidate: Candidate) -> None:
    assert isinstance(candidate, I2cAddressCandidate)
    projection = project_i2c_address_evidence(candidate.source_evidence)
    assert candidate.rule_id == projection.rule_id
    assert candidate.evidence == projection.evidence
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_address_mismatch_candidate_retains_its_coverage_report_and_entry() -> None:
    specification = address_map(responder("U1", address=0x50))
    observed = address_netlist(specification, strap_values={"U1": 1})
    coverage = scan_i2c_address_map(specification, observed, _NETLIST_HASH)

    (candidate,) = i2c_address_candidates(coverage)

    assert isinstance(candidate, I2cAddressCandidate)
    assert isinstance(candidate.source_evidence, I2cAddressMismatchEvidence)
    assert candidate.source_evidence.coverage == coverage
    assert candidate.source_evidence.entry == coverage.entries[0]
    assert candidate.evidence["U1.bit0"] == ("U1.3 function A0; nets +3V3; resolved 1",)
    _assert_public_projection_is_stable(candidate)


def test_collision_candidate_retains_its_source_bound_responder_group() -> None:
    specification = address_map(responder("U1", strap=False), responder("U2", strap=False))
    observed = address_netlist(specification)
    coverage = scan_i2c_address_map(specification, observed, _NETLIST_HASH)

    (candidate,) = i2c_address_candidates(coverage)

    assert isinstance(candidate, I2cAddressCandidate)
    assert isinstance(candidate.source_evidence, I2cAddressCollisionEvidence)
    assert candidate.source_evidence.coverage == coverage
    assert tuple(entry.reference for entry in candidate.source_evidence.entries) == ("U1", "U2")
    assert candidate.evidence["address"] == ("0x50",)
    _assert_public_projection_is_stable(candidate)


def test_unmapped_responder_candidate_retains_the_native_scan_and_map_state() -> None:
    observed = unmapped_responder_netlist()
    specification = address_map(responder("U2", strap=False))

    candidate = i2c_responder_coverage_candidates(observed, specification)[0]

    assert isinstance(candidate, I2cAddressCandidate)
    assert isinstance(candidate.source_evidence, I2cUnmappedResponderEvidence)
    assert candidate.source_evidence.responder.reference == "U1"
    assert candidate.source_evidence.address_map == specification
    assert candidate.evidence["address_map"] == ("configured",)
    _assert_public_projection_is_stable(candidate)


def test_unmapped_responder_candidate_retains_missing_map_state() -> None:
    observed = unmapped_responder_netlist()

    (candidate,) = i2c_responder_coverage_candidates(observed, None)

    assert isinstance(candidate, I2cAddressCandidate)
    assert isinstance(candidate.source_evidence, I2cUnmappedResponderEvidence)
    assert candidate.source_evidence.address_map is None
    assert candidate.evidence["address_map"] == ("not_configured",)
    _assert_public_projection_is_stable(candidate)


def test_blocked_coverage_cannot_become_mismatch_candidate_source() -> None:
    specification = address_map(responder("U1", strap=False))
    observed = address_netlist(specification)
    complete = scan_i2c_address_map(specification, observed, _NETLIST_HASH)
    blocked = I2cAddressCoverageReport(
        status="BLOCKED",
        netlist_sha256=complete.netlist_sha256,
        entries=complete.entries,
        issue="The address comparison is stale",
    )

    with pytest.raises(ValueError, match="require evaluated coverage"):
        I2cAddressMismatchEvidence(coverage=blocked, entry=complete.entries[0])


def test_candidate_rejects_wire_evidence_that_disagrees_with_its_source() -> None:
    specification = address_map(responder("U1", address=0x50))
    observed = address_netlist(specification, strap_values={"U1": 1})
    coverage = scan_i2c_address_map(specification, observed, _NETLIST_HASH)
    source = I2cAddressMismatchEvidence(coverage=coverage, entry=coverage.entries[0])
    projection = project_i2c_address_evidence(source)
    evidence = dict(projection.evidence)
    evidence["U1.address"] = ("fabricated",)

    with pytest.raises(ValueError, match="must match its typed source projection"):
        I2cAddressCandidate(
            rule_id=projection.rule_id,
            subject="Synthetic address mismatch",
            message="Synthetic projection validation",
            evidence=evidence,
            source_evidence=source,
        )


def test_mismatch_source_entry_must_belong_to_its_coverage_report() -> None:
    specification = address_map(responder("U1", address=0x50))
    observed = address_netlist(specification, strap_values={"U1": 1})
    coverage = scan_i2c_address_map(specification, observed, _NETLIST_HASH)
    unrelated_entry = coverage.entries[0].model_copy(update={"reference": "U99"})

    with pytest.raises(ValueError, match="must belong to its coverage report"):
        I2cAddressMismatchEvidence(coverage=coverage, entry=unrelated_entry)
