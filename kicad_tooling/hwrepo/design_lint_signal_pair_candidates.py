"""Translate complementary-signal and named-pair observations."""

from __future__ import annotations

from .bus_signal_pairs import (
    ComplementaryPinFunctionAliasResolution,
    complementary_signal_gaps,
)
from .design_lint_signal_pair_candidate_evidence import SignalPairCandidate
from .design_lint_types import Candidate
from .differential_pair_names import named_differential_pairs
from .netlist_contract_models import NetlistContract
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
            and gap.positive_pins
            and gap.negative_pins
            and (not gap.positive_nets or not gap.negative_nets)
        ):
            # The per-pin CAN rule already reports open CANH/CANL assignments.
            continue
        found.append(
            SignalPairCandidate.from_source_evidence(
                source_evidence=gap,
                subject=f"{gap.reference}: {gap.family} pair",
                message=(
                    f"A recognized {gap.family} complementary pair has an incomplete or ambiguous "
                    f"schematic assignment: {gap.reason}. Review the interface pin map."
                ),
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
            SignalPairCandidate.from_source_evidence(
                source_evidence=pair,
                subject=f"{pair.positive_net} / {pair.negative_net}",
                message=(
                    "These source net names match a recognized complementary-signal pattern. "
                    "Review whether they form a physical differential pair and, if so, add "
                    "project-owned PCB constraints. The name pattern does not establish pair "
                    "intent, routing quality, or an acceptable skew limit."
                ),
            )
        )
    return tuple(found)
