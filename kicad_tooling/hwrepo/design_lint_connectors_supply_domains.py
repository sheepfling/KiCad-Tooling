"""Review source-mapped connector supply domains that share a native net."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_connector_supply_domain_candidate_evidence import (
    MappedSupplyDomainAssignment,
    MappedSupplyDomainsCandidate,
    MappedSupplyDomainsFindingEvidence,
    MappedSupplyDomainsSharedNet,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


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

    mapped_pins = source_matched_connector_pin_evidence(observed, coverage)
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    assignments_by_net: dict[str, list[MappedSupplyDomainAssignment]] = defaultdict(list)
    for pin, mapped in sorted(mapped_pins.items()):
        reference = pin.rsplit(".", 1)[0]
        if (
            reference.casefold() in unpopulated
            or mapped.role != "supply"
            or mapped.voltage_domain is None
            or mapped.unconnected_reason is not None
            or len(mapped.nets) != 1
        ):
            continue
        assignments_by_net[mapped.nets[0]].append(
            MappedSupplyDomainAssignment(
                pin=pin,
                native_net=mapped.nets[0],
                voltage_domain=str(mapped.voltage_domain),
                mapped_pin=mapped,
            )
        )

    candidates: list[Candidate] = []
    for net, assignments in sorted(assignments_by_net.items()):
        ordered_assignments = tuple(
            sorted(assignments, key=lambda item: (item.voltage_domain, item.pin))
        )
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
