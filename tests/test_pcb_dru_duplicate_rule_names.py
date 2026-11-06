"""Source-bound review of duplicate custom PCB DRC rule names."""

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
from kicad_tooling.hwrepo.design_lint_pcb_dru_rule_name_evidence import (
    PcbDruDuplicateRuleNameCandidate,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_dru_rule_review import (
    custom_drc_duplicate_rule_name_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]
RULE_ID = "pcb.custom_drc_duplicate_rule_name"
RULES_RELATIVE = "projects/controller.kicad_dru"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-duplicate-rule-name"


def _project(
    tmp_path: Path,
    fixture: str = "fault-duplicate-names.kicad_dru",
    *,
    kind: ProjectKind = ProjectKind.PCB,
    kicad_version: str = "10.0.5",
) -> tuple[Path, Path, ProjectConfig]:
    root = tmp_path / "repository"
    project = root / "projects/controller.kicad_pro"
    rules = root / RULES_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_text("{}", encoding="utf-8")
    rules.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=kind,
            project="projects/controller.kicad_pro",
            kicad_version=kicad_version,
        ),
    )
    return root, rules, config


def _scan(root: Path, rules: Path, config: ProjectConfig) -> tuple[Candidate, ...]:
    return custom_drc_duplicate_rule_name_candidates(
        root,
        config,
        {RULES_RELATIVE: digest(rules)},
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_duplicate_rule_names_request_source_bound_review_per_exact_name(
    tmp_path: Path,
) -> None:
    root, rules, config = _project(tmp_path)

    (candidate,) = _scan(root, rules, config)

    assert isinstance(candidate, PcbDruDuplicateRuleNameCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == (f"{RULES_RELATIVE}#rules[1,2,3] SYNTHETIC_DUPLICATE_NAME")
    assert candidate.source_evidence.rule_name == "SYNTHETIC_DUPLICATE_NAME"
    assert candidate.source_evidence.rule_ordinals == (1, 2, 3)
    assert candidate.evidence == {
        "source_path": (RULES_RELATIVE,),
        "source_sha256": (digest(rules),),
        "kicad_version": ("10.0.5",),
        "rule_name": ("SYNTHETIC_DUPLICATE_NAME",),
        "rule_ordinals": ("1", "2", "3"),
    }
    assert "unique identifier" in candidate.message
    assert _scan(root, rules, config) == (candidate,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unique_names_case_variants_and_comments_are_quiet(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "control-unique-names.kicad_dru")

    assert _scan(root, rules, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_appending_unique_rule_preserves_duplicate_group_identity(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    (before,) = _scan(root, rules, config)
    assert isinstance(before, PcbDruDuplicateRuleNameCandidate)
    rules.write_text(
        rules.read_text(encoding="utf-8")
        + '(rule "SYNTHETIC_UNIQUE_LATER" (constraint edge_clearance (min 1mm)))\n',
        encoding="utf-8",
    )

    (after,) = _scan(root, rules, config)
    assert isinstance(after, PcbDruDuplicateRuleNameCandidate)

    assert after.subject == before.subject
    assert after.source_evidence.rule_ordinals == before.source_evidence.rule_ordinals
    assert after.evidence["source_sha256"] != before.evidence["source_sha256"]
    assert fingerprint(after) != fingerprint(before)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_exactly_ignore_duplicate_names(
    tmp_path: Path,
) -> None:
    root, rules, config = _project(tmp_path)
    (candidate,) = _scan(root, rules, config)
    observed = coach(NetlistContract(components={}, nets={}))

    def report(policy: DesignLintPolicy) -> DesignLintReport:
        return evaluate(
            "synthetic-dru-duplicate-name",
            observed,
            policy,
            pcb_dru_rule_candidates=(candidate,),
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
                    rule_id=RULE_ID,
                    fingerprint=fingerprint(candidate),
                    reason="Reviewed",
                ),
            )
        )
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


def test_hash_version_project_kind_and_variable_boundaries(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        custom_drc_duplicate_rule_name_candidates(root, config, {})
    stale = digest(rules)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        custom_drc_duplicate_rule_name_candidates(root, config, {RULES_RELATIVE: stale})

    rules.write_text(
        '(version 1)\n(rule "${RULE_NAME}" (constraint track_width (min 0.2mm)))\n',
        encoding="utf-8",
    )
    assert _scan(root, rules, config) == ()

    root, rules, schematic = _project(tmp_path / "schematic", kind=ProjectKind.SCHEMATIC)
    assert _scan(root, rules, schematic) == ()
    root, rules, older = _project(tmp_path / "older", kicad_version="9.0.7")
    assert _scan(root, rules, older) == ()
