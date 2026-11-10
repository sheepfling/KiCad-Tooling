"""Review source-mapped connector returns sharing a shield net."""

from __future__ import annotations

from .connector_coverage import ConnectorCoverageReport
from .connector_mapped_role_pair_evidence import (
    MappedConnectorRolePairCandidate,
    MappedConnectorRolePairFindingEvidence,
    mapped_connector_role_pair_groups,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.mapped_return_shield_share_net"


def mapped_return_shield_sharing_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review a fitted connector when mapped return and shield pins share one exact net."""
    candidates: list[Candidate] = []
    for contacts in mapped_connector_role_pair_groups(
        observed,
        coverage,
        primary_role="return",
        secondary_role="shield",
    ):
        if coverage is None:
            continue
        source_evidence = MappedConnectorRolePairFindingEvidence(
            observed=observed,
            coverage=coverage,
            contacts=contacts,
        )
        candidates.append(
            MappedConnectorRolePairCandidate.from_source_evidence(
                source_evidence,
                rule_id=RULE_ID,
                subject=(
                    f"{contacts.component_reference}: mapped return and shield contacts share "
                    f"native net {contacts.net_name}"
                ),
                message=(
                    "The current source-matched connector map identifies return and shield "
                    f"contacts that share one native net ({contacts.net_name}). Review whether "
                    "the shield bond is intentional and appropriate for this interface. The "
                    "mapped roles do not establish required isolation or bonding, external "
                    "chassis behavior, or PCB copper continuity."
                ),
            )
        )
    return tuple(candidates)
