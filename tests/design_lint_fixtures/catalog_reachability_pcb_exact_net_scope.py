"""Synthetic catalog reachability for an exact DRC net scope absent from PCB source."""

from __future__ import annotations

import hashlib
from pathlib import Path

from kicad_tooling.hwrepo.pcb_board_net_inventory import pcb_board_net_names
from kicad_tooling.hwrepo.pcb_drc_exact_net_scope import unmatched_exact_net_scope_candidates
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures/design_lint/pcb-drc-exact-net-scope"


def exact_net_scope_rule_ids() -> set[str]:
    """Return the active rule ID emitted by the tooling-owned missing-net scope."""
    source = (FIXTURE_DIR / "stale.kicad_dru").read_text(encoding="utf-8")
    board_text = (FIXTURE_DIR / "board.kicad_pcb").read_text(encoding="utf-8")
    board_nets = pcb_board_net_names(board_text)
    if board_nets is None:
        return set()
    evidence = BoundDrcEvidence(
        project_path="projects/synthetic/board.kicad_pro",
        project_sha256="a" * 64,
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=hashlib.sha256(board_text.encode("utf-8")).hexdigest(),
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
    candidates = unmatched_exact_net_scope_candidates(
        native_constraints(source), board_nets, evidence, kicad_version="10.0.5"
    )
    return {candidate.rule_id for candidate in candidates}
