"""Source-bound review of contradictory custom PCB DRC bounds."""

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
from kicad_tooling.hwrepo.design_lint_pcb_dru_contradictory_bounds_evidence import (
    PcbDruContradictoryBoundsCandidate,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_dru_contradictory_bounds_review import (
    contradictory_custom_drc_constraint_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]
RULE_ID = "pcb.custom_drc_contradictory_constraint_bounds"
RULES = "projects/controller.kicad_dru"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-contradictory-bounds"


def _project(tmp_path: Path, fixture: str) -> tuple[Path, Path, ProjectConfig]:
    root = tmp_path / "repository"
    project_path = root / "projects/controller.kicad_pro"
    rules_path = root / RULES
    project_path.parent.mkdir(parents=True)
    project_path.write_text("{}", encoding="utf-8")
    rules_path.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project="projects/controller.kicad_pro",
            kicad_version="10.0.8",
        ),
    )
    return root, rules_path, config


def _scan(
    root: Path,
    rules: Path,
    config: ProjectConfig,
    *,
    expected_hash: str | None = None,
) -> tuple[PcbDruContradictoryBoundsCandidate, ...]:
    return contradictory_custom_drc_constraint_candidates(
        root,
        config,
        {RULES: expected_hash or digest(rules)},
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_minimum_above_maximum_requests_one_source_bound_review_per_constraint(
    tmp_path: Path,
) -> None:
    root, rules, config = _project(tmp_path, "fault-min-exceeds-max.kicad_dru")
    (candidate,) = _scan(root, rules, config)

    assert isinstance(candidate, PcbDruContradictoryBoundsCandidate)
    assert candidate.subject == f"{RULES}#rule[1] SyntheticWidthRange/track_width"
    assert candidate.evidence == {
        "source_path": (RULES,),
        "source_sha256": (digest(rules),),
        "kicad_version": ("10.0.8",),
        "rule_name": ("SyntheticWidthRange",),
        "rule_ordinal": ("1",),
        "constraint_name": ("track_width",),
        "minimum_nm": ("300000",),
        "maximum_nm": ("100000",),
    }
    assert "review the rule's intended bounds" in candidate.message
    assert "does not establish a board defect" in candidate.message


@pytest.mark.parametrize(
    "fixture",
    (
        "control-valid-range.kicad_dru",
        "control-equal-bounds.kicad_dru",
        "control-one-sided-bounds.kicad_dru",
        "control-repeated-bound.kicad_dru",
        "control-text-variable.kicad_dru",
    ),
)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_valid_or_ambiguous_bounds_stay_quiet(tmp_path: Path, fixture: str) -> None:
    root, rules, config = _project(tmp_path, fixture)

    assert _scan(root, rules, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_supported_scope_source_binding_and_review_policy_are_exact(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "fault-min-exceeds-max.kicad_dru")
    candidates = _scan(root, rules, config)
    assert _scan(root, rules, config) == candidates
    (candidate,) = candidates

    report = evaluate(
        "synthetic-contradictory-custom-drc-bounds",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(),
        pcb_dru_rule_candidates=candidates,
    )
    assert report.status == "REVIEW"
    assert sum(item.rule_id == RULE_ID for item in report.findings) == 1

    blocked = evaluate(
        "synthetic-contradictory-custom-drc-bounds",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Review"),)
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert blocked.status == "FAIL"

    off = evaluate(
        "synthetic-contradictory-custom-drc-bounds",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Reviewed"),)
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert all(item.disposition == "RULE_OFF" for item in off.findings if item.rule_id == RULE_ID)

    ignored = evaluate(
        "synthetic-contradictory-custom-drc-bounds",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID, fingerprint=fingerprint(candidate), reason="Reviewed"
                ),
            )
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )

    unsupported = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=config.project, kicad_version="9.0.0"),
    )
    non_pcb = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.SCHEMATIC, project=config.project, kicad_version="10.0.8"),
    )
    assert contradictory_custom_drc_constraint_candidates(root, unsupported, {}) == ()
    assert contradictory_custom_drc_constraint_candidates(root, non_pcb, {}) == ()

    with pytest.raises(ValueError, match="outside source-bound"):
        contradictory_custom_drc_constraint_candidates(root, config, {})
    original_hash = digest(rules)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, rules, config, expected_hash=original_hash)
