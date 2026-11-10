"""Review peer signal contacts on one net with different mapped domains."""

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

RULE_ID: DesignLintRuleId = "connector.reviewed_peer_signal_domain_shared_net"


def reviewed_peer_signal_domains_sharing_net(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review one shared net carrying a same-named peer signal in distinct domains."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.interface_catalog_sha256 is None
    ):
        return ()

    contacts_by_key: dict[tuple[str, str, str], dict[str, list[ReviewedPeerSignalContact]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    for contact in reviewed_peer_signal_contacts(
        observed,
        coverage,
        include_named_native_functions=True,
    ):
        key = (
            contact.peer_assignment_group.casefold(),
            contact.interface_signal.casefold(),
            contact.net,
        )
        contacts_by_key[key][contact.reference.casefold()].append(contact)

    candidates: list[Candidate] = []
    for (_group_key, _signal_key, _net_key), by_reference in sorted(contacts_by_key.items()):
        # A connector must contribute exactly one unambiguous contact to this comparison.
        if len(by_reference) < 2 or any(len(items) != 1 for items in by_reference.values()):
            continue
        peer_contacts = tuple(items[0] for items in by_reference.values())
        domains_by_key: dict[str, str] = {}
        for contact in peer_contacts:
            key = contact.voltage_domain.casefold()
            current = domains_by_key.get(key)
            if current is None or contact.voltage_domain < current:
                domains_by_key[key] = contact.voltage_domain
        domains = tuple(
            sorted(domains_by_key.values(), key=lambda value: (value.casefold(), value))
        )
        if len(domains) < 2:
            continue

        references = tuple(
            sorted(
                (contact.reference for contact in peer_contacts),
                key=lambda value: (value.casefold(), value),
            )
        )
        pins = tuple(
            sorted(
                (contact.component_pin for contact in peer_contacts),
                key=lambda value: (value.casefold(), value),
            )
        )
        signal_name = min(
            (contact.interface_signal for contact in peer_contacts),
            key=lambda value: (value.casefold(), value),
        )
        group_name = min(
            (contact.peer_assignment_group for contact in peer_contacts),
            key=lambda value: (value.casefold(), value),
        )
        net_name = min(
            (contact.net for contact in peer_contacts),
            key=lambda value: (value.casefold(), value),
        )
        bases = tuple(
            sorted(
                {contact.peer_assignment_basis for contact in peer_contacts},
                key=lambda value: (value.casefold(), value),
            )
        )
        named_native_functions = any(
            not pin_function_is_generic(contact.native_function) for contact in peer_contacts
        )
        evidence = {
            "component_reference": references,
            "component_pin": pins,
            "interface_signal": (signal_name,),
            "interface_role": ("signal",),
            "voltage_domain": domains,
            "peer_assignment_group": (group_name,),
            "peer_assignment_basis": bases,
            "assigned_nets": (net_name,),
            "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
        }
        if named_native_functions:
            evidence["native_pin_function"] = tuple(
                f"{contact.component_pin}={contact.native_function or 'unknown'}"
                for contact in sorted(
                    peer_contacts,
                    key=lambda item: (item.component_pin.casefold(), item.component_pin),
                )
            )
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{group_name}: mapped peer signal {signal_name} in voltage domains "
                    f"{', '.join(domains)} shares native net {net_name}"
                ),
                message=(
                    (
                        "Named native connector contacts in this source-reviewed peer group map "
                        "to the same interface signal but declare different voltage domains on "
                        "one native net. Review whether this direct connection is intended and "
                        "electrically compatible. Native pin functions appear in the evidence; "
                        "domain identifiers do not establish nominal voltages or prove an "
                        "incompatibility. The review does not establish PCB copper continuity."
                    )
                    if named_native_functions
                    else (
                        "Generic connector contacts in this source-reviewed peer group map to "
                        "the same interface signal but declare different voltage domains on one "
                        "native net. Review whether a direct connection is intended and "
                        "electrically compatible. Domain identifiers do not establish nominal "
                        "voltages or prove an incompatibility; this review does not establish "
                        "PCB copper continuity."
                    )
                ),
                evidence=evidence,
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (item.rule_id, item.subject.casefold(), item.subject),
        )
    )
