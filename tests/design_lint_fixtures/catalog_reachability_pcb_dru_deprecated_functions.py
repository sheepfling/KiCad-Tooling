"""Synthetic reachability input for deprecated DRC function review."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_dru_deprecated_function_review import (
    custom_drc_deprecated_condition_function_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach


def custom_drc_deprecated_function_rule_ids() -> set[str]:
    """Reach the source-bound predicate from one tooling-owned rule fixture."""
    rule_path = "projects/controller.kicad_dru"
    fixture = (
        Path(__file__).parents[1]
        / "fixtures/design_lint/pcb-dru-deprecated-condition-functions/fault.kicad_dru"
    )
    with TemporaryDirectory(prefix="kicad-dru-deprecated-functions-") as temporary:
        root = Path(temporary)
        project_sources = root / "projects"
        project_sources.mkdir()
        rules = root / rule_path
        rules.write_bytes(fixture.read_bytes())
        config = cast(
            ProjectConfig,
            SimpleNamespace(
                kind=ProjectKind.PCB,
                project="projects/controller.kicad_pro",
                kicad_version="10.0.8",
            ),
        )
        candidates = custom_drc_deprecated_condition_function_candidates(
            root, config, {rule_path: digest(rules)}
        )
        report = evaluate(
            "synthetic-deprecated-drc-function-reachability",
            coach(NetlistContract(components={}, nets={})),
            DesignLintPolicy(),
            pcb_dru_rule_candidates=candidates,
        )
        return {finding.rule_id for finding in report.findings}
