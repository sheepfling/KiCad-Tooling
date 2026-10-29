"""Source-bound review of custom DRC text-variable substitution."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, fingerprint
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import NetlistContract, ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_dru_rule_review import (
    excluded_custom_drc_rule_candidates,
    ignored_custom_drc_rule_candidates,
    text_variable_custom_drc_rule_candidates,
)
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE_ID = "pcb.custom_drc_text_variable_review"
RELATIVE = "projects/controller.kicad_dru"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-text-variable"


def _project(tmp_path: Path) -> tuple[Path, Path, ProjectConfig]:
    root = tmp_path / "repository"
    project = root / "projects/controller.kicad_pro"
    project.parent.mkdir(parents=True)
    project.write_text("{}", encoding="utf-8")
    rules = root / RELATIVE
    rules.write_bytes((FIXTURES / "variable-severity.kicad_dru").read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB, project="projects/controller.kicad_pro", kicad_version="10.0.5"
        ),
    )
    return root, rules, config


def _scan(root: Path, rules: Path, config: ProjectConfig):
    return text_variable_custom_drc_rule_candidates(root, config, {RELATIVE: digest(rules)})


def test_variable_severity_is_reviewed_without_an_authored_map(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    (candidate,) = _scan(root, rules, config)
    assert candidate.rule_id == RULE_ID
    assert candidate.evidence == {
        "source_path": (RELATIVE,),
        "source_sha256": (digest(rules),),
        "kicad_version": ("10.0.5",),
    }
    assert "does not evaluate" in candidate.message
    assert ignored_custom_drc_rule_candidates(root, config, {RELATIVE: digest(rules)}) == ()
    assert excluded_custom_drc_rule_candidates(root, config, {RELATIVE: digest(rules)}) == ()


@pytest.mark.parametrize(
    "source",
    (
        '(version 1)\n(rule "Value" (constraint track_width (min ${WIDTH})))\n',
        '(version 1)\n(rule "Condition" (condition "A.NetName == \'${NET}\'") (constraint edge_clearance (min 1mm)))\n',
        "(version 1)\n${EXTRA_RULE}\n",
        "(version 1)\n# substitution in a comment: ${NOTE}\n",
    ),
)
def test_other_substitution_sites_are_reviewed_without_assuming_their_value(
    tmp_path: Path, source: str
) -> None:
    root, rules, config = _project(tmp_path)
    rules.write_text(source, encoding="utf-8")
    assert len(_scan(root, rules, config)) == 1
    assert ignored_custom_drc_rule_candidates(root, config, {RELATIVE: digest(rules)}) == ()
    assert excluded_custom_drc_rule_candidates(root, config, {RELATIVE: digest(rules)}) == ()


def test_unparseable_raw_substitution_does_not_suppress_parser_errors(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    rules.write_text(
        '(version 1)\n(rule "Clause" ${EXTRA_CLAUSE} (constraint edge_clearance (min 1mm)))\n',
        encoding="utf-8",
    )
    assert len(_scan(root, rules, config)) == 1
    for scan in (ignored_custom_drc_rule_candidates, excluded_custom_drc_rule_candidates):
        with pytest.raises(ValueError, match="Malformed named rule"):
            scan(root, config, {RELATIVE: digest(rules)})


def test_no_substitution_and_absent_rules_are_quiet(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    rules.write_bytes((FIXTURES / "control.kicad_dru").read_bytes())
    assert _scan(root, rules, config) == ()
    rules.unlink()
    assert text_variable_custom_drc_rule_candidates(root, config, {}) == ()


def test_source_hash_and_version_boundaries(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        text_variable_custom_drc_rule_candidates(root, config, {})
    stale = digest(rules)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        text_variable_custom_drc_rule_candidates(root, config, {RELATIVE: stale})
    other = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=config.project, kicad_version="9.0.0"),
    )
    assert text_variable_custom_drc_rule_candidates(root, other, {}) == ()
    rules.write_text(
        '(version 1)\n(rule "synthetic" ${CLAUSE} (constraint edge_clearance (min 1mm)))\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Malformed named rule"):
        ignored_custom_drc_rule_candidates(root, other, {RELATIVE: digest(rules)})


def test_substitution_is_deterministic_and_changes_with_source(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    first = _scan(root, rules, config)
    assert _scan(root, rules, config) == first
    assert fingerprint(_scan(root, rules, config)[0]) == fingerprint(first[0])
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    second = _scan(root, rules, config)
    assert second[0].subject == first[0].subject
    assert second[0].evidence["source_sha256"] != first[0].evidence["source_sha256"]
    assert fingerprint(second[0]) != fingerprint(first[0])


def test_project_policy_can_review_block_disable_or_ignore(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    (candidate,) = _scan(root, rules, config)
    observed = coach(NetlistContract(components={}, nets={}))

    def report(policy: DesignLintPolicy):
        return evaluate("synthetic-dru", observed, policy, pcb_dru_rule_candidates=(candidate,))

    default = report(DesignLintPolicy())
    finding = next(item for item in default.findings if item.rule_id == RULE_ID)
    assert default.status == "REVIEW" and finding.mode == "review" and finding.disposition == "OPEN"
    blocked = report(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID, mode="block", reason="Project requires review"
                ),
            )
        )
    )
    assert blocked.status == "FAIL"
    disabled = report(
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Reviewed policy"),)
        )
    )
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    ignored = report(
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID, fingerprint=finding.fingerprint, reason="Reviewed substitution"
                ),
            )
        )
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )
