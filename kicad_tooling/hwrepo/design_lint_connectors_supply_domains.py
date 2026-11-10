"""Review source-mapped connector supply domains that share a native net."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_domain_assignment_groups import mapped_connector_domain_assignments_by_net
from .design_lint_connector_supply_domain_candidate_evidence import (
    MappedSupplyDomainsCandidate,
    MappedSupplyDomainsFindingEvidence,
    MappedSupplyDomainsSharedNet,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_supply_domain_split_candidate_evidence import (
    MappedSupplyDomainSplit,
    MappedSupplyDomainSplitAssignment,
    MappedSupplyDomainSplitCandidate,
    MappedSupplyDomainSplitFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

_SAME_DOMAIN_SUPPLIES_SPLIT: DesignLintRuleId = "connector.mapped_same_domain_supply_split_nets"


def mapped_supply_domains_shared_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review distinct mapped supply domains assigned to the same exact net.

    Only unambiguous pins from complete, source-matched connector entries are
    considered. Domain names classify authored map entries; they do not imply
    that the named domains have different voltages or must remain separate.
    """
    if coverage is None:
        return ()

    assignments_by_net = mapped_connector_domain_assignments_by_net(
        observed, coverage, role="supply"
    )

    candidates: list[Candidate] = []
    for net, ordered_assignments in assignments_by_net.items():
        ordered_domains = tuple(sorted({item.voltage_domain for item in ordered_assignments}))
        if len(ordered_domains) < 2:
            continue
        shared_net = MappedSupplyDomainsSharedNet(
            native_net=net,
            voltage_domains=ordered_domains,
            assignments=ordered_assignments,
        )
        source_evidence = MappedSupplyDomainsFindingEvidence(
            observed=observed,
            coverage=coverage,
            shared_net=shared_net,
        )
        candidates.append(
            MappedSupplyDomainsCandidate.from_source_evidence(
                source_evidence,
                subject=f"{net}: mapped connector supply domains share one native net",
                message=(
                    "Complete, source-matched project interface entries classify these connector "
                    "pins as supplies in distinct voltage_domain groups assigned to the same "
                    "schematic net. Review whether the entries should share this node or whether "
                    "the mapping needs clarification. Distinct domain identifiers do not establish "
                    "different nominal voltages or electrical incompatibility, and this heuristic "
                    "does not prove a physical board fault."
                ),
            )
        )
    return tuple(candidates)


def mapped_same_domain_supply_split_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review same-domain mapped supplies split across nets on one connector.

    A project map's exact role and voltage-domain values make this a review
    clue; they do not state that the contacts must be shorted together.
    """
    if coverage is None or coverage.status != "COMPLETE" or not coverage.interface_catalog_sha256:
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    assignments_by_connector_domain: dict[
        tuple[str, str], list[MappedSupplyDomainSplitAssignment]
    ] = defaultdict(list)
    for component_pin, mapped in sorted(
        source_matched_connector_pin_evidence(observed, coverage).items()
    ):
        reference, separator, _pin_number = component_pin.rpartition(".")
        if (
            not separator
            or reference.casefold() in dnp_references
            or mapped.role != "supply"
            or not mapped.voltage_domain
            or mapped.unconnected_reason is not None
            or len(mapped.nets) != 1
        ):
            continue
        assignments_by_connector_domain[(reference, mapped.voltage_domain)].append(
            MappedSupplyDomainSplitAssignment(
                component_pin=component_pin,
                native_net=mapped.nets[0],
                voltage_domain=mapped.voltage_domain,
                mapped_pin=mapped,
            )
        )

    candidates: list[Candidate] = []
    for (reference, voltage_domain), assignments in sorted(
        assignments_by_connector_domain.items(),
        key=lambda item: (
            item[0][0].casefold(),
            item[0][1].casefold(),
            item[0][0],
            item[0][1],
        ),
    ):
        ordered_assignments = tuple(sorted(assignments, key=lambda item: item.component_pin))
        if len({item.native_net for item in ordered_assignments}) < 2:
            continue
        split = MappedSupplyDomainSplit(
            component_reference=reference,
            voltage_domain=voltage_domain,
            assignments=ordered_assignments,
        )
        source_evidence = MappedSupplyDomainSplitFindingEvidence(
            observed=observed,
            coverage=coverage,
            split=split,
        )
        candidates.append(
            MappedSupplyDomainSplitCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{reference}: mapped supply contacts in voltage domain "
                    f"{voltage_domain} use separate native nets"
                ),
                message=(
                    "Complete, source-matched connector entries classify these fitted supply "
                    f"contacts in one voltage_domain ({voltage_domain}), but their native nets "
                    "are separate. Review whether the split is intentional or whether the map "
                    "needs correction. A shared domain label does not require common nets or "
                    "prove equal voltage, an electrical defect, or PCB copper continuity."
                ),
            )
        )
    return tuple(candidates)
