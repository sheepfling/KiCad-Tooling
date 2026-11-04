"""Translate same-identity component peer pin assignment observations."""

from __future__ import annotations

from .component_peer_pin_all_open import all_open_generic_component_peer_pin_candidates
from .component_peer_pin_candidate_types import (
    ComponentPeerCandidateInputs,
    ComponentPeerCandidateResult,
    ComponentPeerPinFindingCounts,
)
from .component_peer_pin_findings import component_peer_power_pin_assignment_divergences
from .component_peer_pin_identity import component_peer_pin_identity_context
from .component_peer_pin_mixed_open import mixed_open_generic_component_peer_pin_candidates
from .component_peer_pin_scan import ComponentPeerPinAssignmentScans
from .design_lint_component_peer_candidate_evidence import (
    GenericPeerPinCandidate,
    GenericPowerInputDivergenceEvidence,
    NamedPowerInputAllOpenEvidence,
    NamedPowerInputDivergenceEvidence,
    NamedPowerInputOpenEvidence,
    PeerPinFunctionEvidence,
    PeerPowerPinDivergenceCandidate,
    PeerPowerPinDivergenceEvidence,
    PeerUnconnectedPinEvidence,
    PowerInputPeerCandidate,
    UnconnectedPeerPinCandidate,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


def component_peer_candidates(
    observed: NetlistContract,
    *,
    peer_pin_scans: ComponentPeerPinAssignmentScans,
    reviewed_connector_references: tuple[str, ...] = (),
    control_pin_keys: frozenset[str] = frozenset(),
) -> tuple[Candidate, ...]:
    """Preserve the keyword-based candidate interface for direct callers."""
    return scan_component_peer_candidates(
        ComponentPeerCandidateInputs(
            observed=observed,
            peer_pin_scans=peer_pin_scans,
            reviewed_connector_references=reviewed_connector_references,
            control_pin_keys=control_pin_keys,
        )
    ).candidates


def scan_component_peer_candidates(
    inputs: ComponentPeerCandidateInputs,
) -> ComponentPeerCandidateResult:
    """Build findings and typed counts from the component-peer theme inputs."""
    candidates = _component_peer_candidate_items(inputs)
    return ComponentPeerCandidateResult(
        candidates=candidates,
        finding_counts=ComponentPeerPinFindingCounts.from_candidates(candidates),
    )


def _component_peer_candidate_items(
    inputs: ComponentPeerCandidateInputs,
) -> tuple[Candidate, ...]:
    """Build review prompts for comparable components with divergent peer pins."""
    observed = inputs.observed
    peer_pin_scans = inputs.peer_pin_scans
    reviewed_connector_references = inputs.reviewed_connector_references
    control_pin_keys = inputs.control_pin_keys
    found: list[Candidate] = []
    functions_by_pin = {
        pin.casefold(): function for pin, function in observed.pin_functions.items()
    }
    for group in peer_pin_scans.power_input_assignment_divergence.outliers:
        source_evidence = GenericPowerInputDivergenceEvidence(
            outlier=group,
            pin_functions=tuple(
                PeerPinFunctionEvidence(
                    pin=pin,
                    function=functions_by_pin.get(pin.casefold()) or "",
                )
                for pin in group.assignments
            ),
        )
        found.append(
            PowerInputPeerCandidate.from_source_evidence(
                source_evidence,
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
            )
        )

    for group in peer_pin_scans.named_power_input_assignment_divergence.outliers:
        peer_identity = (
            group.peer_identity if group.peer_identity_basis == "part_id" else group.symbol
        )
        source_evidence = NamedPowerInputDivergenceEvidence(outlier=group)
        found.append(
            PowerInputPeerCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{peer_identity} pin {group.pin_number} ({group.pin_function}): "
                    "named power-input peer assignments differ"
                ),
                message=(
                    "Comparable fitted non-connector components use the same explicit, "
                    "unrecognized native power_in pin function but assign it to different nets. "
                    "Review whether the separate domains are intentional or a connection is "
                    "missing; matching peer metadata does not establish that the nets must be "
                    "common."
                ),
            )
        )

    for group in peer_pin_scans.power_input_open_assignment.outliers:
        peer_identity = (
            group.peer_identity if group.peer_identity_basis == "part_id" else group.symbol
        )
        source_evidence = NamedPowerInputOpenEvidence(outlier=group)
        found.append(
            PowerInputPeerCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{peer_identity} pin {group.pin_number} ({group.pin_function}): "
                    "power-input peer assignment is open"
                ),
                message=(
                    "Comparable fitted non-connector components use this same, unrecognized native "
                    "power_in pin function, but at least one peer has no net assignment. Review "
                    "whether the open pin is intentionally unused or a supply connection is "
                    "missing; matching part metadata is a review clue and does not establish that "
                    "peer pins must share a net."
                ),
            )
        )

    for group in peer_pin_scans.named_power_input_all_open.outliers:
        peer_identity = (
            group.peer_identity if group.peer_identity_basis == "part_id" else group.symbol
        )
        source_evidence = NamedPowerInputAllOpenEvidence(outlier=group)
        found.append(
            PowerInputPeerCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{peer_identity} pin {group.pin_number} ({group.pin_function}): "
                    "named power-input peer pin is open on every fitted peer"
                ),
                message=(
                    "Comparable fitted non-connector components use the same explicit, "
                    "unrecognized native power_in function, but every peer pin is open. "
                    "Review the approved part requirements for an intentionally unused "
                    "pin or a missing connection; matching peer metadata does not establish "
                    "that the pin must be connected."
                ),
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
        subject_identity = (
            group.peer_identity if group.peer_identity_basis == "part_id" else group.symbol
        )
        source_evidence = PeerPowerPinDivergenceEvidence(divergence=group)
        found.append(
            PeerPowerPinDivergenceCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{subject_identity} pin {group.pin_number} ({group.function}): "
                    "peer power assignments differ"
                ),
                message=message,
            )
        )

    for group in peer_pin_scans.power_output.outliers:
        source_evidence = PeerUnconnectedPinEvidence(kind="power_output", outlier=group)
        identity = component_peer_pin_identity_context(group)
        found.append(
            UnconnectedPeerPinCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{identity.subject_identity} pin {group.pin_number}: fitted peer power-output assignment "
                    "is missing"
                ),
                message=(
                    f"Fitted components with {identity.identity_description} have an unassigned pin that "
                    "KiCad classifies as power_out, while at least one fitted peer's matching pin "
                    "has a net assignment. Review whether the open output is intentionally unused "
                    f"or its connection is missing; {identity.independent_net_note}."
                ),
            )
        )

    for group in peer_pin_scans.signal_output.outliers:
        source_evidence = PeerUnconnectedPinEvidence(kind="signal_output", outlier=group)
        identity = component_peer_pin_identity_context(group)
        found.append(
            UnconnectedPeerPinCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{identity.subject_identity} pin {group.pin_number}: fitted peer signal-output assignment "
                    "is missing"
                ),
                message=(
                    f"Fitted components with {identity.identity_description} have an unassigned pin that "
                    "KiCad classifies as output, while at least one fitted peer's matching pin "
                    "has a net assignment. Review whether the open output is intentionally unused "
                    f"or its connection is missing; {identity.independent_net_note}."
                ),
            )
        )

    for group in peer_pin_scans.signal_input.outliers:
        source_evidence = PeerUnconnectedPinEvidence(kind="signal_input", outlier=group)
        identity = component_peer_pin_identity_context(group)
        if any(
            pin.casefold() in control_pin_keys
            for pin, nets in group.assignments.items()
            if not nets
        ):
            # Keep recognized reset, enable, and boot inputs with their specific rule.
            continue
        found.append(
            UnconnectedPeerPinCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{identity.subject_identity} pin {group.pin_number}: fitted peer signal-input assignment "
                    "is missing"
                ),
                message=(
                    f"Fitted components with {identity.identity_description} have an unassigned pin that "
                    f"KiCad classifies as {group.electrical_type}, while at least one fitted "
                    "peer's matching pin has a net assignment. Review whether the open input is "
                    f"intentionally unused or its signal connection is missing; "
                    f"{identity.independent_net_note}."
                ),
            )
        )

    for group in peer_pin_scans.bidirectional.outliers:
        source_evidence = PeerUnconnectedPinEvidence(kind="bidirectional", outlier=group)
        identity = component_peer_pin_identity_context(group)
        found.append(
            UnconnectedPeerPinCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{identity.subject_identity} pin {group.pin_number}: fitted peer bidirectional-pin "
                    "assignment is missing"
                ),
                message=(
                    f"Fitted components with {identity.identity_description} have an unassigned pin that "
                    "KiCad classifies as bidirectional, while at least one fitted peer's matching "
                    "pin has a net assignment. Review whether the open pin is intentionally "
                    f"unused or its connection is missing; {identity.independent_net_note}."
                ),
            )
        )
    for group in peer_pin_scans.generic_assignment_outlier.outliers:
        identity = component_peer_pin_identity_context(group)
        found.append(
            GenericPeerPinCandidate.from_source_evidence(
                group,
                subject=(
                    f"{identity.subject_identity} pin {group.pin_number}: generic peer assignment "
                    "differs from its strict majority"
                ),
                message=(
                    f"Fitted components with {identity.identity_description} share another exact-net anchor, "
                    f"but this generic {group.electrical_type} pin has a strict majority "
                    "assignment and one or more different peer assignments. Review whether "
                    "the outlier is intentional; the shared anchor and repeated identity are "
                    f"comparison clues only, and {identity.independent_net_note}."
                ),
            )
        )
    found.extend(
        mixed_open_generic_component_peer_pin_candidates(peer_pin_scans.generic_partial_open)
    )
    found.extend(all_open_generic_component_peer_pin_candidates(peer_pin_scans.generic_all_open))
    return tuple(found)
