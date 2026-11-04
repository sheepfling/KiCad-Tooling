"""Translate USB-C port role-map coverage observations."""

from __future__ import annotations

from .design_lint_types import Candidate
from .design_lint_usb_c_port_candidate_evidence import (
    UsbCPortCandidate,
    UsbCPortFindingEvidence,
)
from .netlist_contract_models import NetlistContract
from .usb_c_ports import UsbCPortRosterContext, unmapped_usb_c_ports


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
