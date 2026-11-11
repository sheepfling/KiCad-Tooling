"""Synthetic reachability input for custom DRC layer-reference review."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_dru_layer_review import custom_drc_layer_reference_candidates
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach


def custom_drc_layer_rule_ids() -> set[str]:
    """Reach the source-bound layer predicate from a minimal synthetic project."""
    rule_path = "projects/controller.kicad_dru"
    board_path = "projects/controller.kicad_pcb"
    with TemporaryDirectory(prefix="kicad-dru-layer-reachability-") as temporary:
        root = Path(temporary)
        project_sources = root / "projects"
        project_sources.mkdir()
        rules = root / rule_path
        board = root / board_path
        rules.write_text(
            "(version 1)\n"
            '(rule "SyntheticDisplayAlias" (layer "F.Silkscreen") '
            "(severity error) (constraint track_width (min 0.2mm)))\n",
            encoding="utf-8",
        )
        board.write_text(
            '(kicad_pcb (version 20241229) (generator "pcbnew") '
            '(layers (0 "F.Cu" signal) (31 "B.Cu" signal) (37 "F.SilkS" user)))\n',
            encoding="utf-8",
        )
        config = cast(
            ProjectConfig,
            SimpleNamespace(
                kind=ProjectKind.PCB,
                project="projects/controller.kicad_pro",
                kicad_version="10.0.8",
            ),
        )
        source_hashes = {rule_path: digest(rules), board_path: digest(board)}
        layer_candidates = custom_drc_layer_reference_candidates(root, config, source_hashes)
        observed = NetlistContract(components={}, nets={})
        report = evaluate(
            "synthetic-pcb-dru-layer-reachability",
            coach(observed),
            DesignLintPolicy(),
            pcb_dru_rule_candidates=layer_candidates,
        )
        return {finding.rule_id for finding in report.findings}
