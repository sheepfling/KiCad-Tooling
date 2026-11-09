"""Review project-mapped active regulator-support pin-to-net assignments."""

from __future__ import annotations

from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_regulator_support_candidate_evidence import (
    RegulatorSupportPinNetFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .regulator_support_checks import regulator_support_pin_net_issues
from .regulator_support_models import RegulatorSupportPinNetMap

RULE_ID = "power.regulator_support_pin_net_mismatch"


def regulator_support_pin_net_candidates(
    observed: NetlistContract,
    requirements: RegulatorSupportPinNetMap | None,
) -> tuple[Candidate, ...]:
    """Review only exact active-support pin assignments declared by a project."""
    if requirements is None:
        return ()
    topologies = {item.id.casefold(): item for item in requirements.requirements}
    components = {
        (topology.id.casefold(), component.reference.casefold()): component
        for topology in requirements.requirements
        for component in topology.components
    }
    findings: list[Candidate] = []
    for topology_id, reference, issues in regulator_support_pin_net_issues(requirements, observed):
        topology = topologies[topology_id.casefold()]
        component = components[(topology_id.casefold(), reference.casefold())]
        source = RegulatorSupportPinNetFindingEvidence(
            observed=observed,
            requirements=requirements,
            topology_id=topology.id,
            component_reference=component.reference,
            issues=issues,
        )
        findings.append(
            PowerCandidate.from_source_evidence(
                source,
                subject=f"{component.reference}: mapped {component.role} pin-to-net assignments differ",
                message=(
                    "The source-bound native netlist differs from the explicit pin-to-net map for "
                    f"regulator {topology.regulator_reference} and support role {component.role!r} "
                    f"({topology.basis}): {'; '.join(issues)}. Review the independently reviewed "
                    "project requirement. This schematic comparison does not establish a physical "
                    "bond, PCB copper continuity, component conduction, or topology correctness."
                ),
            )
        )
    return tuple(findings)
