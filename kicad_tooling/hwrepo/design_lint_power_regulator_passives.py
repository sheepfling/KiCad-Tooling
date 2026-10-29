"""Find mismatches in project-authored regulator-required passive topologies."""

from __future__ import annotations

import hashlib

from .design_lint_types import Candidate
from .models import NetlistContract
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
    map_sha256 = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    by_id = {item.id.casefold(): item for item in requirements.requirements}
    findings: list[Candidate] = []
    for topology_id, issues in regulator_passive_topology_issues(requirements, observed):
        requirement = by_id[topology_id.casefold()]
        references = (
            requirement.regulator.reference,
            *(item.component.reference for item in requirement.required_passives),
        )
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{requirement.regulator.reference}: required passive topology differs",
                message=(
                    f"The source-bound native netlist does not match the project-authored "
                    f"regulator passive topology {requirement.id!r} ({requirement.basis}): "
                    f"{'; '.join(issues)}. Review the exact component and pin map. The cited "
                    "basis is project-authored and is not verified by this check."
                ),
                evidence={
                    "topology_id": (requirement.id,),
                    "regulator": (requirement.regulator.reference,),
                    "required_passive_roles": tuple(
                        f"{item.role}:{item.component.reference}"
                        for item in requirement.required_passives
                    ),
                    "components": tuple(sorted(references, key=str.casefold)),
                    "issues": issues,
                    "map_sha256": (map_sha256,),
                },
            )
        )
    return tuple(findings)
