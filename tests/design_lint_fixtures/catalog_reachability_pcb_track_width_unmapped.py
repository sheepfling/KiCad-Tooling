"""Synthetic reachability case for omitted native track-width scope review."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract


def unmapped_track_width_rule_ids() -> set[str]:
    """Return the catalog ID emitted for a synthetic omitted-width-scope finding."""
    project_id = "synthetic-unmapped-track-width"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        netlist_sha256="f" * 64,
        observed=NetlistContract(components={}, nets={}),
        source_hashes={},
    )
    candidate = Candidate(
        rule_id="pcb.track_width_unmapped_native_rule",
        subject="projects/synthetic/controller.kicad_dru#data-width",
        message="Synthetic per-net track-width rule is absent from mapped geometry scope.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_dru",)},
    )
    report = evaluate(
        project_id,
        coach,
        DesignLintPolicy(),
        pcb_dru_rule_candidates=(candidate,),
    )
    return {finding.rule_id for finding in report.findings}
