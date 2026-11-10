"""Review source-mapped connector supplies sharing a net with signal contacts."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .design_lint_connector_mapped_contact_sharing_candidate_evidence import (
    MappedConnectorContactsAtNet,
    MappedConnectorContactSharingFindingEvidence,
    project_mapped_connector_contact_sharing_evidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.mapped_supply_signal_share_net"


def mapped_supply_signal_sharing_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review one connector when mapped supply and signal contacts share one exact net."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.interface_catalog_sha256 is None
    ):
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    contacts_by_reference_and_net: dict[
        tuple[str, str], dict[str, list[ConnectorMappedPinEvidence]]
    ] = defaultdict(lambda: {"supply": [], "signal": []})
    for pin, mapped in source_matched_connector_pin_evidence(observed, coverage).items():
        reference, separator, _pin_number = pin.rpartition(".")
        if (
            not separator
            or mapped.role not in {"supply", "signal"}
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or len(mapped.nets) != 1
        ):
            continue
        contacts_by_reference_and_net[(reference, mapped.nets[0])][mapped.role].append(mapped)

    candidates: list[Candidate] = []
    for (reference, net_name), roles in sorted(
        contacts_by_reference_and_net.items(),
        key=lambda item: (item[0][0].casefold(), item[0][1].casefold(), item[0]),
    ):
        supplies = tuple(sorted(roles["supply"], key=lambda item: item.component_pin))
        signals = tuple(sorted(roles["signal"], key=lambda item: item.component_pin))
        if not supplies or not signals:
            continue

        source = MappedConnectorContactSharingFindingEvidence(
            observed=observed,
            coverage=coverage,
            contacts=MappedConnectorContactsAtNet(
                net_name=net_name,
                primary_role="supply",
                primary_contacts=supplies,
                signal_contacts=signals,
            ),
        )
        signal_names = tuple(
            sorted(
                {item.interface_signal for item in signals},
                key=lambda item: (item.casefold(), item),
            )
        )
        supply_names = tuple(
            sorted(
                {item.interface_signal for item in supplies},
                key=lambda item: (item.casefold(), item),
            )
        )
        projection = project_mapped_connector_contact_sharing_evidence(source)
        evidence = dict(projection.evidence)
        evidence["component_reference"] = (reference,)
        evidence["interface_role"] = ("supply", "signal")
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{reference}: mapped supply and signal contacts share native net {net_name}"
                ),
                message=(
                    f"The current source-matched connector map identifies {', '.join(supply_names)} "
                    f"as supply contacts and {', '.join(signal_names)} as signal contacts, but the "
                    f"native netlist assigns them to the same net ({net_name}). Review whether the "
                    "shared assignment is intentional or needs correction. The mapped roles do not "
                    "prove an electrical defect, incompatible voltage, or required separation, and "
                    "this check does not establish PCB copper continuity."
                ),
                evidence=evidence,
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted(item.evidence.items())),
            ),
        )
    )
