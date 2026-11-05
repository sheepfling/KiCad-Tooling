"""Select mapped IC decoupling findings from native power evidence."""

from __future__ import annotations

from decimal import Decimal

from .design_lint_ic_decoupling_candidate_evidence import (
    IcDecouplingFindingEvidence,
    ic_decoupling_total_pf,
    review_ic_decoupling_requirement,
)
from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_types import Candidate
from .ic_decoupling_models import IcDecouplingMap
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index


def ic_decoupling_candidates(
    observed: NetlistContract,
    requirements: IcDecouplingMap | None,
) -> tuple[Candidate, ...]:
    """Report only mapped identity/topology faults or values below authored minimums."""
    if requirements is None:
        return ()
    pin_nets = netlist_pin_net_index(observed)
    found: list[Candidate] = []
    for requirement in sorted(requirements.requirements, key=lambda item: item.id.casefold()):
        review = review_ic_decoupling_requirement(observed, requirement, pin_nets)
        total_pf = ic_decoupling_total_pf(review)
        minimum_pf = Decimal(str(requirement.minimum_total_capacitance_pf))
        below_minimum = total_pf is not None and total_pf < minimum_pf
        if not review.issues and not below_minimum:
            continue
        if below_minimum:
            message = (
                f"The mapped fitted capacitor set totals {total_pf} pF, below the project-authored "
                f"minimum {minimum_pf} pF. Review the cited requirement and component network. "
                "Nominal schematic values do not establish tolerance, bias derating, placement, "
                "transient response, or physical return-path adequacy."
            )
        else:
            message = (
                "The source-bound netlist does not match the project-authored IC decoupling map: "
                + "; ".join(review.issues)
                + ". Review the exact identities, fitted state, pin inventory, and pin-to-net "
                "assignments before relying on the capacitance comparison."
            )
        source = IcDecouplingFindingEvidence(
            observed=observed,
            requirements=requirements,
            requirement_id=requirement.id,
            review=review,
            total_pf=total_pf,
            minimum_pf=minimum_pf,
        )
        found.append(
            PowerCandidate.from_source_evidence(
                source,
                subject=f"{requirement.id}: {requirement.power_pin}",
                message=message,
            )
        )
    return tuple(found)
