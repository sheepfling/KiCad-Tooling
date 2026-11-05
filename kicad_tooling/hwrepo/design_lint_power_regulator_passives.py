"""Find mismatches in project-authored regulator-required passive topologies."""

from __future__ import annotations

from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_regulator_passive_candidate_evidence import (
    RegulatorPassiveTopologyFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .regulator_passive_checks import regulator_passive_topology_issues
from .regulator_passive_models import RegulatorPassiveTopologyMap

RULE_ID = "power.regulator_required_passive_topology_mismatch"


def regulator_required_passive_candidates(
    observed: NetlistContract,
    requirements: RegulatorPassiveTopologyMap | None,
) -> tuple[Candidate, ...]:
    """Report exact authored regulator or required-passive map mismatches."""
    if requirements is None:
        return ()
    by_id = {item.id.casefold(): item for item in requirements.requirements}
    findings: list[Candidate] = []
    for topology_id, issues in regulator_passive_topology_issues(requirements, observed):
        requirement = by_id[topology_id.casefold()]
        source = RegulatorPassiveTopologyFindingEvidence(
            observed=observed,
            requirements=requirements,
            topology_id=requirement.id,
            issues=issues,
        )
        findings.append(
            PowerCandidate.from_source_evidence(
                source,
                subject=f"{requirement.regulator.reference}: required passive topology differs",
                message=(
                    f"The source-bound native netlist does not match the project-authored "
                    f"regulator passive topology {requirement.id!r} ({requirement.basis}): "
                    f"{'; '.join(issues)}. Review the exact component and pin map. The cited "
                    "basis is project-authored and is not verified by this check."
                ),
            )
        )
    return tuple(findings)
