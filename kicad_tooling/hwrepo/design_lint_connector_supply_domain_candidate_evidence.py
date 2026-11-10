"""Compatibility names for mapped connector supply-domain evidence."""

from __future__ import annotations

from .design_lint_connector_domain_shared_net_candidate_evidence import (
    MappedConnectorDomainAssignment as MappedSupplyDomainAssignment,
)
from .design_lint_connector_domain_shared_net_candidate_evidence import (
    MappedConnectorDomainsCandidate as MappedSupplyDomainsCandidate,
)
from .design_lint_connector_domain_shared_net_candidate_evidence import (
    MappedConnectorDomainsFindingEvidence as MappedSupplyDomainsFindingEvidence,
)
from .design_lint_connector_domain_shared_net_candidate_evidence import (
    MappedConnectorDomainsSharedNet as MappedSupplyDomainsSharedNet,
)
from .design_lint_connector_domain_shared_net_candidate_evidence import (
    project_mapped_connector_domains_shared_net_evidence,
)
from .design_lint_types import CandidateEvidenceProjection

__all__ = [
    "MappedSupplyDomainAssignment",
    "MappedSupplyDomainsCandidate",
    "MappedSupplyDomainsFindingEvidence",
    "MappedSupplyDomainsSharedNet",
    "project_mapped_supply_domains_evidence",
]


def project_mapped_supply_domains_evidence(
    source: MappedSupplyDomainsFindingEvidence,
) -> CandidateEvidenceProjection:
    """Preserve the existing public supply-rule evidence projection."""
    return project_mapped_connector_domains_shared_net_evidence(source)
