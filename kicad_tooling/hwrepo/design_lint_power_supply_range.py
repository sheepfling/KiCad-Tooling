"""Build project-mapped supply operating-range review findings."""

from __future__ import annotations

from .component_supply_range_models import ComponentSupplyVoltageRangeMap
from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .power_component_supply_range import component_supply_voltage_range_issues


def component_supply_voltage_range_candidates(
    observed: NetlistContract,
    requirements: ComponentSupplyVoltageRangeMap | None,
) -> tuple[Candidate, ...]:
    """Review mapped supply pins with stale identity, missing evidence, or out-of-range labels."""
    candidates: list[Candidate] = []
    for issue in component_supply_voltage_range_issues(observed, requirements):
        requirement = issue.requirement
        candidates.append(
            PowerCandidate.from_source_evidence(
                issue,
                subject=f"{requirement.pin}: component supply operating-range review",
                message=(
                    f"The exact project-mapped supply pin {requirement.pin} needs review: "
                    f"{' ; '.join(issue.issues)}. The configured operating range is "
                    f"{requirement.minimum_voltage_v:g} to {requirement.maximum_voltage_v:g} V "
                    f"per {requirement.range_source} ({requirement.range_conditions}). "
                    "Net-label voltages are nominal clues only; verify the actual supply, "
                    "tolerances, sequencing, and part-specific operating conditions."
                ),
            )
        )
    return tuple(candidates)
