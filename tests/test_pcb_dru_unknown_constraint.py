"""Source-bound review of unknown custom PCB DRC constraint names."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, fingerprint
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_pcb_dru_unknown_constraint_evidence import (
    PcbDruUnknownConstraintCandidate,
)
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_dru_constraint_type_registry import (
    KICAD_10_0_CUSTOM_DRC_CONSTRAINT_TYPES,
)
from kicad_tooling.hwrepo.pcb_dru_unknown_constraint_review import (
    unknown_custom_drc_constraint_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]
RULE_ID = "pcb.custom_drc_unknown_constraint_type"
RULES = "projects/controller.kicad_dru"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-unknown-constraint"


def _project(tmp_path: Path, fixture: str) -> tuple[Path, Path, ProjectConfig]:
    root = tmp_path / "repository"
    (root / "projects").mkdir(parents=True)
    (root / "projects/controller.kicad_pro").write_text("{}", encoding="utf-8")
    rules = root / RULES
    rules.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project="projects/controller.kicad_pro",
            kicad_version="10.0.8",
        ),
    )
    return root, rules, config


def _scan(root: Path, rules: Path, config: ProjectConfig):
    return unknown_custom_drc_constraint_candidates(
        root,
        config,
        {RULES: digest(rules)},
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_misspelled_constraint_requests_source_bound_review(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "fault-misspelled-track-width.kicad_dru")

    (candidate,) = _scan(root, rules, config)

    assert isinstance(candidate, PcbDruUnknownConstraintCandidate)
    assert candidate.subject == f"{RULES}#rule[1] MisspelledTrackWidth/constraint[1]"
    assert candidate.evidence["source_sha256"] == (digest(rules),)
    assert candidate.evidence["kicad_version"] == ("10.0.8",)
    assert candidate.evidence["constraint_type"] == ("track_wdith",)
    assert "does not establish a board defect" in candidate.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_documented_and_legacy_constraint_names_stay_quiet(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "control-track-width.kicad_dru")

    assert "track_width" in KICAD_10_0_CUSTOM_DRC_CONSTRAINT_TYPES
    assert "mechanical_clearance" in KICAD_10_0_CUSTOM_DRC_CONSTRAINT_TYPES
    assert _scan(root, rules, config) == ()
    legacy_root, legacy_rules, legacy_config = _project(
        tmp_path / "legacy",
        "control-legacy-clearance-alias.kicad_dru",
    )
    assert _scan(legacy_root, legacy_rules, legacy_config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unresolved_text_variables_and_out_of_scope_versions_are_quiet(
    tmp_path: Path,
) -> None:
    root, rules, config = _project(tmp_path, "fault-misspelled-track-width.kicad_dru")
    rules.write_text(rules.read_text(encoding="utf-8").replace("track_wdith", "${Type}"))
    assert (
        unknown_custom_drc_constraint_candidates(
            root,
            config,
            {RULES: digest(rules)},
        )
        == ()
    )
    rules.write_bytes((FIXTURES / "fault-misspelled-track-width.kicad_dru").read_bytes())
    config.kicad_version = "10.1.0"
    assert (
        unknown_custom_drc_constraint_candidates(
            root,
            config,
            {RULES: digest(rules)},
        )
        == ()
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_fingerprint_and_source_freshness_are_exact(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "fault-misspelled-track-width.kicad_dru")
    candidates = _scan(root, rules, config)
    assert _scan(root, rules, config) == candidates
    (candidate,) = candidates
    report = evaluate(
        "synthetic-unknown-custom-drc-constraint",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(),
        pcb_dru_rule_candidates=candidates,
    )
    assert report.status == "REVIEW"
    assert sum(item.rule_id == RULE_ID for item in report.findings) == 1

    blocked = evaluate(
        "synthetic-unknown-custom-drc-constraint",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Required"),)
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert blocked.status == "FAIL"

    off = evaluate(
        "synthetic-unknown-custom-drc-constraint",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Reviewed"),)
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert all(item.disposition == "RULE_OFF" for item in off.findings if item.rule_id == RULE_ID)

    ignored = evaluate(
        "synthetic-unknown-custom-drc-constraint",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint(candidate),
                    reason="Constraint spelling reviewed",
                ),
            )
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert all(
        item.disposition == "IGNORED" for item in ignored.findings if item.rule_id == RULE_ID
    )
    with pytest.raises(ValueError, match="differ from source-bound"):
        unknown_custom_drc_constraint_candidates(root, config, {RULES: "0" * 64})
