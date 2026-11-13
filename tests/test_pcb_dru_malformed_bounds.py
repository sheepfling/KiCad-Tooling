"""Source-bound review of malformed custom PCB DRC constraint bounds."""

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
from kicad_tooling.hwrepo.design_lint_pcb_dru_malformed_bounds_evidence import (
    PcbDruMalformedBoundsCandidate,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_dru_malformed_bounds_review import (
    custom_drc_malformed_bound_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]
RULE_ID = "pcb.custom_drc_malformed_constraint_bounds"
RULES = "projects/controller.kicad_dru"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-malformed-bounds"
FAULTS = {
    "fault-repeated-minimum.kicad_dru": "Repeated min bound",
    "fault-invalid-length.kicad_dru": "Unsupported native DRC length literal",
    "fault-unsupported-clause.kicad_dru": "Unsupported bound expression",
    "fault-empty-constraint.kicad_dru": "no explicit min/max bound",
}


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
) -> tuple[PcbDruMalformedBoundsCandidate, ...]:
    return custom_drc_malformed_bound_candidates(
        root,
        config,
        {RULES: expected_hash or digest(rules)},
    )


@pytest.mark.parametrize(("fixture", "issue"), tuple(FAULTS.items()))
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unparseable_bounds_request_source_bound_review(
    tmp_path: Path,
    fixture: str,
    issue: str,
) -> None:
    root, rules, config = _project(tmp_path, fixture)
    (candidate,) = _scan(root, rules, config)

    assert isinstance(candidate, PcbDruMalformedBoundsCandidate)
    assert candidate.subject.startswith(f"{RULES}#rule[1]")
    assert candidate.evidence["source_sha256"] == (digest(rules),)
    assert candidate.evidence["kicad_version"] == ("10.0.8",)
    assert candidate.evidence["constraint_name"] == ("track_width",)
    assert issue in candidate.evidence["parser_issue"][0]
    assert "does not establish a board defect" in candidate.message


@pytest.mark.parametrize(
    "fixture",
    ("control-valid-range.kicad_dru", "control-one-sided.kicad_dru"),
)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_supported_bound_forms_are_quiet(tmp_path: Path, fixture: str) -> None:
    root, rules, config = _project(tmp_path, fixture)

    (constraint,) = native_constraints(rules.read_text(encoding="utf-8"))
    assert constraint.bounds_issue is None
    assert _scan(root, rules, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_text_variables_and_layer_only_issues_stay_out_of_bound_review(
    tmp_path: Path,
) -> None:
    root, rules, config = _project(tmp_path, "control-text-variable.kicad_dru")

    assert _scan(root, rules, config) == ()
    constraint = native_constraints(
        '(version 1) (rule "LayerOnly" (condition "A.Type == \'Track\'") '
        '(layer "F.Cu") (layer "B.Cu") (constraint track_width (min 0.1mm)))'
    )[0]
    assert constraint.issue is not None
    assert constraint.bounds_issue is None
    constraint_with_two_layer_clauses = native_constraints(
        '(version 1) (rule "LayerAndBounds" (condition "A.Type == \'Track\'") '
        '(layer "F.Cu") (layer "B.Cu") (constraint track_width))'
    )[0]
    assert constraint_with_two_layer_clauses.issue is not None
    assert "no explicit min/max bound" in (constraint_with_two_layer_clauses.bounds_issue or "")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_scope_policy_and_freshness_are_exact(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "fault-repeated-minimum.kicad_dru")
    candidates = _scan(root, rules, config)
    assert _scan(root, rules, config) == candidates
    (candidate,) = candidates

    report = evaluate(
        "synthetic-malformed-custom-drc-bounds",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(),
        pcb_dru_rule_candidates=candidates,
    )
    assert report.status == "REVIEW"
    assert sum(item.rule_id == RULE_ID for item in report.findings) == 1

    blocked = evaluate(
        "synthetic-malformed-custom-drc-bounds",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Review"),)
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert blocked.status == "FAIL"

    off = evaluate(
        "synthetic-malformed-custom-drc-bounds",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Reviewed"),)
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert all(item.disposition == "RULE_OFF" for item in off.findings if item.rule_id == RULE_ID)

    ignored = evaluate(
        "synthetic-malformed-custom-drc-bounds",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint(candidate),
                    reason="Reviewed",
                ),
            )
        ),
        pcb_dru_rule_candidates=candidates,
    )
    finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert finding.disposition == "IGNORED"

    unsupported = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=config.project, kicad_version="9.0.0"),
    )
    non_pcb = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.SCHEMATIC,
            project=config.project,
            kicad_version="10.0.8",
        ),
    )
    assert custom_drc_malformed_bound_candidates(root, unsupported, {}) == ()
    assert custom_drc_malformed_bound_candidates(root, non_pcb, {}) == ()

    with pytest.raises(ValueError, match="outside source-bound"):
        custom_drc_malformed_bound_candidates(root, config, {})
    original_hash = digest(rules)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, rules, config, expected_hash=original_hash)
