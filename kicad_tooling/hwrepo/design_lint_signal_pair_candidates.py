"""Translate complementary-signal and named-pair observations."""

from __future__ import annotations

from .bus_signal_pairs import (
    ComplementaryPinFunctionAliasResolution,
    complementary_signal_gaps,
)
from .design_lint_types import Candidate
from .differential_pair_names import named_differential_pairs
from .models import NetlistContract
from .pcb_drc_models import PcbDifferentialPairRuleMap


def complementary_signal_candidates(
    observed: NetlistContract,
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution | None = None,
) -> tuple[Candidate, ...]:
    """Build review prompts for complementary pin-function gaps."""
    found: list[Candidate] = []
    for gap in complementary_signal_gaps(observed, complementary_alias_resolution):
        if (
            gap.family == "CAN"
            and gap.alias_symbol is None
            and gap.pins["positive"]
            and gap.pins["negative"]
            and (not gap.nets["positive"] or not gap.nets["negative"])
        ):
            # The per-pin CAN rule already reports open CANH/CANL assignments.
            continue
        evidence = {
            "positive_pins": gap.pins["positive"],
            "negative_pins": gap.pins["negative"],
            "positive_nets": gap.nets["positive"],
            "negative_nets": gap.nets["negative"],
        }
        if gap.alias_symbol is not None:
            if gap.alias_basis is None or gap.alias_sha256 is None:
                raise AssertionError(
                    "Resolved complementary aliases must retain their basis digest"
                )
            evidence.update(
                {
                    "alias_symbol": (gap.alias_symbol,),
                    "alias_basis": (gap.alias_basis,),
                    "alias_sha256": (gap.alias_sha256,),
                }
            )
        found.append(
            Candidate(
                rule_id="bus.complementary_pair_assignment",
                subject=f"{gap.reference}: {gap.family} pair",
                message=(
                    f"A recognized {gap.family} complementary pair has an incomplete or ambiguous "
                    f"schematic assignment: {gap.reason}. Review the interface pin map."
                ),
                evidence=evidence,
            )
        )
    return tuple(found)


def named_differential_pair_candidates(
    observed: NetlistContract,
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None = None,
) -> tuple[Candidate, ...]:
    """Build prompts for recognized differential-pair net names."""
    found: list[Candidate] = []
    for pair in named_differential_pairs(observed.nets, pcb_differential_pair_rule_map):
        found.append(
            Candidate(
                rule_id="signal.named_pair_without_reviewed_requirement",
                subject=f"{pair.positive_net} / {pair.negative_net}",
                message=(
                    "These source net names match a recognized complementary-signal pattern. "
                    "Review whether they form a physical differential pair and, if so, add "
                    "project-owned PCB constraints. The name pattern does not establish pair "
                    "intent, routing quality, or an acceptable skew limit."
                ),
                evidence={
                    "positive_net": (pair.positive_net,),
                    "positive_references": pair.positive_references,
                    "negative_net": (pair.negative_net,),
                    "negative_references": pair.negative_references,
                    "naming_pattern": (pair.naming_pattern,),
                },
            )
        )
    return tuple(found)
