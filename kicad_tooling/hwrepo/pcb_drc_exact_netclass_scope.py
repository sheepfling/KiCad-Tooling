"""Review exact custom DRC netclass selectors absent from project settings."""

from __future__ import annotations

from .design_lint_types import Candidate
from .pcb_drc_conditions import native_exact_netclass_condition
from .pcb_drc_rule_parser import NativeRuleConstraint
from .pcb_drc_source_evidence import BoundDrcEvidence

RULE_ID = "pcb.drc_exact_netclass_scope_unmatched"
SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5"})


def unmatched_exact_netclass_scope_candidates(
    constraints: tuple[NativeRuleConstraint, ...],
    project_netclass_names: tuple[str, ...],
    evidence: BoundDrcEvidence,
    *,
    kicad_version: str,
) -> tuple[Candidate, ...]:
    """Prompt for exact class scopes absent from all supported project sources."""
    if kicad_version not in SUPPORTED_KICAD_VERSIONS:
        return ()
    folded_names = tuple(name.casefold() for name in project_netclass_names)
    if len(set(folded_names)) != len(folded_names):
        return ()

    grouped: dict[str, list[tuple[str, NativeRuleConstraint]]] = {}
    current_names = set(folded_names)
    for constraint in constraints:
        if (
            not constraint.rule_name.strip()
            or constraint.issue is not None
            or constraint.severity_issue is not None
            or constraint.severity in {"ignore", "exclusion"}
        ):
            continue
        netclass = native_exact_netclass_condition(constraint.condition)
        if netclass is None or not netclass.isascii() or netclass.casefold() in current_names:
            continue
        grouped.setdefault(netclass.casefold(), []).append((netclass, constraint))

    candidates: list[Candidate] = []
    for matches in (grouped[key] for key in sorted(grouped)):
        selectors = tuple(sorted({selector for selector, _ in matches}))
        constraints_for_scope = tuple(item for _, item in matches)
        selector_label = selectors[0]
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{selector_label}: exact custom DRC netclass selector is absent "
                    "from current project settings"
                ),
                message=(
                    f"The source-bound custom DRC rules contain exact A.NetClass selectors "
                    f"{selectors!r}, but none matches a class declared or referenced by the "
                    "current project settings. Review whether the selector is stale, reserved "
                    "for another variant, or needs a project-specific disposition. This prompt "
                    "does not decide that the class should exist or that the board has an "
                    "electrical defect."
                ),
                evidence={
                    "netclass_selectors": selectors,
                    "native_rule_names": tuple(
                        sorted({item.rule_name for item in constraints_for_scope})
                    ),
                    "native_constraint_count": (str(len(constraints_for_scope)),),
                    "native_constraints": tuple(
                        sorted({item.name for item in constraints_for_scope})
                    ),
                    "native_conditions": tuple(
                        sorted({item.condition for item in constraints_for_scope})
                    ),
                    "native_bounds_nm": tuple(
                        sorted(
                            f"{item.name}:min={item.minimum_nm};max={item.maximum_nm}"
                            for item in constraints_for_scope
                        )
                    ),
                    "native_layers": tuple(
                        sorted({item.layer or "<all layers>" for item in constraints_for_scope})
                    ),
                    "native_severities": tuple(
                        sorted({item.severity or "<default>" for item in constraints_for_scope})
                    ),
                    "project_netclass_names": project_netclass_names,
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
