"""Review project-mapped active regulator-support component pin roles."""

from __future__ import annotations

from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_regulator_support_candidate_evidence import (
    RegulatorSupportPinRoleFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .regulator_support_checks import regulator_support_pin_role_issues
from .regulator_support_models import RegulatorSupportPinRoleMap

RULE_ID = "power.regulator_support_pin_role_mismatch"


def regulator_support_pin_role_candidates(
    observed: NetlistContract,
    requirements: RegulatorSupportPinRoleMap | None,
) -> tuple[Candidate, ...]:
    """Review only exact active-support identities and pin roles in the map."""
    if requirements is None:
        return ()
    by_id = {item.id.casefold(): item for item in requirements.requirements}
    components = {
        (topology.id.casefold(), component.reference.casefold()): component
        for topology in requirements.requirements
        for component in topology.components
    }
    findings: list[Candidate] = []
    for topology_id, reference, issues in regulator_support_pin_role_issues(requirements, observed):
        topology = by_id[topology_id.casefold()]
        component = components[(topology_id.casefold(), reference.casefold())]
        source = RegulatorSupportPinRoleFindingEvidence(
            observed=observed,
            requirements=requirements,
            topology_id=topology.id,
            component_reference=component.reference,
            issues=issues,
        )
        findings.append(
            PowerCandidate.from_source_evidence(
                source,
                subject=f"{component.reference}: mapped {component.role} pin roles differ",
                message=(
                    "The source-bound native netlist differs from the explicitly authored pin-role "
                    f"expectations for regulator {topology.regulator_reference} and support role "
                    f"{component.role!r} ({topology.basis}): {'; '.join(issues)}. Review the "
                    "exact component map and its independently reviewed basis. This check does "
                    "not establish the component's electrical function or topology correctness."
                ),
            )
        )
    return tuple(findings)
