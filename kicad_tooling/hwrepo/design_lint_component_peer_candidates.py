"""Translate same-identity component peer pin assignment observations."""

from __future__ import annotations

from .component_peer_pin_findings import component_peer_power_pin_assignment_divergences
from .component_peer_pin_scan import ComponentPeerPinAssignmentScans, PeerPinAssignmentOutlier
from .design_lint_types import Candidate
from .models import NetlistContract


def _component_peer_identity_context(
    group: PeerPinAssignmentOutlier,
) -> tuple[str, str, str, dict[str, tuple[str, ...]]]:
    """Describe the exact source identity that made two components comparable."""
    if group.peer_identity_basis == "part_id":
        subject_identity = f"PART_ID {group.peer_identity}"
        identity_text = (
            f"the same native PART_ID {group.peer_identity!r} across distinct native symbols"
        )
        independent_net_text = "a shared PART_ID does not require peer pins to share a net"
    else:
        subject_identity = group.peer_identity
        identity_text = f"the exact native symbol {group.peer_identity!r}"
        independent_net_text = "identical symbols do not require peer pins to share a net"
    evidence: dict[str, tuple[str, ...]] = {
        "peer_group_basis": (group.peer_identity_basis,),
        "peer_group_identity": (group.peer_identity,),
        "peer_group_symbols": group.peer_symbols,
    }
    if group.peer_identity_basis == "exact_symbol":
        evidence["symbol"] = (group.peer_identity,)
    return subject_identity, identity_text, independent_net_text, evidence


