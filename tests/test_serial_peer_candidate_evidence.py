"""Serial-peer projections keep native scan and authored roster sources."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_serial_peer_candidate_evidence import (
    SerialPeerCandidate,
    SerialPeerReferenceFindingEvidence,
    UnmappedSerialPeerFindingEvidence,
    project_serial_peer_evidence,
)
from kicad_tooling.hwrepo.serial_participants import (
    SerialNativePeerLink,
    SerialPeerRosterContext,
    UnmappedSerialPeer,
)
from kicad_tooling.hwrepo.serial_peer_reference_types import (
    SerialLabelPeerLink,
    SerialPeerReferenceReview,
    SerialPeerReferenceScan,
    SerialReferenceDomain,
    SerialReferencePinAssignment,
)


def _scope() -> SerialPeerRosterContext:
    return SerialPeerRosterContext(
        state="required",
        source_path="electrical/serial-peers.toml",
        source_sha256="a" * 64,
    )


def _reference_scan(
    *,
    include_native_link: bool,
    include_label_link: bool,
) -> tuple[SerialPeerReferenceScan, SerialPeerReferenceReview]:
    native_links = (
        (
            SerialNativePeerLink(
                output_reference="U1",
                output_pin="U1.1",
                output_function="TX",
                output_type="output",
                input_reference="U2",
                input_pin="U2.1",
                input_function="RX",
                input_type="input",
                net="UART_TX",
            ),
        )
        if include_native_link
        else ()
    )
    label_links = (
        (
            SerialLabelPeerLink(
                channel="uart1",
                tx_net="UART1_TX",
                rx_net="UART1_RX",
                first_reference="U1",
                second_reference="U2",
                first_tx_pin="U1.1",
                second_tx_pin="U2.1",
                first_rx_pin="U1.2",
                second_rx_pin="U2.2",
            ),
        )
        if include_label_link
        else ()
    )
    review = SerialPeerReferenceReview(
        first_reference="U1",
        second_reference="U2",
        first_reference_domain=SerialReferenceDomain(
            net="GND_A",
            pins=(SerialReferencePinAssignment("U1.3", "GND", "passive", "GND_A"),),
        ),
        second_reference_domain=SerialReferenceDomain(
            net="GND_B",
            pins=(SerialReferencePinAssignment("U2.3", "GND", "passive", "GND_B"),),
        ),
        links=native_links,
        label_links=label_links,
    )
    scan = SerialPeerReferenceScan(
        reviews=(review,),
        link_entries=(),
        native_peer_link_count=len(native_links),
        label_peer_link_count=len(label_links),
        supported_reference_link_count=1,
        incomplete_reference_link_count=0,
        common_reference_link_count=0,
        separate_reference_link_count=1,
        mapped_separate_reference_link_count=0,
    )
    return scan, review


def test_unmapped_peer_projection_retains_roster_scope_and_discovery_source() -> None:
    peer = UnmappedSerialPeer(
        reference="U1",
        channel="uart1",
        tx_pins=("U1.1",),
        rx_pins=("U1.2",),
        signal_assignments=("U1.1: TX on UART1_TX", "U1.2: RX on UART1_RX"),
        discovery_basis="pin_function",
    )
    source = UnmappedSerialPeerFindingEvidence(peer, _scope())
    projection = project_serial_peer_evidence(source)
    candidate = SerialPeerCandidate.from_source_evidence(
        source,
        subject="U1: serial-peer map coverage (uart1)",
        message="Review the endpoint roster.",
    )

    assert projection.rule_id == "bus.serial_unmapped_peer"
    assert dict(projection.evidence) == {
        "interface_channel": ("uart1",),
        "TX_pins": ("U1.1",),
        "RX_pins": ("U1.2",),
        "assigned_signal_pins": ("U1.1: TX on UART1_TX", "U1.2: RX on UART1_RX"),
        "discovery_basis": ("pin_function",),
        "serial_peer_map_state": ("required",),
        "electrical_contract_path": ("electrical/serial-peers.toml",),
        "electrical_contract_sha256": ("a" * 64,),
    }
    assert candidate.source_evidence is source
    assert candidate.evidence == projection.evidence


@pytest.mark.parametrize(
    ("include_native_link", "include_label_link", "expected_fields"),
    [
        pytest.param(
            True,
            False,
            {
                "shared_serial_pin_assignments": (
                    "UART_TX: U1.1 (TX, output) -> U2.1 (RX, input)",
                ),
            },
            id="native-link",
        ),
        pytest.param(
            False,
            True,
            {
                "serial_label_link_assignments": (
                    "uart1: TX UART1_TX (U1.1, U2.1); RX UART1_RX (U1.2, U2.2)",
                ),
                "discovery_basis": ("net_label",),
            },
            id="label-link",
        ),
        pytest.param(
            True,
            True,
            {
                "shared_serial_pin_assignments": (
                    "UART_TX: U1.1 (TX, output) -> U2.1 (RX, input)",
                ),
                "serial_label_link_assignments": (
                    "uart1: TX UART1_TX (U1.1, U2.1); RX UART1_RX (U1.2, U2.2)",
                ),
                "discovery_basis": ("native_pin_function", "net_label"),
            },
            id="native-and-label-link",
        ),
    ],
)
def test_reference_projection_retains_review_scan_and_conditional_links(
    include_native_link: bool,
    include_label_link: bool,
    expected_fields: dict[str, tuple[str, ...]],
) -> None:
    scan, review = _reference_scan(
        include_native_link=include_native_link,
        include_label_link=include_label_link,
    )
    source = SerialPeerReferenceFindingEvidence(scan, review, _scope())
    projection = project_serial_peer_evidence(source)
    candidate = SerialPeerCandidate.from_source_evidence(
        source,
        subject="U1 / U2: serial reference-domain review",
        message="Review the reference topology.",
    )

    assert projection.rule_id == "bus.serial_peer_reference_review"
    assert dict(projection.evidence) == {
        "first_component": ("U1",),
        "second_component": ("U2",),
        "first_reference_net": ("GND_A",),
        "first_reference_pin_assignments": ("U1.3 (GND, passive)=GND_A",),
        "second_reference_net": ("GND_B",),
        "second_reference_pin_assignments": ("U2.3 (GND, passive)=GND_B",),
        "serial_peer_map_state": ("required",),
        **expected_fields,
        "electrical_contract_path": ("electrical/serial-peers.toml",),
        "electrical_contract_sha256": ("a" * 64,),
    }
    assert source.scan is scan
    assert source.review is review
    assert candidate.source_evidence is source
    assert candidate.evidence == projection.evidence


def test_reference_source_rejects_a_review_from_another_scan() -> None:
    _scan, review = _reference_scan(include_native_link=True, include_label_link=False)
    other_scan, _other_review = _reference_scan(
        include_native_link=False,
        include_label_link=True,
    )

    with pytest.raises(ValueError, match="must belong to its source scan"):
        SerialPeerReferenceFindingEvidence(other_scan, review, _scope())


def test_serial_candidate_rejects_a_projection_mismatch() -> None:
    peer = UnmappedSerialPeer("U1", "uart1", ("U1.1",), ("U1.2",), ("U1.1: TX",), "pin_function")
    source = UnmappedSerialPeerFindingEvidence(peer, _scope())

    with pytest.raises(ValueError, match="typed source projection"):
        SerialPeerCandidate(
            rule_id="bus.serial_unmapped_peer",
            subject="review",
            message="inspect",
            evidence={"interface_channel": ("wrong",)},
            source_evidence=source,
        )


def test_pending_roster_has_no_fabricated_contract_identity() -> None:
    peer = UnmappedSerialPeer("U1", "uart1", ("U1.1",), ("U1.2",), ("U1.1: TX",), "net_label")
    source = UnmappedSerialPeerFindingEvidence(
        peer,
        SerialPeerRosterContext(state="pending"),
    )

    evidence = project_serial_peer_evidence(source).evidence

    assert evidence["serial_peer_map_state"] == ("pending",)
    assert "electrical_contract_path" not in evidence
    assert "electrical_contract_sha256" not in evidence
