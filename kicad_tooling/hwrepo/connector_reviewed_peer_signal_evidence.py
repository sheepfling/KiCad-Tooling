"""Source-matched generic signal contacts in reviewed connector peer groups."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
)
from .connector_coverage_models import ConnectorCoverageReport
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


def reviewed_peer_signal_contacts(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[ReviewedPeerSignalContact, ...]:
    """Return fitted, assigned generic signal contacts with source-matched peer maps."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.interface_catalog_sha256 is None
    ):
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    peer_scopes = source_matched_connector_peer_assignment_groups(observed, coverage)
    contacts: list[ReviewedPeerSignalContact] = []
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
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or not pin_function_is_generic(mapped.symbol_function)
            or len(mapped.nets) != 1
        ):
            continue
        contacts.append(
            ReviewedPeerSignalContact(
                reference=reference,
                component_pin=component_pin,
                native_symbol=native_symbol,
                net=mapped.nets[0],
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
