"""Review authored regulator pin-role metadata against native exports."""

from __future__ import annotations

from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_regulator_passive_candidate_evidence import (
    RegulatorPassivePinRoleFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .regulator_passive_checks import regulator_passive_pin_role_issues
from .regulator_passive_models import RegulatorPassiveTopologyMap

RULE_ID = "power.regulator_pin_role_mismatch"


def regulator_pin_role_candidates(
    observed: NetlistContract,
    requirements: RegulatorPassiveTopologyMap | None,
) -> tuple[Candidate, ...]:
    """Report only mismatches for pin roles explicitly supplied by the project."""
    if requirements is None:
        return ()
    by_id = {item.id.casefold(): item for item in requirements.requirements}
    findings: list[Candidate] = []
    for topology_id, issues in regulator_passive_pin_role_issues(requirements, observed):
        requirement = by_id[topology_id.casefold()]
        source = RegulatorPassivePinRoleFindingEvidence(
            observed=observed,
            requirements=requirements,
            topology_id=requirement.id,
            issues=issues,
        )
        findings.append(
            PowerCandidate.from_source_evidence(
                source,
                subject=f"{requirement.regulator.reference}: mapped pin roles differ",
                message=(
                    "The source-bound native netlist does not match the explicitly authored "
                    f"pin-function or electrical-type expectations for topology "
                    f"{requirement.id!r} ({requirement.basis}): {'; '.join(issues)}. Review "
                    "the exact component pin map and its independently reviewed basis. This "
                    "check does not validate that basis against a datasheet."
                ),
            )
        )
    return tuple(findings)
