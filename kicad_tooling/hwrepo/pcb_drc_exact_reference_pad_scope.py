"""Review exact custom DRC reference-and-pad selectors absent from the PCB."""

from __future__ import annotations

import json

from .design_lint_types import Candidate
from .pcb_drc_conditions import native_exact_reference_pad_condition
from .pcb_drc_rule_parser import NativeRuleConstraint
from .pcb_drc_source_evidence import BoundDrcEvidence

RULE_ID = "pcb.drc_exact_reference_pad_scope_unmatched"
SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.5"})


def unmatched_exact_reference_pad_scope_candidates(
    constraints: tuple[NativeRuleConstraint, ...],
    footprint_pads: tuple[tuple[str, tuple[str, ...]], ...],
    evidence: BoundDrcEvidence,
    *,
    kicad_version: str,
) -> tuple[Candidate, ...]:
    """Prompt for exact reference/pad scopes absent from an unambiguous PCB inventory."""
    if kicad_version not in SUPPORTED_KICAD_VERSIONS:
        return ()

    footprints_by_reference = {reference.casefold(): pads for reference, pads in footprint_pads}
    if len(footprints_by_reference) != len(footprint_pads):
        return ()

    grouped: dict[tuple[str, str], list[tuple[str, str, NativeRuleConstraint]]] = {}
    for constraint in constraints:
        if (
            not constraint.rule_name.strip()
            or constraint.issue is not None
            or constraint.severity_issue is not None
            or constraint.severity in {"ignore", "exclusion"}
        ):
            continue
        selector = native_exact_reference_pad_condition(constraint.condition)
        if selector is None:
            continue
        reference, pad_number = selector
        if not reference.isascii() or not pad_number.isascii():
            continue
        footprint_key = reference.casefold()
        if footprint_key not in footprints_by_reference:
            # The exact-reference lint owns scopes whose footprint is absent.
            continue
        current_pad_numbers = {value.casefold() for value in footprints_by_reference[footprint_key]}
        if pad_number.casefold() in current_pad_numbers:
            continue
        grouped.setdefault((footprint_key, pad_number.casefold()), []).append(
            (reference, pad_number, constraint)
        )

    candidates: list[Candidate] = []
    for key in sorted(grouped):
        matches = grouped[key]
        references = tuple(sorted({reference for reference, _, _ in matches}))
        pad_numbers = tuple(sorted({pad for _, pad, _ in matches}))
        constraints_for_scope = tuple(item for _, _, item in matches)
        reference = references[0]
        pad_number = pad_numbers[0]
        inventory = tuple(
            json.dumps((name, pads), ensure_ascii=True, separators=(",", ":"))
            for name, pads in footprint_pads
        )
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{reference} pad {pad_number}: exact custom DRC reference/pad selector "
                    "is absent from the current footprint"
                ),
                message=(
                    "The source-bound custom DRC rules contain exact A.Reference and "
                    f"A.Pad_Number selectors {references!r} / {pad_numbers!r}, but the matching "
                    "current PCB footprint has no pad with that number. Review whether the "
                    "selector is stale, reserved for another board variant, or needs a "
                    "project-specific disposition. This prompt does not decide that a pad "
                    "should exist or that the board has an electrical defect."
                ),
                evidence={
                    "reference_selectors": references,
                    "pad_number_selectors": pad_numbers,
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
                    "current_footprint_pad_inventory": inventory,
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
