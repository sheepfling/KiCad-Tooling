"""Synthetic reachability for omitted native signal-path rule scopes."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract


def unmapped_signal_path_rule_ids() -> set[str]:
    """Emit the active rule ID from one tooling-owned synthetic candidate."""
    project_id = "synthetic-unmapped-signal-path-length"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        netlist_sha256="f" * 64,
        observed=NetlistContract(components={}, nets={"EXTRA": ("J1.1",)}),
        source_hashes={},
    )
    candidates = (
        Candidate(
            rule_id="pcb.signal_path_unmapped_native_rule",
            subject="projects/synthetic/controller.kicad_dru#extra-length",
            message="Synthetic exact native length rule is absent from mapped path coverage.",
            evidence={"source_path": ("projects/synthetic/controller.kicad_dru",)},
        ),
        Candidate(
            rule_id="pcb.signal_path_unmapped_edge_clearance_rule",
            subject="projects/synthetic/controller.kicad_dru#extra-edge-clearance",
            message=(
                "Synthetic exact native edge-clearance rule is absent from mapped path coverage."
            ),
            evidence={"source_path": ("projects/synthetic/controller.kicad_dru",)},
        ),
        Candidate(
            rule_id="pcb.signal_path_unmapped_from_to_length_rule",
            subject="projects/synthetic/controller.kicad_dru#extra-fromto-length",
            message=(
                "Synthetic exact native fromTo length rule is absent from mapped path coverage."
            ),
            evidence={"source_path": ("projects/synthetic/controller.kicad_dru",)},
        ),
    )
    report = evaluate(
        project_id,
        coach,
        DesignLintPolicy(),
        pcb_dru_rule_candidates=candidates,
    )
    return {finding.rule_id for finding in report.findings}
