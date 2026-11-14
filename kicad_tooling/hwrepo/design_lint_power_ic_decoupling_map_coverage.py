"""Build review candidates for omitted IC decoupling map pins."""

from __future__ import annotations

from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .ic_decoupling_models import IcDecouplingMap
from .netlist_contract_models import NetlistContract
from .power_ic_decoupling_map_coverage import ic_decoupling_map_coverage_issues

RULE_ID: DesignLintRuleId = "power.ic_decoupling_map_pin_coverage"


def ic_decoupling_map_pin_coverage_candidates(
    observed: NetlistContract,
    requirements: IcDecouplingMap | None,
) -> tuple[Candidate, ...]:
    """Prompt for native supply pins or fitted ICs missing from the decoupling map."""
    candidates: list[Candidate] = []
    for issue in ic_decoupling_map_coverage_issues(observed, requirements):
        if issue.component_unmapped_from_map:
            candidates.append(
                PowerCandidate.from_source_evidence(
                    issue,
                    subject=(
                        f"{issue.reference}: IC decoupling-map component coverage needs review"
                    ),
                    message=(
                        f"The optional IC decoupling map has no entry for fitted {issue.reference}, "
                        "whose native power-input pins are "
                        f"{', '.join(issue.native_power_input_pins)}. Review whether this IC "
                        "needs a source-backed per-pin requirement or an exact reasoned ignore. "
                        "This prompt does not infer that a capacitor is required, choose a "
                        "capacitance, or establish placement or return-path adequacy."
                    ),
                )
            )
            continue
        details: list[str] = []
        if issue.stale_map_identity:
            details.append("the mapped component identity is stale")
        if issue.unmapped_power_input_pins:
            details.append(
                "power-input pins without map entries: "
                + ", ".join(issue.unmapped_power_input_pins)
            )
        if issue.pin_type_unavailable_pins:
            details.append(
                "native electrical type is unavailable for: "
                + ", ".join(issue.pin_type_unavailable_pins)
            )
        if issue.pin_inventory_unavailable:
            details.append("the complete native pin inventory is unavailable")
        if issue.pin_inventory_disagreement_pins:
            details.append(
                "typed pins are absent from the native pin inventory: "
                + ", ".join(issue.pin_inventory_disagreement_pins)
            )
        candidates.append(
            PowerCandidate.from_source_evidence(
                issue,
                subject=f"{issue.reference}: IC decoupling-map pin coverage needs review",
                message=(
                    f"The current decoupling map does not account for complete native power-input "
                    f"coverage on {issue.reference}: {'; '.join(details)}. Add a reviewed per-pin "
                    "requirement where one applies, or record a reasoned exact ignore for an "
                    "intentional exclusion. This prompt does not infer that a capacitor is "
                    "required, choose a capacitance, or establish placement or return-path adequacy."
                ),
            )
        )
    return tuple(candidates)
