"""Build review candidates for incomplete mapped supply-range pin coverage."""

from __future__ import annotations

from .component_supply_range_models import ComponentSupplyVoltageRangeMap
from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .power_component_supply_range_coverage import component_supply_range_pin_coverage_issues

RULE_ID: DesignLintRuleId = "power.component_supply_range_pin_coverage"


def component_supply_range_pin_coverage_candidates(
    observed: NetlistContract,
    requirements: ComponentSupplyVoltageRangeMap | None,
) -> tuple[Candidate, ...]:
    """Review native supply pins omitted from the authored range map."""
    candidates: list[Candidate] = []
    for issue in component_supply_range_pin_coverage_issues(observed, requirements):
        details: list[str] = []
        if issue.unmapped_power_input_pins:
            details.append(
                "power-input pins without range entries: "
                + ", ".join(issue.unmapped_power_input_pins)
            )
        if issue.pin_type_unavailable_pins:
            details.append(
                "native electrical type is unavailable for: "
                + ", ".join(issue.pin_type_unavailable_pins)
            )
        if issue.pin_inventory_disagreement_pins:
            details.append(
                "native typed pins missing from the pin inventory: "
                + ", ".join(issue.pin_inventory_disagreement_pins)
            )
        if issue.pin_inventory_unavailable:
            details.append("the native component pin inventory is unavailable")
        candidates.append(
            PowerCandidate.from_source_evidence(
                issue,
                subject=f"{issue.reference}: supply-range pin coverage needs review",
                message=(
                    "The source-matched supply-range map does not account for complete native "
                    f"power-input coverage on {issue.reference}: {'; '.join(details)}. Add or "
                    "correct the reviewed per-pin requirements. This check covers only mapped "
                    "references and native symbol metadata; it does not verify the symbol against "
                    "the physical package or validate the authored voltage ranges."
                ),
            )
        )
    return tuple(candidates)