def component_peer_candidates(
    observed: NetlistContract,
    *,
    peer_pin_scans: ComponentPeerPinAssignmentScans,
    reviewed_connector_references: tuple[str, ...] = (),
    control_pin_keys: frozenset[str] = frozenset(),
) -> tuple[Candidate, ...]:
    """Build review prompts for comparable components with divergent peer pins."""
    found: list[Candidate] = []
    for group in component_peer_power_pin_assignment_divergences(
        observed, reviewed_connector_references
    ):
        if group.peer_identity_basis == "part_id" and group.role == "ground/return":
            message = (
                "The same recognized return pin on fitted non-connector components sharing this "
                "native PART_ID across distinct symbols is assigned to different nets. Review "
                "whether the domains are intentionally separate or a return connection is missing; "
                "matching part identity and pin metadata do not prove the nets should be common."
            )
        elif group.peer_identity_basis == "part_id":
            message = (
                "The same recognized supply pin on fitted non-connector components sharing this "
                "native PART_ID across distinct symbols is assigned to different nets. Review "
                "whether the separate rails are intentional or a supply connection is missing; "
                "matching part identity and pin metadata do not prove the nets should be common."
            )
        elif group.role == "ground/return":
            message = (
                "The same recognized return pin on fitted non-connector components with this exact "
                "symbol is assigned to different nets. Review whether the domains are intentionally "
                "separate or a return connection is missing; matching symbol pins do not prove the "
                "nets should be common."
            )
        else:
            message = (
                "The same recognized supply pin on fitted non-connector components with this exact "
                "symbol is assigned to different nets. Review whether the separate rails are "
                "intentional or a supply connection is missing; matching symbol pins do not prove "
                "the nets should be common."
            )
        identity_evidence = (
            {
                "peer_identity_basis": (group.peer_identity_basis,),
                "peer_identity": (group.peer_identity,),
                "peer_symbols": group.peer_symbols,
            }
            if group.peer_identity_basis == "part_id"
            else {}
        )
        subject_identity = (
            group.peer_identity if group.peer_identity_basis == "part_id" else group.symbol
        )
        found.append(
            Candidate(
                rule_id="component.peer_power_pin_assignment_divergence",
                subject=(
                    f"{subject_identity} pin {group.pin_number} ({group.function}): "
                    "peer power assignments differ"
                ),
                message=message,
                evidence={
                    **group.assignments,
                    **identity_evidence,
                    "symbol": (group.symbol,),
                    "pin_number": (group.pin_number,),
                    "pin_function": (group.function,),
                    "peer_role": (group.role,),
                },
            )
        )

    for group in peer_pin_scans.power_output.outliers:
        open_pins = tuple(pin for pin, nets in group.assignments.items() if not nets)
        (
            subject_identity,
            identity_text,
            independent_net_text,
            identity_evidence,
        ) = _component_peer_identity_context(group)
        found.append(
            Candidate(
                rule_id="component.peer_power_output_unconnected",
                subject=(
                    f"{subject_identity} pin {group.pin_number}: fitted peer power-output assignment "
                    "is missing"
                ),
                message=(
                    f"Fitted components with {identity_text} have an unassigned pin that "
                    "KiCad classifies as power_out, while at least one fitted peer's matching pin "
                    "has a net assignment. Review whether the open output is intentionally unused "
                    f"or its connection is missing; {independent_net_text}."
                ),
                evidence={
                    **group.assignments,
                    **identity_evidence,
                    "pin_number": (group.pin_number,),
                    "pin_electrical_type": ("power_out",),
                    "pin_function": (group.pin_function or "",),
                    "unassigned_pins": open_pins,
                },
            )
        )

    for group in peer_pin_scans.signal_output.outliers:
        open_pins = tuple(pin for pin, nets in group.assignments.items() if not nets)
        (
            subject_identity,
            identity_text,
            independent_net_text,
            identity_evidence,
        ) = _component_peer_identity_context(group)
        found.append(
            Candidate(
                rule_id="component.peer_signal_output_unconnected",
                subject=(
                    f"{subject_identity} pin {group.pin_number}: fitted peer signal-output assignment "
                    "is missing"
                ),
                message=(
                    f"Fitted components with {identity_text} have an unassigned pin that "
                    "KiCad classifies as output, while at least one fitted peer's matching pin "
                    "has a net assignment. Review whether the open output is intentionally unused "
                    f"or its connection is missing; {independent_net_text}."
                ),
                evidence={
                    **group.assignments,
                    **identity_evidence,
                    "pin_number": (group.pin_number,),
                    "pin_electrical_type": (group.electrical_type,),
                    "pin_function": (group.pin_function or "",),
                    "unassigned_pins": open_pins,
                },
            )
        )

    for group in peer_pin_scans.signal_input.outliers:
        open_pins = tuple(pin for pin, nets in group.assignments.items() if not nets)
        if any(pin.casefold() in control_pin_keys for pin in open_pins):
            # Keep recognized reset, enable, and boot inputs with their specific rule.
            continue
        (
            subject_identity,
            identity_text,
            independent_net_text,
            identity_evidence,
        ) = _component_peer_identity_context(group)
        found.append(
            Candidate(
                rule_id="component.peer_signal_input_unconnected",
                subject=(
                    f"{subject_identity} pin {group.pin_number}: fitted peer signal-input assignment "
                    "is missing"
                ),
                message=(
                    f"Fitted components with {identity_text} have an unassigned pin that "
                    f"KiCad classifies as {group.electrical_type}, while at least one fitted "
                    "peer's matching pin has a net assignment. Review whether the open input is "
                    f"intentionally unused or its signal connection is missing; "
                    f"{independent_net_text}."
                ),
                evidence={
                    **group.assignments,
                    **identity_evidence,
                    "pin_number": (group.pin_number,),
                    "pin_electrical_type": (group.electrical_type,),
                    "pin_function": (group.pin_function or "",),
                    "unassigned_pins": open_pins,
                },
            )
        )

    for group in peer_pin_scans.bidirectional.outliers:
        open_pins = tuple(pin for pin, nets in group.assignments.items() if not nets)
        (
            subject_identity,
            identity_text,
            independent_net_text,
            identity_evidence,
        ) = _component_peer_identity_context(group)
        found.append(
            Candidate(
                rule_id="component.peer_bidirectional_pin_unconnected",
                subject=(
                    f"{subject_identity} pin {group.pin_number}: fitted peer bidirectional-pin "
                    "assignment is missing"
                ),
                message=(
                    f"Fitted components with {identity_text} have an unassigned pin that "
                    "KiCad classifies as bidirectional, while at least one fitted peer's matching "
                    "pin has a net assignment. Review whether the open pin is intentionally "
                    f"unused or its connection is missing; {independent_net_text}."
                ),
                evidence={
                    **group.assignments,
                    **identity_evidence,
                    "pin_number": (group.pin_number,),
                    "pin_electrical_type": (group.electrical_type,),
                    "pin_function": (group.pin_function or "",),
                    "unassigned_pins": open_pins,
                },
            )
        )
    return tuple(found)
