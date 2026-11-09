"""Source-matched generic signal contacts in reviewed connector peer groups."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
)
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import pin_function_is_generic
from .netlist_contract_models import NetlistContract


@dataclass(frozen=True, slots=True)
class ReviewedPeerSignalContact:
    """One unambiguous generic signal contact with current reviewed peer scope."""

    reference: str
    component_pin: str
    native_symbol: str
    net: str
    interface_signal: str
    voltage_domain: str
    peer_assignment_group: str
    peer_assignment_basis: str


@dataclass(frozen=True, slots=True)
class ReviewedPeerSignalObservation:
    """One mapped generic signal contact, including assigned and open states."""

    reference: str
    component_pin: str
    native_symbol: str
    nets: tuple[str, ...]
    unconnected_reason: str | None
    interface_signal: str
    voltage_domain: str
    peer_assignment_group: str
    peer_assignment_basis: str


@dataclass(frozen=True, slots=True)
class ReviewedPeerSignalAssignment:
    """One source-matched peer signal contact and its native net assignment."""

    reference: str
    component_pin: str
    net: str


@dataclass(frozen=True, slots=True)
class ReviewedPeerSignalAssignmentContext:
    """Assigned peers matching one source-mapped open signal contact."""

    group: str
    group_basis: tuple[str, ...]
    assignments: tuple[ReviewedPeerSignalAssignment, ...]


def reviewed_peer_signal_contacts(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[ReviewedPeerSignalContact, ...]:
    """Return fitted, assigned generic signal contacts with source-matched peer maps."""
    return tuple(
        ReviewedPeerSignalContact(
            reference=observation.reference,
            component_pin=observation.component_pin,
            native_symbol=observation.native_symbol,
            net=observation.nets[0],
            interface_signal=observation.interface_signal,
            voltage_domain=observation.voltage_domain,
            peer_assignment_group=observation.peer_assignment_group,
            peer_assignment_basis=observation.peer_assignment_basis,
        )
        for observation in reviewed_peer_signal_observations(observed, coverage)
        if observation.unconnected_reason is None and len(observation.nets) == 1
    )


def reviewed_peer_signal_observations(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[ReviewedPeerSignalObservation, ...]:
    """Return source-matched generic signal pins, retaining open/intentional-open states."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.interface_catalog_sha256 is None
    ):
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    peer_scopes = source_matched_connector_peer_assignment_groups(observed, coverage)
    contacts: list[ReviewedPeerSignalObservation] = []
    for component_pin, mapped in sorted(
        source_matched_connector_pin_evidence(observed, coverage).items()
    ):
        reference, separator, _pin_number = component_pin.rpartition(".")
        scope = peer_scopes.get(reference)
        native_symbol = observed.component_symbols.get(reference, "").strip()
        signal = mapped.interface_signal.strip()
        voltage_domain = (mapped.voltage_domain or "").strip()
        if (
            not separator
            or scope is None
            or mapped.role != "signal"
            or not signal
            or not voltage_domain
            or not native_symbol
            or reference.casefold() in dnp_references
            or not pin_function_is_generic(mapped.symbol_function)
        ):
            continue
        contacts.append(
            ReviewedPeerSignalObservation(
                reference=reference,
                component_pin=component_pin,
                native_symbol=native_symbol,
                nets=mapped.nets,
                unconnected_reason=mapped.unconnected_reason,
                interface_signal=signal,
                voltage_domain=voltage_domain,
                peer_assignment_group=scope.group,
                peer_assignment_basis=scope.basis,
            )
        )
    return tuple(
        sorted(
            contacts,
            key=lambda item: (
                item.peer_assignment_group.casefold(),
                item.interface_signal.casefold(),
                item.voltage_domain.casefold(),
                item.reference.casefold(),
                item.component_pin.casefold(),
            ),
        )
    )


def reviewed_peer_signal_assignment_context(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
    mapped_pin: ConnectorMappedPinEvidence,
) -> ReviewedPeerSignalAssignmentContext | None:
    """Find current peers on one net that match an open mapped signal and domain."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.interface_catalog_sha256 is None
        or mapped_pin.role != "signal"
        or mapped_pin.nets
        or mapped_pin.unconnected_reason is not None
        or mapped_pin.voltage_domain is None
        or not mapped_pin.voltage_domain.strip()
    ):
        return None

    observations = reviewed_peer_signal_observations(observed, coverage)
    target = next(
        (contact for contact in observations if contact.component_pin == mapped_pin.component_pin),
        None,
    )
    if target is None:
        return None

    target_reference = target.reference.casefold()
    peers_by_reference: dict[str, list[ReviewedPeerSignalObservation]] = defaultdict(list)
    for contact in observations:
        if (
            contact.reference.casefold() == target_reference
            or contact.peer_assignment_group.casefold() != target.peer_assignment_group.casefold()
            or contact.interface_signal.casefold() != target.interface_signal.casefold()
            or contact.voltage_domain.casefold() != target.voltage_domain.casefold()
            or contact.unconnected_reason is not None
        ):
            continue
        peers_by_reference[contact.reference.casefold()].append(contact)

    if not peers_by_reference or any(
        len(contacts) != 1 or len(contacts[0].nets) > 1 for contacts in peers_by_reference.values()
    ):
        return None
    assigned = tuple(
        contacts[0] for contacts in peers_by_reference.values() if len(contacts[0].nets) == 1
    )
    if not assigned:
        return None

    group_bases = {target.peer_assignment_basis}
    group_bases.update(contact.peer_assignment_basis for contact in assigned)
    return ReviewedPeerSignalAssignmentContext(
        group=target.peer_assignment_group,
        group_basis=tuple(
            sorted(
                group_bases,
                key=lambda value: (value.casefold(), value),
            )
        ),
        assignments=tuple(
            ReviewedPeerSignalAssignment(
                reference=contact.reference,
                component_pin=contact.component_pin,
                net=contact.nets[0],
            )
            for contact in sorted(
                assigned,
                key=lambda item: (
                    item.reference.casefold(),
                    item.component_pin.casefold(),
                ),
            )
        ),
    )
