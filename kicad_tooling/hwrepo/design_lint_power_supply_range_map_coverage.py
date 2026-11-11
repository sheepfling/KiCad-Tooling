"""Build review candidates for unmapped IC power-input ranges."""

from __future__ import annotations

from .component_supply_range_models import ComponentSupplyVoltageRangeMap
from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .power_component_supply_range_map_coverage import (
    component_supply_range_map_coverage_issues,
)

RULE_ID: DesignLintRuleId = "power.component_supply_range_map_coverage"


def component_supply_range_map_coverage_candidates(
    observed: NetlistContract,
    requirements: ComponentSupplyVoltageRangeMap | None,
) -> tuple[Candidate, ...]:
    """Prompt when recognized IC power inputs lack a current authored range map."""
    candidates: list[Candidate] = []
    for issue in component_supply_range_map_coverage_issues(observed, requirements):
        if issue.stale_map_identity:
            detail = "the map's symbol, footprint, or PART_ID does not match native evidence"
        else:
            detail = "no exact component supply-range map entry covers the current identity"
        candidates.append(
            PowerCandidate.from_source_evidence(
                issue,
                subject=f"{issue.reference}: IC supply-range map coverage needs review",
                message=(
                    f"Native KiCad metadata identifies {', '.join(issue.native_power_input_pins)} "
                    f"on {issue.reference} as power inputs, but {detail}. Add a reviewed range "
                    "for each applicable supply pin or explicitly disable this optional coverage "
                    "rule for the project. This prompt does not infer voltage limits, required "
                    "nets, or whether separate supply domains should be joined."
                ),
            )
        )
    return tuple(candidates)
