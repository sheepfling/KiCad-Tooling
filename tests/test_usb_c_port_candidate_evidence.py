"""USB-C port candidates retain their typed endpoint and roster source."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_usb_c_port_candidate_evidence import (
    UsbCPortCandidate,
    UsbCPortFindingEvidence,
    project_usb_c_port_evidence,
)
from kicad_tooling.hwrepo.usb_c_ports import UnmappedUsbCPort, UsbCPortRosterContext


def _port() -> UnmappedUsbCPort:
    return UnmappedUsbCPort(
        reference="J3",
        cc1_pins=("J3.4",),
        cc2_pins=("J3.5",),
        signal_assignments=("J3.4=CC1", "J3.5=CC2"),
    )


def test_usb_c_port_projection_preserves_roster_source_and_pin_assignments() -> None:
    source = UsbCPortFindingEvidence(
        port=_port(),
        roster=UsbCPortRosterContext(
            state="required",
            source_path="contracts/electrical.json",
            source_sha256="b" * 64,
        ),
    )

    candidate = UsbCPortCandidate.from_source_evidence(
        source,
        subject="J3: USB-C role-map coverage",
        message="Review the connector role.",
    )

    assert dict(project_usb_c_port_evidence(source).evidence) == {
        "CC1_pins": ("J3.4",),
        "CC2_pins": ("J3.5",),
        "CC_assignments": ("J3.4=CC1", "J3.5=CC2"),
        "USB_C_roster_state": ("required",),
        "electrical_contract_path": ("contracts/electrical.json",),
        "electrical_contract_sha256": ("b" * 64,),
    }
    assert candidate.source_evidence is source


def test_usb_c_pending_roster_does_not_fabricate_source_identity() -> None:
    source = UsbCPortFindingEvidence(
        port=_port(),
        roster=UsbCPortRosterContext(state="pending"),
    )

    evidence = project_usb_c_port_evidence(source).evidence

    assert evidence["USB_C_roster_state"] == ("pending",)
    assert "electrical_contract_path" not in evidence
    assert "electrical_contract_sha256" not in evidence


def test_usb_c_candidate_rejects_projection_mismatch() -> None:
    source = UsbCPortFindingEvidence(
        port=_port(),
        roster=UsbCPortRosterContext(state="required"),
    )

    with pytest.raises(ValueError, match="typed source projection"):
        UsbCPortCandidate(
            rule_id="bus.usb_c_unreviewed_port",
            subject="review",
            message="inspect",
            evidence={"CC1_pins": ("wrong",)},
            source_evidence=source,
        )
