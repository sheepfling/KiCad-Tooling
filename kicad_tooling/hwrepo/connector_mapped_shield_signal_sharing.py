"""Review mapped connector contact roles sharing one native net."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .design_lint_connector_mapped_contact_sharing_candidate_evidence import (
    SHIELD_SIGNAL_RULE_ID as _SHIELD_SIGNAL_RULE_ID,
)
from .design_lint_connector_mapped_contact_sharing_candidate_evidence import (
    SIGNAL_RETURN_RULE_ID as _SIGNAL_RETURN_RULE_ID,
)
from .design_lint_connector_mapped_contact_sharing_candidate_evidence import (
    MappedConnectorContactsAtNet,
    MappedConnectorContactSharingCandidate,
    MappedConnectorContactSharingFindingEvidence,
    MappedContactSharingRole,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

SHIELD_SIGNAL_RULE_ID = _SHIELD_SIGNAL_RULE_ID
SIGNAL_RETURN_RULE_ID = _SIGNAL_RETURN_RULE_ID


def mapped_shields_sharing_signal_nets(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Prompt when a current, complete connector map puts shield and signal on one net."""
    if coverage is None:
        return ()
    candidates: list[Candidate] = []
    for contacts in _mapped_contacts_by_net(observed, coverage, primary_role="shield"):
        if not contacts.primary_contacts or not contacts.signal_contacts:
            continue
        shield_pins = tuple(sorted(item.component_pin for item in contacts.primary_contacts))
        signal_pins = tuple(sorted(item.component_pin for item in contacts.signal_contacts))
        shield_names = tuple(
            sorted({item.interface_signal for item in contacts.primary_contacts}, key=str.casefold)
        )
        signal_names = tuple(
            sorted({item.interface_signal for item in contacts.signal_contacts}, key=str.casefold)
        )
        source_evidence = MappedConnectorContactSharingFindingEvidence(
            observed=observed,
            coverage=coverage,
            contacts=contacts,
        )
        candidates.append(
            MappedConnectorContactSharingCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"mapped shield contacts {', '.join(shield_pins)} and signal contacts "
                    f"{', '.join(signal_pins)} share native net {contacts.net_name}"
                ),
                message=(
                    f"The source-matched connector map identifies {', '.join(shield_names)} as "
                    f"shield contacts and {', '.join(signal_names)} as signal contacts, while "
                    f"the native netlist assigns both roles to {contacts.net_name}. Review whether "
                    "this direct connection is intentional. Shield bonding can be valid, but this "
                    "heuristic does not decide the intended bond, inspect intervening circuitry, "
                    "or establish PCB copper continuity or external chassis bonding."
                ),
            )
        )
    return tuple(candidates)


def mapped_signals_sharing_return_nets(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Prompt when source-mapped signal and return contacts share one net."""
    if coverage is None:
        return ()
    candidates: list[Candidate] = []
    for contacts in _mapped_contacts_by_net(observed, coverage, primary_role="return"):
        if not contacts.primary_contacts or not contacts.signal_contacts:
            continue
        return_pins = tuple(sorted(item.component_pin for item in contacts.primary_contacts))
        signal_pins = tuple(sorted(item.component_pin for item in contacts.signal_contacts))
        return_names = tuple(
            sorted({item.interface_signal for item in contacts.primary_contacts}, key=str.casefold)
        )
        signal_names = tuple(
            sorted({item.interface_signal for item in contacts.signal_contacts}, key=str.casefold)
        )
        source_evidence = MappedConnectorContactSharingFindingEvidence(
            observed=observed,
            coverage=coverage,
            contacts=contacts,
        )
        candidates.append(
            MappedConnectorContactSharingCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"mapped return contacts {', '.join(return_pins)} and signal contacts "
                    f"{', '.join(signal_pins)} share native net {contacts.net_name}"
                ),
                message=(
                    f"The source-matched connector map identifies {', '.join(return_names)} as "
                    f"return contacts and {', '.join(signal_names)} as signal contacts, while "
                    f"the native netlist assigns both roles to {contacts.net_name}. Review whether "
                    "this direct connection is intentional. This heuristic does not determine the "
                    "required signal reference, prove a wiring defect, inspect intervening "
                    "circuitry, or establish PCB copper continuity or off-board behavior."
                ),
            )
        )
    return tuple(candidates)


def _mapped_contacts_by_net(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport,
    *,
    primary_role: MappedContactSharingRole,
) -> tuple[MappedConnectorContactsAtNet, ...]:
    if coverage.status != "COMPLETE" or not coverage.interface_catalog_sha256:
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    by_net: dict[str, dict[str, list[ConnectorMappedPinEvidence]]] = defaultdict(
        lambda: {primary_role: [], "signal": []}
    )
    for _pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference, separator, _pin_number = mapped.component_pin.rpartition(".")
        if (
            not separator
            or mapped.role not in {primary_role, "signal"}
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or len(mapped.nets) != 1
        ):
            continue
        by_net[mapped.nets[0]][mapped.role].append(mapped)

    return tuple(
        MappedConnectorContactsAtNet(
            net_name=net_name,
            primary_role=primary_role,
            primary_contacts=tuple(
                sorted(roles[primary_role], key=lambda item: item.component_pin)
            ),
            signal_contacts=tuple(sorted(roles["signal"], key=lambda item: item.component_pin)),
        )
        for net_name, roles in sorted(by_net.items())
    )
