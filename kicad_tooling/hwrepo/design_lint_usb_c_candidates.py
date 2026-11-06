"""Translate USB-C port role-map coverage observations."""

from __future__ import annotations

from .design_lint_types import Candidate
from .design_lint_usb_c_port_candidate_evidence import (
    UsbCPortCandidate,
    UsbCPortFindingEvidence,
)
from .design_lint_usb_c_vbus_candidate_evidence import (
    UsbCVbusCapacitanceReviewCandidate,
    UsbCVbusCapacitanceReviewEvidence,
)
from .netlist_contract_models import NetlistContract
from .usb_c_ports import UsbCPortRosterContext, unmapped_usb_c_ports
from .usb_c_vbus_review import usb_c_vbus_capacitance_gaps


def usb_c_port_candidates(
    observed: NetlistContract,
    usb_c_scope: UsbCPortRosterContext,
    reviewed_connector_references: tuple[str, ...],
) -> tuple[Candidate, ...]:
    """Build coverage prompts for USB-C ports absent from their role map."""
    found: list[Candidate] = []
    if usb_c_scope.state == "required":
        usb_c_scope_text = "is not listed in the project USB-C port role map"
    elif usb_c_scope.state == "pending":
        usb_c_scope_text = "is a candidate while the project USB-C port review remains pending"
    elif usb_c_scope.state == "not_applicable":
        usb_c_scope_text = (
            "is a candidate despite the project USB-C review being marked not applicable"
        )
    else:
        usb_c_scope_text = "has no configured project USB-C port role map"

    for port in unmapped_usb_c_ports(observed, usb_c_scope, reviewed_connector_references):
        source_evidence = UsbCPortFindingEvidence(port=port, roster=usb_c_scope)
        found.append(
            UsbCPortCandidate.from_source_evidence(
                source_evidence,
                subject=f"{port.reference}: USB-C role-map coverage",
                message=(
                    f"{port.reference} exports connector pin functions CC1 and CC2 and "
                    f"{usb_c_scope_text}. Review whether this is a USB-C port and, if so, "
                    "record its approved source, sink, or dual-role requirements. The pin names "
                    "do not establish port role, Rp/Rd, controller behavior, VBUS path, or "
                    "protection requirements."
                ),
            )
        )
    return tuple(found)


def usb_c_vbus_capacitance_candidates(
    observed: NetlistContract,
    usb_c_scope: UsbCPortRosterContext,
    reviewed_connector_references: tuple[str, ...],
) -> tuple[Candidate, ...]:
    """Prompt when likely USB-C VBUS lacks a recognized return capacitor."""
    found: list[Candidate] = []
    for gap in usb_c_vbus_capacitance_gaps(
        observed,
        usb_c_scope,
        reviewed_connector_references,
    ):
        source_evidence = UsbCVbusCapacitanceReviewEvidence(gap=gap)
        found.append(
            UsbCVbusCapacitanceReviewCandidate.from_source_evidence(
                source_evidence,
                subject=f"{gap.connector}: USB-C VBUS has no recognized return capacitor",
                message=(
                    f"The fitted connector {gap.connector} exports CC1/CC2, VBUS on "
                    f"{gap.vbus_net}, and return on {gap.return_net}, but no fitted, "
                    "exactly inventoried two-pin capacitor symbol connects those native "
                    "nets. Review the approved port requirement and record an authored "
                    "capacitance map or a reasoned not-applicable decision. Pin functions "
                    "and schematic assignments do not establish a universal requirement, "
                    "capacitance value, PCB placement, copper continuity, or USB compliance."
                ),
            )
        )
    return tuple(found)
