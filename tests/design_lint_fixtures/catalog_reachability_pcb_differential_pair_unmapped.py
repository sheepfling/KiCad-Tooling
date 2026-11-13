"""Synthetic catalog reachability for unmapped exact pair-rule selectors."""

from __future__ import annotations

import hashlib
from pathlib import Path

from kicad_tooling.hwrepo.pcb_differential_pair_unmapped import (
    unmapped_differential_pair_rule_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_models import (
    PcbDifferentialPairRuleMap,
    PcbDifferentialPairRuleRequirement,
    PcbDrcMaximumRequirement,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence


def unmapped_differential_pair_rule_ids() -> set[str]:
    """Return the rule ID emitted for a selector omitted from a synthetic map."""
    source = (
        '(version 1)\n(rule "motor skew" (severity warning) '
        "(condition \"A.inDiffPair('MOTOR_')\") "
        "(constraint skew (max 0.5mm)))"
    )
    requirement = PcbDifferentialPairRuleRequirement(
        id="usb",
        basis="Synthetic reviewed interface requirement",
        positive_net="USB_D_P",
        negative_net="USB_D_N",
        pair_selector="USB_D_",
        skew=PcbDrcMaximumRequirement(max_nm=100_000),
    )
    pair_map = PcbDifferentialPairRuleMap(
        basis="Synthetic reviewed pair map", requirements=(requirement,)
    )
    evidence = BoundDrcEvidence(
        project_path="projects/synthetic/board.kicad_pro",
        project_sha256="a" * 64,
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256="b" * 64,
        native_summary_path="build/native/summary.json",
        native_summary_sha256="c" * 64,
        native_drc_path="build/native/drc.json",
        native_drc_sha256="d" * 64,
        project_file=Path("projects/synthetic/board.kicad_pro"),
        board_file=Path("projects/synthetic/board.kicad_pcb"),
        summary_file=Path("build/native/summary.json"),
        summary_sha256_before="c" * 64,
        drc_file=Path("build/native/drc.json"),
        command_file=Path("build/native/drc.command.json"),
        command_sha256="e" * 64,
        rules_source=source,
        ignored_checks=frozenset(),
    )
    candidates = unmapped_differential_pair_rule_candidates(
        pair_map,
        native_constraints(source),
        evidence,
        kicad_version="10.0.5",
    )
    return {candidate.rule_id for candidate in candidates}
