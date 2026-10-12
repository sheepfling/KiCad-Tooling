"""Translate same-identity component peer pin assignment observations."""

from __future__ import annotations

from .component_peer_pin_all_open import all_open_generic_component_peer_pin_candidates
from .component_peer_pin_findings import component_peer_power_pin_assignment_divergences
from .component_peer_pin_identity import component_peer_pin_identity_context
from .component_peer_pin_mixed_open import mixed_open_generic_component_peer_pin_candidates
from .component_peer_pin_scan import ComponentPeerPinAssignmentScans
from .design_lint_types import Candidate
from .models import NetlistContract


def component_peer_candidates(
    observed: NetlistContract,
    *,
    peer_pin_scans: ComponentPeerPinAssignmentScans,
    reviewed_connector_references: tuple[str, ...] = (),
    control_pin_keys: frozenset[str] = frozenset(),
) -> tuple[Candidate, ...]:
    """Build review prompts for comparable components with divergent peer pins."""
    found: list[Candidate] = []
    functions_by_pin = {
        pin.casefold(): function for pin, function in observed.pin_functions.items()
    }
    for group in peer_pin_scans.power_input_assignment_divergence.outliers:
        found.append(
            Candidate(
                rule_id="component.peer_power_input_assignment_divergence",
                subject=(
                    f"{group.symbol} pin {group.pin_number}: generic peer power-input "
                    "assignments differ"
                ),
                message=(
                    "Fitted non-connector components with this exact native symbol assign the "
                    "same generic power_in pin to different nets. Review whether these supply "
                    "domains are intentionally separate or a connection is missing; matching "
                    "symbol identity and electrical type do not prove that the rails must be common."
                ),
                evidence={
                    **group.assignments,
                    "symbol": (group.symbol,),
                    "pin_number": (group.pin_number,),
                    "pin_electrical_type": ("power_in",),
                    "pin_functions": tuple(
                        f"{pin}={functions_by_pin.get(pin.casefold()) or ''}"
                        for pin in group.assignments
                    ),
                },
            )
        )

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
        ) = component_peer_pin_identity_context(group)
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
        ) = component_peer_pin_identity_context(group)
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
        ) = component_peer_pin_identity_context(group)
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
        ) = component_peer_pin_identity_context(group)
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
    for group in peer_pin_scans.generic_assignment_outlier.outliers:
        (
            subject_identity,
            identity_text,
            independent_net_text,
            identity_evidence,
        ) = component_peer_pin_identity_context(group)
        found.append(
            Candidate(
                rule_id="component.generic_peer_pin_assignment_outlier",
                subject=(
                    f"{subject_identity} pin {group.pin_number}: generic peer assignment "
                    "differs from its strict majority"
                ),
                message=(
                    f"Fitted components with {identity_text} share another exact-net anchor, "
                    f"but this generic {group.electrical_type} pin has a strict majority "
                    "assignment and one or more different peer assignments. Review whether "
                    "the outlier is intentional; the shared anchor and repeated identity are "
                    f"comparison clues only, and {independent_net_text}."
                ),
                evidence={
                    **group.assignments,
                    **identity_evidence,
                    "pin_number": (group.pin_number,),
                    "pin_function": (group.pin_function or "",),
                    "pin_electrical_type": (group.electrical_type,),
                    "majority_net": (group.majority_net or "",),
                    "outlier_pins": group.outlier_pins,
                    "shared_anchor_contacts": group.shared_anchor_contacts,
                },
            )
        )
    found.extend(
        mixed_open_generic_component_peer_pin_candidates(peer_pin_scans.generic_partial_open)
    )
    found.extend(all_open_generic_component_peer_pin_candidates(peer_pin_scans.generic_all_open))
    return tuple(found)
