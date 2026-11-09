"""Review split mapped signals across unlike reviewed connector peers."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage_models import ConnectorCoverageReport
from .connector_reviewed_peer_signal_evidence import (
    ReviewedPeerSignalContact,
    reviewed_peer_signal_contacts,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.reviewed_peer_signal_assignment_split"


def reviewed_peer_signal_assignment_splits(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review one mapped signal/domain split across unlike reviewed peers."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.interface_catalog_sha256 is None
    ):
        return ()
    contacts_by_key: dict[tuple[str, str, str], dict[str, list[ReviewedPeerSignalContact]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    for contact in reviewed_peer_signal_contacts(observed, coverage):
        key = (
            contact.peer_assignment_group.casefold(),
            contact.interface_signal.casefold(),
            contact.voltage_domain.casefold(),
        )
        contacts_by_key[key][contact.reference.casefold()].append(contact)

    candidates: list[Candidate] = []
    for (_group_key, _signal_key, _domain_key), by_reference in sorted(contacts_by_key.items()):
        # Repeated contacts inside one connector belong to existing rules.
        if len(by_reference) < 2 or any(len(items) != 1 for items in by_reference.values()):
            continue
        peer_contacts = tuple(items[0] for items in by_reference.values())
        symbols = {contact.native_symbol.casefold() for contact in peer_contacts}
        if len(symbols) < 2:
            continue

        nets_by_symbol: dict[str, set[str]] = defaultdict(set)
        for contact in peer_contacts:
            nets_by_symbol[contact.native_symbol.casefold()].add(contact.net)
        # Same-symbol assignment differences remain with existing connector rules.
        if any(len(nets) > 1 for nets in nets_by_symbol.values()):
            continue

        nets = tuple(
            sorted(
                {contact.net for contact in peer_contacts},
                key=lambda value: (value.casefold(), value),
            )
        )
        if len(nets) < 2:
            continue

        references = tuple(
            sorted(
                (contact.reference for contact in peer_contacts),
                key=lambda value: (value.casefold(), value),
            )
        )
        signal_name = min(
            (contact.interface_signal for contact in peer_contacts),
            key=lambda value: (value.casefold(), value),
        )
        voltage_domain = min(
            (contact.voltage_domain for contact in peer_contacts),
            key=lambda value: (value.casefold(), value),
        )
        group_name = min(
            (contact.peer_assignment_group for contact in peer_contacts),
            key=lambda value: (value.casefold(), value),
        )
        bases = tuple(
            sorted(
                {contact.peer_assignment_basis for contact in peer_contacts},
                key=lambda value: (value.casefold(), value),
            )
        )
        pins = tuple(
            sorted(
                (contact.component_pin for contact in peer_contacts),
                key=lambda value: (value.casefold(), value),
            )
        )
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{group_name}: mapped peer signal {signal_name} ({voltage_domain}) "
                    f"spans native nets {', '.join(nets)}"
                ),
                message=(
                    "Unlike connector symbols in this source-reviewed peer group map generic "
                    "signal contacts to the same interface signal and voltage domain, but the "
                    "native netlist assigns them to different nets. Review whether distinct "
                    "routes or isolation are intentional. The peer map does not require direct "
                    "commoning and this check does not establish PCB copper continuity."
                ),
                evidence={
                    "component_reference": references,
                    "component_pin": pins,
                    "interface_signal": (signal_name,),
                    "interface_role": ("signal",),
                    "voltage_domain": (voltage_domain,),
                    "peer_assignment_group": (group_name,),
                    "peer_assignment_basis": bases,
                    "assigned_nets": nets,
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (item.rule_id, item.subject.casefold(), item.subject),
        )
    )
