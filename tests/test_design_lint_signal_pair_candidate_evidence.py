"""Signal-pair candidates retain typed sources and a stable report projection."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from kicad_tooling.hwrepo.bus_signal_pairs import (
    ComplementaryLineGap,
    ComplementaryPairSide,
    complementary_signal_gaps,
)
from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_signal_pair_candidate_evidence import (
    SignalPairCandidate,
)
from kicad_tooling.hwrepo.design_lint_signal_pair_candidates import (
    complementary_signal_candidates,
    named_differential_pair_candidates,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.differential_pair_names import NamedDifferentialPair
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures import complementary_usb_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _assert_fingerprint_matches_public_candidate(candidate: SignalPairCandidate) -> None:
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_complementary_candidate_retains_its_scan_record_and_wire_fields() -> None:
    observed = complementary_usb_netlist(positive_net="USB_DATA", negative_net="USB_DATA")
    source = complementary_signal_gaps(observed)[0]
    candidate = complementary_signal_candidates(observed)[0]

    assert isinstance(candidate, SignalPairCandidate)
    assert candidate.source_evidence == source
    assert candidate.rule_id == "bus.complementary_pair_assignment"
    assert candidate.evidence == {
        "positive_pins": ("J1.1",),
        "negative_pins": ("J1.2",),
        "positive_nets": ("USB_DATA",),
        "negative_nets": ("USB_DATA",),
    }
    _assert_fingerprint_matches_public_candidate(candidate)


def test_alias_candidate_projects_the_retained_basis_and_digest() -> None:
    source = ComplementaryLineGap(
        reference="U1",
        family="Ethernet TX",
        reason="one or both pair pins lack a unique schematic net assignment",
        pins={"positive": ("U1.1",), "negative": ("U1.2",)},
        nets={"positive": ("TX_P",), "negative": ()},
        alias_symbol="Synthetic:EthernetPhy",
        alias_basis="Reviewed Ethernet TX pin-function alias",
        alias_sha256="a" * 64,
    )
    candidate = SignalPairCandidate.from_source_evidence(
        source,
        subject="U1: Ethernet TX pair",
        message="synthetic review",
    )

    assert candidate.evidence == {
        "positive_pins": ("U1.1",),
        "negative_pins": ("U1.2",),
        "positive_nets": ("TX_P",),
        "negative_nets": (),
        "alias_symbol": ("Synthetic:EthernetPhy",),
        "alias_basis": ("Reviewed Ethernet TX pin-function alias",),
        "alias_sha256": ("a" * 64,),
    }
    assert candidate.source_evidence is source


def test_complementary_scan_records_freeze_compatibility_side_maps() -> None:
    pins: dict[ComplementaryPairSide, tuple[str, ...]] = {
        "positive": ("U1.1",),
        "negative": ("U1.2",),
    }
    nets: dict[ComplementaryPairSide, tuple[str, ...]] = {
        "positive": ("TX_P",),
        "negative": ("TX_N",),
    }
    source = ComplementaryLineGap(
        reference="U1",
        family="Ethernet TX",
        reason="one or both pair pins lack a unique schematic net assignment",
        pins=pins,
        nets=nets,
    )
    pins["positive"] = ("U9.1",)
    nets["positive"] = ("OTHER",)

    assert source.positive_pins == ("U1.1",)
    assert source.positive_nets == ("TX_P",)
    assert isinstance(source.pins, MappingProxyType)
    assert isinstance(source.nets, MappingProxyType)
    with pytest.raises(TypeError):
        source.pins["positive"] = ("U9.1",)  # type: ignore[index]


def test_named_pair_candidate_retains_its_source_record() -> None:
    observed = NetlistContract(
        components={},
        nets={"USB_DP": ("J1.1",), "USB_DM": ("J1.2",)},
    )
    candidate = named_differential_pair_candidates(observed)[0]

    assert isinstance(candidate, SignalPairCandidate)
    assert isinstance(candidate.source_evidence, NamedDifferentialPair)
    assert candidate.evidence == {
        "positive_net": ("USB_DP",),
        "positive_references": ("J1.1",),
        "negative_net": ("USB_DM",),
        "negative_references": ("J1.2",),
        "naming_pattern": ("_DP/_DM",),
    }
    _assert_fingerprint_matches_public_candidate(candidate)


def test_signal_pair_candidate_rejects_report_evidence_that_drifted_from_source() -> None:
    source = NamedDifferentialPair(
        positive_net="USB_DP",
        negative_net="USB_DM",
        naming_pattern="_DP/_DM",
        positive_references=("J1.1",),
        negative_references=("J1.2",),
    )
    with pytest.raises(ValueError, match="typed source projection"):
        SignalPairCandidate(
            rule_id="signal.named_pair_without_reviewed_requirement",
            subject="USB_DP / USB_DM",
            message="synthetic review",
            evidence={"positive_net": ("OTHER",)},
            source_evidence=source,
        )
