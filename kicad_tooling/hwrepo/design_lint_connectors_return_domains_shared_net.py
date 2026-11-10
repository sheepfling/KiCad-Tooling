"""Review source-mapped connector return domains that share a native net."""

from __future__ import annotations

from .connector_coverage_models import ConnectorCoverageReport
from .connector_domain_assignment_groups import mapped_connector_domain_assignments_by_net
from .design_lint_connector_domain_shared_net_candidate_evidence import (
    MappedConnectorDomainsCandidate,
    MappedConnectorDomainsFindingEvidence,
    MappedConnectorDomainsSharedNet,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


def mapped_return_domains_shared_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review distinct mapped return domains assigned to one exact net.

    Exact return roles and domain labels are review clues only. The predicate
    cannot infer whether the contacts should be bonded or intentionally joined.
    """
    if coverage is None:
        return ()

    assignments_by_net = mapped_connector_domain_assignments_by_net(
        observed, coverage, role="return"
    )
    candidates: list[Candidate] = []
    for net, assignments in assignments_by_net.items():
        domains = tuple(sorted({item.voltage_domain for item in assignments}))
        if len(domains) < 2:
            continue
        shared_net = MappedConnectorDomainsSharedNet(
            native_net=net,
            voltage_domains=domains,
            assignments=assignments,
            interface_role="return",
        )
        source_evidence = MappedConnectorDomainsFindingEvidence(
            observed=observed,
            coverage=coverage,
            shared_net=shared_net,
        )
        candidates.append(
            MappedConnectorDomainsCandidate.from_source_evidence(
                source_evidence,
                subject=f"{net}: mapped connector return domains share one native net",
                message=(
                    "Complete, source-matched project interface entries classify these connector "
                    "pins as returns in distinct voltage_domain groups assigned to the same "
                    "schematic net. Review whether the entries should share this node or whether "
                    "the mapping needs clarification. Distinct domain identifiers do not establish "
                    "different potentials or an electrical defect, and this heuristic does not "
                    "prove a physical board fault."
                ),
            )
        )
    return tuple(candidates)
