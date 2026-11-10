"""Review named mapped peer signals assigned to separate native nets."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
)
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import (
    connector_power_function_key,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_connector_named_peer_signal_split_candidate_evidence import (
    MappedNamedPeerSignalSplit,
    MappedNamedPeerSignalSplitAssignment,
    MappedNamedPeerSignalSplitCandidate,
    MappedNamedPeerSignalSplitFindingEvidence,
    source_matched_legacy_named_peer_signal_pins,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


def mapped_named_peer_signal_split_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review named source-mapped signal peers with distinct native assignments.

    The interface signal, voltage domain, and reviewed peer group set scope.
    They do not require direct commoning or establish PCB copper continuity.
    """
    if coverage is None or coverage.status != "COMPLETE" or not coverage.interface_catalog_sha256:
        return ()

    mapped_pins = source_matched_connector_pin_evidence(observed, coverage)
    peer_scopes = source_matched_connector_peer_assignment_groups(observed, coverage)
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    unscoped_signal_domains: set[tuple[str, str]] = set()
    contacts_by_scope: dict[
        tuple[str, str, str], list[tuple[str, str, ConnectorMappedPinEvidence]]
    ] = defaultdict(list)
    for component_pin, mapped in sorted(mapped_pins.items()):
        reference, separator, _pin_number = component_pin.rpartition(".")
        signal = mapped.interface_signal.strip()
        domain = (mapped.voltage_domain or "").strip()
        if (
            not separator
            or reference.casefold() in dnp_references
            or mapped.role != "signal"
            or not signal
            or not domain
        ):
            continue
        signal_domain = (signal, domain)
        scope = peer_scopes.get(reference)
        if scope is None:
            unscoped_signal_domains.add(signal_domain)
            continue
        contacts_by_scope[(scope.group, *signal_domain)].append((reference, component_pin, mapped))

    legacy_pins = source_matched_legacy_named_peer_signal_pins(
        observed,
        coverage,
        mapped_pins,
        peer_scopes,
    )
    candidates: list[Candidate] = []
    for (_group_key, signal_key, domain_key), contacts in sorted(
        contacts_by_scope.items(), key=lambda item: tuple(part.casefold() for part in item[0])
    ):
        signal_domain = (signal_key, domain_key)
        if signal_domain in unscoped_signal_domains:
            continue
        references = {reference for reference, _pin, _mapped in contacts}
        if len(references) < 2 or any(legacy_pin in legacy_pins for _, legacy_pin, _ in contacts):
            continue
        if any(
            sum(
                1
                for reference, _pin, _mapped in contacts
                if reference.casefold() == target.casefold()
            )
            != 1
            for target in references
        ):
            continue

        assignments: list[MappedNamedPeerSignalSplitAssignment] = []
        invalid_contact = False
        symbols_by_reference: dict[str, str] = {}
        nets_by_symbol: dict[str, set[str]] = defaultdict(set)
        for reference, component_pin, mapped in contacts:
            function = mapped.symbol_function
            symbol = observed.component_symbols.get(reference, "").strip()
            if (
                mapped.unconnected_reason is not None
                or len(mapped.nets) != 1
                or function is None
                or pin_function_is_generic(function)
                or connector_power_function_key(function) is not None
                or is_return_function(function)
                or not symbol
            ):
                invalid_contact = True
                break
            symbols_by_reference[reference] = symbol.casefold()
            nets_by_symbol[symbol.casefold()].add(mapped.nets[0])
            assignments.append(
                MappedNamedPeerSignalSplitAssignment(
                    component_pin=component_pin,
                    native_net=mapped.nets[0],
                    interface_signal=mapped.interface_signal.strip(),
                    voltage_domain=(mapped.voltage_domain or "").strip(),
                    mapped_pin=mapped,
                )
            )
        if (
            invalid_contact
            or len(set(symbols_by_reference.values())) < 2
            or any(len(nets) > 1 for nets in nets_by_symbol.values())
            or len({item.native_net for item in assignments}) < 2
        ):
            continue

        ordered = tuple(
            sorted(
                assignments, key=lambda item: (item.component_pin.casefold(), item.component_pin)
            )
        )
        group = min(
            (peer_scopes[reference].group for reference in references),
            key=lambda item: (item.casefold(), item),
        )
        interface_signal = min(
            (item.interface_signal for item in ordered),
            key=lambda item: (item.casefold(), item),
        )
        voltage_domain = min(
            (item.voltage_domain for item in ordered),
            key=lambda item: (item.casefold(), item),
        )
        split = MappedNamedPeerSignalSplit(
            peer_assignment_group=group,
            interface_signal=interface_signal,
            voltage_domain=voltage_domain,
            assignments=ordered,
        )
        source = MappedNamedPeerSignalSplitFindingEvidence(
            observed=observed,
            coverage=coverage,
            split=split,
        )
        candidates.append(
            MappedNamedPeerSignalSplitCandidate.from_source_evidence(
                source,
                subject=(
                    f"{group}: mapped peer signal {interface_signal} ({voltage_domain}) "
                    "uses separate native nets"
                ),
                message=(
                    "Complete, source-matched connector entries map these fitted contacts to "
                    f"one peer_assignment_group ({group}), interface_signal ({interface_signal}), "
                    f"and voltage_domain ({voltage_domain}), but their exact native nets are "
                    "separate. Review whether separate routes, switches, filtering, or isolation "
                    "are intentional. These map fields scope review; they do not require direct "
                    "commoning or prove PCB copper continuity."
                ),
            )
        )
    return tuple(candidates)
