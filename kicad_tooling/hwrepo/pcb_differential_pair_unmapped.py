"""Review exact native differential-pair selectors omitted from the project map."""

from __future__ import annotations

import hashlib

from .design_lint_types import Candidate
from .pcb_drc_conditions import native_exact_diff_pair_condition
from .pcb_drc_models import PcbDifferentialPairRuleMap
from .pcb_drc_rule_parser import NativeRuleConstraint
from .pcb_drc_source_evidence import BoundDrcEvidence

RULE_ID = "pcb.differential_pair_unmapped_native_rule"
_PAIR_CONSTRAINTS = frozenset(
    {"track_width", "diff_pair_gap", "skew", "diff_pair_uncoupled", "edge_clearance"}
)


def unmapped_differential_pair_rule_candidates(
    requirements: PcbDifferentialPairRuleMap,
    constraints: tuple[NativeRuleConstraint, ...],
    evidence: BoundDrcEvidence,
    *,
    kicad_version: str,
) -> tuple[Candidate, ...]:
    """Prompt for exact pair selectors absent from an enabled project pair map."""
    mapped_selectors = {item.pair_selector for item in requirements.requirements}
    grouped: dict[str, list[NativeRuleConstraint]] = {}
    for constraint in constraints:
        if constraint.name not in _PAIR_CONSTRAINTS or not constraint.rule_name.strip():
            continue
        selector = native_exact_diff_pair_condition(constraint.condition)
        if selector is None or selector in mapped_selectors:
            continue
        grouped.setdefault(selector, []).append(constraint)

    map_sha256 = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    candidates: list[Candidate] = []
    for selector, matches in sorted(grouped.items()):
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{selector}: native differential-pair rule scope is absent from the project map",
                message=(
                    f"The source-bound native DRC rules use exact A.inDiffPair({selector!r}) "
                    "conditions, but that selector is absent from "
                    "pcb_differential_pair_rule_map while pcb.differential_pair_rule_coverage "
                    "is enabled. Add an independently reviewed pair requirement if the scope "
                    "needs coverage, or disposition this prompt if the omission is intentional. "
                    "The finding does not infer pair identity, required limits, or DRC geometry."
                ),
                evidence={
                    "pair_selector": (selector,),
                    "native_rule_names": tuple(sorted({item.rule_name for item in matches})),
                    "native_constraint_count": (str(len(matches)),),
                    "native_constraints": tuple(sorted({item.name for item in matches})),
                    "native_conditions": tuple(sorted({item.condition for item in matches})),
                    "native_bounds_nm": tuple(
                        sorted(
                            f"{item.name}:min={item.minimum_nm};max={item.maximum_nm}"
                            for item in matches
                        )
                    ),
                    "native_layers": tuple(
                        sorted({item.layer or "<all layers>" for item in matches})
                    ),
                    "native_severities": tuple(
                        sorted({item.severity or "<default>" for item in matches})
                    ),
                    "map_basis": (requirements.basis,),
                    "map_sha256": (map_sha256,),
                    "source_path": (evidence.rules_path,),
                    "source_sha256": (evidence.rules_sha256 or "<rules-file-absent>",),
                    "project_path": (evidence.project_path,),
                    "project_sha256": (evidence.project_sha256,),
                    "board_path": (evidence.board_path,),
                    "board_sha256": (evidence.board_sha256,),
                    "native_drc_path": (evidence.native_drc_path,),
                    "native_drc_sha256": (evidence.native_drc_sha256,),
                    "native_drc_kicad_version": (kicad_version,),
                    "native_summary_path": (evidence.native_summary_path,),
                    "native_summary_sha256": (evidence.native_summary_sha256,),
                },
            )
        )
    return tuple(candidates)
