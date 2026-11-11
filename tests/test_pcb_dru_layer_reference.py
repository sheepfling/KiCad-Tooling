"""Source-bound review of custom DRC layer names against a saved board."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, fingerprint
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_pcb_dru_layer_evidence import PcbDruLayerCandidate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_dru_layer_review import custom_drc_layer_reference_candidates
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]
RULE_ID = "pcb.custom_drc_layer_reference"
RULES = "projects/controller.kicad_dru"
BOARD = "projects/controller.kicad_pcb"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-layer-reference"
PROBE_BOARD = (
    Path(__file__).parents[1]
    / "kicad_tooling/hwrepo/fixtures/pcb-dru-rule-compilation-probe.kicad_pcb"
)


def _project(tmp_path: Path, fixture: str) -> tuple[Path, Path, Path, ProjectConfig]:
    root = tmp_path / "repository"
    project_path = root / "projects/controller.kicad_pro"
    rules_path = root / RULES
    board_path = root / BOARD
    project_path.parent.mkdir(parents=True)
    project_path.write_text("{}", encoding="utf-8")
    rules_path.write_bytes((FIXTURES / fixture).read_bytes())
    board_path.write_bytes(PROBE_BOARD.read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project="projects/controller.kicad_pro",
            kicad_version="10.0.8",
        ),
    )
    return root, rules_path, board_path, config


def _scan(root: Path, rules: Path, board: Path, config: ProjectConfig):
    return custom_drc_layer_reference_candidates(
        root,
        config,
        {RULES: digest(rules), BOARD: digest(board)},
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_display_aliases_in_layer_clauses_and_conditions_request_review(
    tmp_path: Path,
) -> None:
    root, rules, board, config = _project(tmp_path, "fault-display-alias.kicad_dru")
    findings = _scan(root, rules, board, config)

    assert len(findings) == 3
    assert all(isinstance(item, PcbDruLayerCandidate) for item in findings)
    assert {item.source_evidence.rule_name for item in findings} == {
        "DirectDisplayLayer",
        "ConditionDisplayLayer",
        "ExistsOnLayerDisplay",
    }
    assert {item.evidence["issue_kinds"] for item in findings} == {("display_alias",)}
    assert {item.evidence["canonical_layers"] for item in findings} == {
        ("F.SilkS",),
        ("B.SilkS",),
    }
    assert all("does not establish" in item.message for item in findings)


@pytest.mark.parametrize(
    ("fixture", "expected_kind", "expected_layer"),
    (
        ("fault-unknown-layer.kicad_dru", "unknown_layer", "F.Unknown"),
        ("fault-absent-stackup-layer.kicad_dru", "layer_not_in_board", "In5.Cu"),
    ),
)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unknown_and_stackup_absent_layers_are_distinguished(
    tmp_path: Path, fixture: str, expected_kind: str, expected_layer: str
) -> None:
    root, rules, board, config = _project(tmp_path, fixture)
    (candidate,) = _scan(root, rules, board, config)

    assert isinstance(candidate, PcbDruLayerCandidate)
    assert candidate.evidence["issue_kinds"] == (expected_kind,)
    assert candidate.evidence["layer_names"] == (expected_layer,)
    assert candidate.evidence["source_sha256"] == (digest(rules),)
    assert candidate.evidence["board_sha256"] == (digest(board),)
    assert candidate.evidence["kicad_version"] == ("10.0.8",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_canonical_names_and_alias_text_in_comments_are_quiet(tmp_path: Path) -> None:
    root, rules, board, config = _project(tmp_path, "control-canonical-layers.kicad_dru")
    rules.write_text(
        rules.read_text(encoding="utf-8") + "\n# F.Silkscreen and In5.Cu are comment text\n",
        encoding="utf-8",
    )

    assert _scan(root, rules, board, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_text_variables_defer_to_the_existing_substitution_review(tmp_path: Path) -> None:
    root, rules, board, config = _project(tmp_path, "control-text-variable.kicad_dru")

    assert _scan(root, rules, board, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_board_saved_display_alias_is_discovered_from_its_layer_table(tmp_path: Path) -> None:
    root, rules, board, config = _project(tmp_path, "control-canonical-layers.kicad_dru")
    board.write_text(
        board.read_text(encoding="utf-8").replace(
            '(37 "F.SilkS" user)', '(37 "F.SilkS" user "Synthetic.Silkscreen")'
        ),
        encoding="utf-8",
    )
    rules.write_text(
        '(version 1)\n(rule "BoardAlias" (layer "Synthetic.Silkscreen") '
        "(severity error) (constraint track_width (min 0.5mm)))\n",
        encoding="utf-8",
    )
    (candidate,) = _scan(root, rules, board, config)

    assert candidate.evidence["issue_kinds"] == ("display_alias",)
    assert candidate.evidence["canonical_layers"] == ("F.SilkS",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_hashes_fingerprints_and_project_policy_are_exact(tmp_path: Path) -> None:
    root, rules, board, config = _project(tmp_path, "fault-unknown-layer.kicad_dru")
    (candidate,) = _scan(root, rules, board, config)
    assert _scan(root, rules, board, config) == (candidate,)
    assert isinstance(candidate, PcbDruLayerCandidate)
    observed = coach(NetlistContract(components={}, nets={}))

    def report(policy: DesignLintPolicy):
        return evaluate(
            "synthetic-layer-review", observed, policy, pcb_dru_rule_candidates=(candidate,)
        )

    review = report(DesignLintPolicy())
    finding = next(item for item in review.findings if item.rule_id == RULE_ID)
    assert review.status == "REVIEW" and finding.disposition == "OPEN"
    blocked = report(
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Required"),)
        )
    )
    assert blocked.status == "FAIL"
    off = report(
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Reviewed"),)
        )
    )
    assert next(item for item in off.findings if item.rule_id == RULE_ID).disposition == "RULE_OFF"
    ignored = report(
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID, fingerprint=fingerprint(candidate), reason="Reviewed"
                ),
            )
        )
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )

    board.write_text(board.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    (changed_board,) = _scan(root, rules, board, config)
    assert changed_board.evidence["board_sha256"] != candidate.evidence["board_sha256"]
    assert fingerprint(changed_board) != fingerprint(candidate)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    (changed_rule,) = _scan(root, rules, board, config)
    assert changed_rule.evidence["source_sha256"] != candidate.evidence["source_sha256"]
    assert fingerprint(changed_rule) != fingerprint(changed_board)
    with pytest.raises(ValueError, match="outside source-bound"):
        custom_drc_layer_reference_candidates(root, config, {})
    with pytest.raises(ValueError, match="board source is outside source-bound"):
        custom_drc_layer_reference_candidates(root, config, {RULES: digest(rules)})
    with pytest.raises(ValueError, match="board source differs from source-bound"):
        custom_drc_layer_reference_candidates(root, config, {RULES: digest(rules), BOARD: "0" * 64})
    unsupported = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=config.project, kicad_version="9.0.0"),
    )
    assert custom_drc_layer_reference_candidates(root, unsupported, {}) == ()
    non_pcb = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.SCHEMATIC, project=config.project, kicad_version="10.0.8"),
    )
    assert custom_drc_layer_reference_candidates(root, non_pcb, {}) == ()
