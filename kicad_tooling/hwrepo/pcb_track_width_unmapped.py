"""Find exact native track-width scopes omitted from geometry review."""

from __future__ import annotations

import hashlib

from .design_lint_types import Candidate
from .pcb_drc_conditions import native_exact_net_condition
from .pcb_drc_rule_parser import NativeRuleConstraint
from .pcb_drc_source_evidence import BoundDrcEvidence
from .pcb_track_width_models import PcbTrackWidthMap

RULE_ID = "pcb.track_width_unmapped_native_rule"


def unmapped_track_width_rule_candidates(
    requirements: PcbTrackWidthMap,
    constraints: tuple[NativeRuleConstraint, ...],
    evidence: BoundDrcEvidence,
    *,
    kicad_version: str,
) -> tuple[Candidate, ...]:
    """Prompt when exact native track-width scopes are outside the review map."""
    mapped_nets = {item.net.casefold() for item in requirements.requirements}
    if "*" in mapped_nets:
        return ()

    groups: dict[tuple[str, str], list[NativeRuleConstraint]] = {}
    labels: dict[tuple[str, str], tuple[str, str]] = {}
    for constraint in constraints:
        if constraint.name != "track_width" or not constraint.rule_name.strip():
            continue
        net = native_exact_net_condition(constraint.condition)
        if net is None or net.casefold() in mapped_nets:
            continue
        key = (constraint.rule_name.casefold(), net.casefold())
        groups.setdefault(key, []).append(constraint)
        prior = labels.get(key, (constraint.rule_name, net))
        labels[key] = (min(prior[0], constraint.rule_name), min(prior[1], net))

    map_sha256 = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    candidates: list[Candidate] = []
    for key, matches in sorted(groups.items()):
        rule_name, net = labels[key]
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{rule_name}: {net} is absent from track-width geometry scope",
                message=(
                    f"The source-bound native track_width rule {rule_name!r} targets exact net "
                    f"{net!r}, but that net is absent from pcb_track_width_map while "
                    "pcb.minimum_track_width is enabled. Add an independently reviewed map "
                    "entry if geometry lint should cover it, or disposition this prompt if the "
                    "omission is intentional. Native DRC remains the authority for its "
                    "configured rule; the geometry map is not an ampacity calculation."
                ),
                evidence={
                    "native_rule_name": tuple(sorted({item.rule_name for item in matches})),
                    "native_rule_count": (str(len(matches)),),
                    "net": tuple(
                        sorted(
                            {native_exact_net_condition(item.condition) or net for item in matches}
                        )
                    ),
                    "map_basis": (requirements.basis,),
                    "map_sha256": (map_sha256,),
                    "native_conditions": tuple(sorted({item.condition for item in matches})),
                    "native_width_bounds_nm": tuple(
                        sorted(f"min={item.minimum_nm};max={item.maximum_nm}" for item in matches)
                    ),
                    "native_layers": tuple(
                        sorted({item.layer or "<all layers>" for item in matches})
                    ),
                    "native_severities": tuple(
                        sorted({item.severity or "<default>" for item in matches})
                    ),
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
