"""Source-bound review of custom DRC rules with no direct constraints."""

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
from kicad_tooling.hwrepo.design_lint_pcb_dru_rule_candidate_evidence import (
    PcbDruRuleWithoutConstraintCandidate,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_dru_rule_review import (
    custom_drc_rule_without_constraint_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]
RULE_ID = "pcb.custom_drc_rule_without_constraint"
RELATIVE = "projects/controller.kicad_dru"
PROJECT = "projects/controller.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-rule-without-constraint"


def _project(
    tmp_path: Path,
    source: str | None = None,
    *,
    kind: ProjectKind = ProjectKind.PCB,
    kicad_version: str = "10.0.5",
) -> tuple[Path, Path, ProjectConfig]:
    root = tmp_path / "repository"
    project = root / PROJECT
    project.parent.mkdir(parents=True)
    project.write_text("{}", encoding="utf-8")
    rules = root / RELATIVE
    rules.write_text(
        source
        if source is not None
        else (FIXTURES / "fault-no-constraint.kicad_dru").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=kind,
            project=PROJECT,
            kicad_version=kicad_version,
        ),
    )
    return root, rules, config


def _scan(root: Path, rules: Path, config: ProjectConfig):
    return custom_drc_rule_without_constraint_candidates(root, config, {RELATIVE: digest(rules)})


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_without_direct_constraint_requests_source_bound_review(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    (candidate,) = _scan(root, rules, config)

    assert isinstance(candidate, PcbDruRuleWithoutConstraintCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{RELATIVE}#rule[1] SyntheticUnconstrained"
    assert candidate.evidence == {
        "source_path": (RELATIVE,),
        "source_sha256": (digest(rules),),
        "kicad_version": ("10.0.5",),
        "rule_name": ("SyntheticUnconstrained",),
        "rule_ordinal": ("1",),
        "constraint_count": ("0",),
    }
    assert "may be an inert declaration" in candidate.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rules_with_direct_constraints_are_quiet(tmp_path: Path) -> None:
    source = (FIXTURES / "control-active.kicad_dru").read_text(encoding="utf-8")
    source += "# a comment mentioning (constraint edge_clearance (min 1mm))\n"
    root, rules, config = _project(tmp_path, source)

    assert _scan(root, rules, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_text_variable_substitution_defers_to_the_variable_review(tmp_path: Path) -> None:
    source = (
        "(version 1)\n"
        '(rule "VariableConstraint" (condition "A.Type == \'Track\'") '
        "(severity error) ${CONSTRAINT})\n"
    )
    root, rules, config = _project(tmp_path, source)

    assert _scan(root, rules, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_source_change_updates_fingerprint(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    (first,) = _scan(root, rules, config)
    rules.write_text(
        rules.read_text(encoding="utf-8").replace("SyntheticUnconstrained", "SyntheticNoop"),
        encoding="utf-8",
    )
    (changed,) = _scan(root, rules, config)

    assert changed.subject != first.subject
    assert changed.evidence["source_sha256"] != first.evidence["source_sha256"]
    assert fingerprint(changed) != fingerprint(first)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_review_block_disable_or_exactly_ignore(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    (candidate,) = _scan(root, rules, config)
    observed = coach(NetlistContract(components={}, nets={}))

    def report(policy: DesignLintPolicy):
        return evaluate("synthetic-dru", observed, policy, pcb_dru_rule_candidates=(candidate,))

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


def test_non_pcb_old_versions_and_source_binding_boundaries(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        custom_drc_rule_without_constraint_candidates(root, config, {})
    stale = digest(rules)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        custom_drc_rule_without_constraint_candidates(root, config, {RELATIVE: stale})

    root, rules, schematic = _project(tmp_path / "schematic", kind=ProjectKind.SCHEMATIC)
    assert _scan(root, rules, schematic) == ()
    root, rules, old_version = _project(tmp_path / "old-version", kicad_version="9.0.0")
    assert _scan(root, rules, old_version) == ()
