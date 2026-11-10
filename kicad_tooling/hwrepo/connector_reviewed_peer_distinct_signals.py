"""Review distinct mapped peer signals assigned to one native net."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import pin_function_is_generic
from .connector_reviewed_peer_signal_evidence import (
    ReviewedPeerSignalContact,
    reviewed_peer_signal_contacts,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.reviewed_peer_distinct_signals_shared_net"


def reviewed_peer_distinct_signals_sharing_net(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review distinct mapped signal names shared across separate peer connectors."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.interface_catalog_sha256 is None
    ):
        return ()

    contacts_by_scope: dict[tuple[str, str], list[ReviewedPeerSignalContact]] = defaultdict(list)
    for contact in reviewed_peer_signal_contacts(
        observed,
        coverage,
        include_named_native_functions=True,
    ):
        contacts_by_scope[(contact.peer_assignment_group.casefold(), contact.net)].append(contact)

    candidates: list[Candidate] = []
    for (_group_key, _net_key), contacts in sorted(contacts_by_scope.items()):
        by_signal: dict[str, dict[str, list[ReviewedPeerSignalContact]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for contact in contacts:
            by_signal[contact.interface_signal.casefold()][contact.reference.casefold()].append(
                contact
            )

        signal_keys = sorted(by_signal)
        for index, left_key in enumerate(signal_keys):
            for right_key in signal_keys[index + 1 :]:
                left_by_reference: dict[str, ReviewedPeerSignalContact] = {
                    reference: items[0]
                    for reference, items in by_signal[left_key].items()
                    if len(items) == 1
                }
                right_by_reference: dict[str, ReviewedPeerSignalContact] = {
                    reference: items[0]
                    for reference, items in by_signal[right_key].items()
                    if len(items) == 1
                }
                overlapping_references = left_by_reference.keys() & right_by_reference.keys()
                left_contacts: tuple[ReviewedPeerSignalContact, ...] = tuple(
                    contact
                    for reference, contact in left_by_reference.items()
                    if reference not in overlapping_references
                )
                right_contacts: tuple[ReviewedPeerSignalContact, ...] = tuple(
                    contact
                    for reference, contact in right_by_reference.items()
                    if reference not in overlapping_references
                )
                if not left_contacts or not right_contacts:
                    continue
                candidates.append(
                    _candidate(
                        left_contacts,
                        right_contacts,
                        catalog_digest=str(coverage.interface_catalog_sha256),
                    )
                )

    return tuple(
        sorted(
            candidates,
            key=lambda item: (item.rule_id, item.subject.casefold(), item.subject),
        )
    )


def _candidate(
    left: tuple[ReviewedPeerSignalContact, ...],
    right: tuple[ReviewedPeerSignalContact, ...],
    *,
    catalog_digest: str,
) -> Candidate:
    """Assemble one deterministic finding for a signal-name pair and net."""
    contacts: tuple[ReviewedPeerSignalContact, ...] = (*left, *right)
    signal_names = tuple(
        sorted(
            {contact.interface_signal for contact in contacts},
            key=lambda value: (value.casefold(), value),
        )
    )
    references = tuple(
        sorted(
            {contact.reference for contact in contacts},
            key=lambda value: (value.casefold(), value),
        )
    )
    pins = tuple(
        sorted(
            {contact.component_pin for contact in contacts},
            key=lambda value: (value.casefold(), value),
        )
    )
    domains = tuple(
        sorted(
            {contact.voltage_domain for contact in contacts},
            key=lambda value: (value.casefold(), value),
        )
    )
    groups = tuple(
        sorted(
            {contact.peer_assignment_group for contact in contacts},
            key=lambda value: (value.casefold(), value),
        )
    )
    bases = tuple(
        sorted(
            {contact.peer_assignment_basis for contact in contacts},
            key=lambda value: (value.casefold(), value),
        )
    )
    nets = tuple(
        sorted(
            {contact.net for contact in contacts},
            key=lambda value: (value.casefold(), value),
        )
    )
    group_name = groups[0]
    net_name = nets[0]
    named_native_functions = any(
        not pin_function_is_generic(contact.native_function) for contact in contacts
    )
    evidence = {
        "component_reference": references,
        "component_pin": pins,
        "interface_signal": signal_names,
        "interface_role": ("signal",),
        "voltage_domain": domains,
        "peer_assignment_group": groups,
        "peer_assignment_basis": bases,
        "assigned_nets": nets,
        "interface_catalog_sha256": (catalog_digest,),
    }
    if named_native_functions:
        evidence["native_pin_function"] = tuple(
            f"{contact.component_pin}={contact.native_function or 'unknown'}"
            for contact in sorted(
                contacts,
                key=lambda item: (item.component_pin.casefold(), item.component_pin),
            )
        )
    return Candidate(
        rule_id=RULE_ID,
        subject=(
            f"{group_name}: distinct mapped peer signals {', '.join(signal_names)} "
            f"share native net {net_name} across separate connectors"
        ),
        message=(
            (
                "Different mapped signal names on named native connector contacts in this "
                "source-reviewed peer group are assigned to one native net across separate "
                "connectors. Review whether the shared connection is intended. Native pin "
                "functions appear in the evidence; peer grouping and signal labels are review "
                "context only. This does not establish an electrical conflict, validate the maps "
                "against a datasheet, or prove PCB continuity."
            )
            if named_native_functions
            else (
                "Different signal names in this source-reviewed peer group are assigned to one "
                "native net across separate connectors. Review whether the shared connection is "
                "intended. Peer grouping and signal labels are review context only; this does not "
                "establish an electrical conflict, validate the maps against a datasheet, or prove "
                "PCB continuity."
            )
        ),
        evidence=evidence,
    )
