"""Review exact custom DRC net selectors absent from the current PCB net table."""

from __future__ import annotations

from .design_lint_types import Candidate
from .pcb_drc_conditions import native_exact_net_condition
from .pcb_drc_rule_parser import NativeRuleConstraint
from .pcb_drc_source_evidence import BoundDrcEvidence

RULE_ID = "pcb.drc_exact_net_scope_unmatched"
SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5"})


def unmatched_exact_net_scope_candidates(
    constraints: tuple[NativeRuleConstraint, ...],
    board_net_names: tuple[str, ...],
    evidence: BoundDrcEvidence,
    *,
    kicad_version: str,
) -> tuple[Candidate, ...]:
    """Prompt for supported exact rule selectors absent from source PCB nets."""
    if kicad_version not in SUPPORTED_KICAD_VERSIONS:
        return ()

    folded_names = tuple(name.casefold() for name in board_net_names)
    # KiCad's A.NetName equality is case-insensitive. If the source PCB has
    # names that collapse under case-folding, the match is ambiguous here, so
    # avoid presenting any selector as definitely absent.
    if len(set(folded_names)) != len(folded_names):
        return ()
    current_names = set(folded_names)
    grouped: dict[str, list[NativeRuleConstraint]] = {}
    for constraint in constraints:
        if (
            not constraint.rule_name.strip()
            or constraint.issue is not None
            or constraint.severity_issue is not None
            or constraint.severity in {"ignore", "exclusion"}
        ):
            continue
        net = native_exact_net_condition(constraint.condition)
        if net is None or "$" in net or net.casefold() in current_names:
            continue
        grouped.setdefault(net, []).append(constraint)

    candidates: list[Candidate] = []
    for net, matches in sorted(grouped.items()):
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{net}: exact custom DRC net selector is absent from the current PCB",
                message=(
                    f"The source-bound custom DRC rules contain exact A.NetName == {net!r} "
                    "scopes, but the current PCB net table has no exact matching name. "
                    "Review whether the rule is stale, intentionally reserved for another "
                    "variant, or needs a project-specific disposition. This prompt does not "
                    "decide that the net should exist or that the board has an electrical defect."
                ),
                evidence={
                    "net_selector": (net,),
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
                    "current_board_net_count": (str(len(board_net_names)),),
                    "rules_path": (evidence.rules_path,),
                    "rules_sha256": (evidence.rules_sha256 or "<rules-file-absent>",),
                    "board_path": (evidence.board_path,),
                    "board_sha256": (evidence.board_sha256,),
                    "project_path": (evidence.project_path,),
                    "project_sha256": (evidence.project_sha256,),
                    "native_drc_path": (evidence.native_drc_path,),
                    "native_drc_sha256": (evidence.native_drc_sha256,),
                    "native_drc_kicad_version": (kicad_version,),
                    "native_summary_path": (evidence.native_summary_path,),
                    "native_summary_sha256": (evidence.native_summary_sha256,),
                },
            )
        )
    return tuple(candidates)
