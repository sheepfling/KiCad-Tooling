"""Source-bound catalog reachability for an absent exact DRC reference scope."""

from __future__ import annotations

import hashlib
from pathlib import Path

from kicad_tooling.hwrepo.pcb_drc_exact_reference_scope import (
    unmatched_exact_reference_scope_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence
from kicad_tooling.hwrepo.pcb_footprint_reference_inventory import (
    pcb_board_footprint_reference_names,
)

FIXTURES = Path(__file__).parent.parent / "fixtures/design_lint/pcb-drc-exact-reference-scope"
BOARD = (
    Path(__file__).parent.parent
    / "fixtures/design_lint/pcb-mechanical-edge-clearance/control.kicad_pcb"
)


def pcb_drc_exact_reference_scope_rule_ids() -> set[str]:
    """Return the rule ID reached by a tooling-owned absent-reference selector."""
    rules = (FIXTURES / "absent.kicad_dru").read_text(encoding="utf-8")
    board = BOARD.read_text(encoding="utf-8")
    references = pcb_board_footprint_reference_names(board)
    if references is None:
        return set()
    rules_hash = hashlib.sha256(rules.encode("utf-8")).hexdigest()
    board_hash = hashlib.sha256(board.encode("utf-8")).hexdigest()
    evidence = BoundDrcEvidence(
        project_path="projects/synthetic/board.kicad_pro",
        project_sha256="a" * 64,
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256=rules_hash,
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=board_hash,
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
        rules_source=rules,
        ignored_checks=frozenset(),
    )
    candidates = unmatched_exact_reference_scope_candidates(
        native_constraints(rules), references, evidence, kicad_version="10.0.5"
    )
    return {candidate.rule_id for candidate in candidates}
