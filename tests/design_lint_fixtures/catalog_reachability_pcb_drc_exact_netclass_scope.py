"""Source-bound catalog reachability for an absent exact DRC netclass scope."""

from __future__ import annotations

import hashlib
from pathlib import Path

from kicad_tooling.hwrepo.pcb_drc_exact_netclass_scope import (
    unmatched_exact_netclass_scope_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_netclass_scope_inventory import (
    pcb_project_netclass_scope_names,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence

FIXTURES = Path(__file__).parent.parent / "fixtures/design_lint/pcb-drc-exact-netclass-scope"


def pcb_drc_exact_netclass_scope_rule_ids() -> set[str]:
    """Return the rule ID reached by the tooling-owned absent-class selector."""
    settings = (FIXTURES / "declared.kicad_pro").read_text(encoding="utf-8")
    rules = (FIXTURES / "absent.kicad_dru").read_text(encoding="utf-8")
    names = pcb_project_netclass_scope_names(settings)
    if names is None:
        return set()
    evidence = BoundDrcEvidence(
        project_path="projects/synthetic/board.kicad_pro",
        project_sha256=hashlib.sha256(settings.encode("utf-8")).hexdigest(),
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256=hashlib.sha256(rules.encode("utf-8")).hexdigest(),
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
        rules_source=rules,
        ignored_checks=frozenset(),
    )
    candidates = unmatched_exact_netclass_scope_candidates(
        native_constraints(rules), names, evidence, kicad_version="10.0.5"
    )
    return {candidate.rule_id for candidate in candidates}
