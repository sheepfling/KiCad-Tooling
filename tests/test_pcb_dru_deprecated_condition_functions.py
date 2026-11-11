"""Review deprecated custom DRC condition functions from source evidence."""

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
from kicad_tooling.hwrepo.design_lint_pcb_dru_deprecated_function_evidence import (
    PcbDruDeprecatedFunctionCandidate,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_dru_deprecated_function_review import (
    custom_drc_deprecated_condition_function_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]
RULE_ID = "pcb.custom_drc_deprecated_condition_function"
RULES = "projects/controller.kicad_dru"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-deprecated-condition-functions"


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
):
    return custom_drc_deprecated_condition_function_candidates(
        root, config, {RULES: expected_hash or digest(rules)}
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_deprecated_calls_are_reported_once_per_named_rule(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "fault.kicad_dru")
    first, second = _scan(root, rules, config)

    assert isinstance(first, PcbDruDeprecatedFunctionCandidate)
    assert first.evidence["rule_name"] == ("DeprecatedQueries",)
    assert first.evidence["rule_ordinal"] == ("1",)
    assert first.evidence["deprecated_functions"] == (
        "insideArea",
        "insideFrontCourtyard",
        "memberOf",
    )
    assert first.evidence["recommended_functions"] == (
        "intersectsArea",
        "intersectsFrontCourtyard",
        "memberOfGroup",
    )
    assert second.evidence["deprecated_functions"] == (
        "insideCourtyard",
        "insideBackCourtyard",
    )
    assert first.evidence["source_sha256"] == second.evidence["source_sha256"] == (digest(rules),)
    assert "preserves the intended match" in first.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_current_functions_strings_comments_and_no_condition_are_quiet(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "control.kicad_dru")

    assert _scan(root, rules, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_text_variable_sources_are_deferred_and_exact_version_is_required(
    tmp_path: Path,
) -> None:
    root, rules, config = _project(tmp_path, "fault.kicad_dru")
    rules.write_text(rules.read_text(encoding="utf-8") + "\n# ${RULE_MODE}\n", encoding="utf-8")
    assert _scan(root, rules, config) == ()

    rules.write_bytes((FIXTURES / "fault.kicad_dru").read_bytes())
    unsupported = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=config.project, kicad_version="9.0.0"),
    )
    non_pcb = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.SCHEMATIC, project=config.project, kicad_version="10.0.8"),
    )
    assert custom_drc_deprecated_condition_function_candidates(root, unsupported, {}) == ()
    assert custom_drc_deprecated_condition_function_candidates(root, non_pcb, {}) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_binding_determinism_and_policy_are_exact(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "fault.kicad_dru")
    candidates = _scan(root, rules, config)
    assert _scan(root, rules, config) == candidates
    first = candidates[0]
    report = evaluate(
        "synthetic-deprecated-custom-drc-functions",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(),
        pcb_dru_rule_candidates=candidates,
    )
    assert report.status == "REVIEW"
    assert sum(item.rule_id == RULE_ID for item in report.findings) == 2

    blocked = evaluate(
        "synthetic-deprecated-custom-drc-functions",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Review"),)
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert blocked.status == "FAIL"
    off = evaluate(
        "synthetic-deprecated-custom-drc-functions",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Reviewed"),)
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert all(item.disposition == "RULE_OFF" for item in off.findings if item.rule_id == RULE_ID)
    ignored = evaluate(
        "synthetic-deprecated-custom-drc-functions",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID, fingerprint=fingerprint(first), reason="Reviewed"
                ),
            )
        ),
        pcb_dru_rule_candidates=candidates,
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )

    with pytest.raises(ValueError, match="outside source-bound"):
        custom_drc_deprecated_condition_function_candidates(root, config, {})
    original_hash = digest(rules)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, rules, config, expected_hash=original_hash)
