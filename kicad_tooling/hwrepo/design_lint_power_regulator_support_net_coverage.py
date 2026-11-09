"""Review active regulator-support components missing pin-to-net map coverage."""

from __future__ import annotations

from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_regulator_support_candidate_evidence import (
    RegulatorSupportPinNetCoverageFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .regulator_support_checks import regulator_support_pin_net_coverage_issues
from .regulator_support_models import RegulatorSupportPinNetMap, RegulatorSupportPinRoleMap

RULE_ID = "power.regulator_support_pin_net_map_coverage_missing"


def regulator_support_pin_net_coverage_candidates(
    observed: NetlistContract,
    role_requirements: RegulatorSupportPinRoleMap | None,
    net_requirements: RegulatorSupportPinNetMap | None,
) -> tuple[Candidate, ...]:
    """Prompt when exact active support-role entries lack pin-net map coverage."""
    if role_requirements is None:
        return ()
    topologies = {item.id.casefold(): item for item in role_requirements.requirements}
    components = {
        (topology.id.casefold(), component.reference.casefold()): component
        for topology in role_requirements.requirements
        for component in topology.components
    }
    findings: list[Candidate] = []
    for topology_id, reference, issues in regulator_support_pin_net_coverage_issues(
        role_requirements,
        net_requirements,
        observed,
    ):
        topology = topologies[topology_id.casefold()]
        component = components[(topology_id.casefold(), reference.casefold())]
        source = RegulatorSupportPinNetCoverageFindingEvidence(
            observed=observed,
            role_requirements=role_requirements,
            net_requirements=net_requirements,
            topology_id=topology.id,
            component_reference=component.reference,
            issues=issues,
        )
        findings.append(
            PowerCandidate.from_source_evidence(
                source,
                subject=f"{component.reference}: active support pin-to-net map coverage is missing",
                message=(
                    "The source-matched active support-role map declares "
                    f"{component.reference} ({component.role}) under regulator "
                    f"{topology.regulator_reference}, but the separate pin-to-net map does not "
                    f"cover it: {'; '.join(issues)}. Review whether an exact assignment map is "
                    "required for this component. No expected nets are inferred."
                ),
            )
        )
    return tuple(findings)
