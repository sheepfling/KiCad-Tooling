"""USB peer-reference candidates retain the scan, review, and map input."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from kicad_tooling.hwrepo.design_lint_usb_peer_candidate_evidence import (
    UsbPeerReferenceCandidate,
    UsbPeerReferenceFindingEvidence,
    project_usb_peer_reference_evidence,
)
from kicad_tooling.hwrepo.design_lint_usb_peer_candidates import usb_peer_reference_candidates
from kicad_tooling.hwrepo.usb_peer_reference_scan import scan_usb_peer_reference_reviews
from kicad_tooling.hwrepo.usb_peer_reference_types import UsbPeerReferenceScan
from tests.usb_peer_reference_support import usb_data_map, usb_peer_netlist


def _scan() -> UsbPeerReferenceScan:
    return scan_usb_peer_reference_reviews(usb_peer_netlist())


def test_usb_peer_candidate_retains_exact_review_scan_and_authored_map() -> None:
    scan = _scan()
    data_path = UsbDataPathCandidateInputs(authored_map=None)

    candidate = usb_peer_reference_candidates(scan, data_path)[0]
    assert isinstance(candidate, UsbPeerReferenceCandidate)
    source = candidate.source_evidence

    assert source.scan is scan
    assert source.review is scan.reviews[0]
    assert source.data_path is data_path
    assert project_usb_peer_reference_evidence(source).evidence == candidate.evidence
    assert candidate.evidence["connector"] == ("J1: Connector:USB_A; Synthetic:USB-A",)
    assert candidate.evidence["USB_D+_link"] == ("J1.1 / U1.1=USB_DP",)
    assert candidate.evidence["USB_data_map_state"] == ("not_configured",)
    assert "USB_data_map_sha256" not in candidate.evidence


def test_usb_peer_candidate_preserves_authored_map_digest_and_review_state() -> None:
    scan = _scan()
    data_path = UsbDataPathCandidateInputs(authored_map=usb_data_map())

    candidate = usb_peer_reference_candidates(scan, data_path)[0]

    assert candidate.evidence["USB_data_map_state"] == ("configured",)
    assert candidate.evidence["USB_reference_policy_state"] == ("not_configured",)
    assert candidate.evidence["USB_data_map_sha256"] == (data_path.map_sha256,)


def test_usb_peer_candidate_rejects_review_detached_from_scan() -> None:
    scan = _scan()
    review = scan.reviews[0]
    detached_scan = replace(scan, reviews=())

    with pytest.raises(ValueError, match="belong to its source scan"):
        UsbPeerReferenceFindingEvidence(
            scan=detached_scan,
            review=review,
            data_path=UsbDataPathCandidateInputs(authored_map=None),
        )


def test_usb_peer_candidate_rejects_projection_mismatch() -> None:
    scan = _scan()
    candidate = usb_peer_reference_candidates(
        scan,
        UsbDataPathCandidateInputs(authored_map=None),
    )[0]

    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"connector": ("wrong",)})
