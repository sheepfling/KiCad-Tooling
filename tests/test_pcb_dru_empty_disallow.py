"""Source-bound review of empty custom DRC disallow clauses."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, fingerprint
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_pcb_dru_empty_disallow_evidence import (
    PcbDruEmptyDisallowCandidate,
)
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_dru_empty_disallow_review import (
    empty_custom_drc_disallow_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]
RULE_ID = "pcb.custom_drc_empty_disallow_clause"
RULES = "projects/controller.kicad_dru"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-empty-disallow"


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
    return empty_custom_drc_disallow_candidates(root, config, {RULES: digest(rules)})


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_empty_disallow_clauses_request_exact_source_bound_reviews(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "fault-empty-object-list.kicad_dru")

    candidates = _scan(root, rules, config)

    assert len(candidates) == 2
    assert all(isinstance(candidate, PcbDruEmptyDisallowCandidate) for candidate in candidates)
    assert tuple(candidate.subject for candidate in candidates) == (
        f"{RULES}#rule[1] EmptyDisallow/constraint[1]",
        f"{RULES}#rule[1] EmptyDisallow/constraint[3]",
    )
    assert all(candidate.evidence["source_sha256"] == (digest(rules),) for candidate in candidates)
    assert all(candidate.evidence["kicad_version"] == ("10.0.8",) for candidate in candidates)
    assert all("does not establish a board defect" in candidate.message for candidate in candidates)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_one_or_more_documented_disallow_objects_stay_quiet(tmp_path: Path) -> None:
    for fixture in ("control-one-object.kicad_dru", "control-multiple-objects.kicad_dru"):
        root, rules, config = _project(tmp_path / fixture.split(".")[0], fixture)
        assert _scan(root, rules, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_text_variables_and_out_of_scope_versions_stay_deferred(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "fault-empty-object-list.kicad_dru")
    rules.write_text(
        rules.read_text(encoding="utf-8").replace(
            "(constraint disallow)", "(constraint disallow ${Types})"
        )
    )
    assert _scan(root, rules, config) == ()

    rules.write_bytes((FIXTURES / "fault-empty-object-list.kicad_dru").read_bytes())
    config.kicad_version = "10.1.0"
    assert _scan(root, rules, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_fingerprint_repeatability_and_source_freshness_are_exact(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "fault-empty-object-list.kicad_dru")
    candidates = _scan(root, rules, config)
    assert _scan(root, rules, config) == candidates
    report = evaluate(
        "synthetic-empty-disallow",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(),
        pcb_dru_rule_candidates=candidates,
    )
    assert report.status == "REVIEW"
    assert sum(item.rule_id == RULE_ID for item in report.findings) == 2

    blocked = evaluate(
        "synthetic-empty-disallow",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Required"),)
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert blocked.status == "FAIL"

    off = evaluate(
        "synthetic-empty-disallow",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Reviewed"),)
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert all(item.disposition == "RULE_OFF" for item in off.findings if item.rule_id == RULE_ID)

    ignored = evaluate(
        "synthetic-empty-disallow",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            ignores=tuple(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint(item),
                    reason="Empty clause reviewed",
                )
                for item in candidates
            )
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert all(
        item.disposition == "IGNORED" for item in ignored.findings if item.rule_id == RULE_ID
    )
    with pytest.raises(ValueError, match="differ from source-bound"):
        empty_custom_drc_disallow_candidates(root, config, {RULES: "0" * 64})
