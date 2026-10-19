"""Synthetic source-bound checks for explicitly ignored custom DRC rules."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import NetlistContract, ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_dru_rule_review import ignored_custom_drc_rule_candidates
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-ignored-rules"
RULE_ID = "pcb.custom_drc_rule_ignored"
RULES_RELATIVE = "projects/controller.kicad_dru"


def _project(tmp_path: Path, fixture: str = "fault.kicad_dru"):
    root = tmp_path / "repository"
    project = root / "projects/controller.kicad_pro"
    rules = root / RULES_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_text("{}", encoding="utf-8")
    rules.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project="projects/controller.kicad_pro",
            kicad_version="10.0.5",
        ),
    )
    return root, rules, config


def _scan(root: Path, rules: Path, config: ProjectConfig):
    return ignored_custom_drc_rule_candidates(root, config, {RULES_RELATIVE: digest(rules)})


def test_explicit_ignore_rule_creates_a_source_bound_review_candidate(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)

    candidates = _scan(root, rules, config)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{RULES_RELATIVE}#rule[1] SyntheticSuppressedWidth"
    assert "confirm that suppressing this rule is intentional" in candidate.message
    assert candidate.evidence == {
        "source_path": (RULES_RELATIVE,),
        "source_sha256": (digest(rules),),
        "kicad_version": ("10.0.5",),
        "rule_name": ("SyntheticSuppressedWidth",),
        "rule_ordinal": ("1",),
    }


def test_active_error_warning_and_exclusion_severities_are_valid_controls(
    tmp_path: Path,
) -> None:
    root, rules, config = _project(tmp_path, "control.kicad_dru")

    assert _scan(root, rules, config) == ()


def test_missing_rules_file_and_non_pcb_projects_are_out_of_scope(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    rules.unlink()

    assert ignored_custom_drc_rule_candidates(root, config, {}) == ()
    schematic = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.SCHEMATIC,
            project="projects/controller.kicad_pro",
            kicad_version="10.0.5",
        ),
    )
    rules.write_bytes((FIXTURES / "fault.kicad_dru").read_bytes())
    assert ignored_custom_drc_rule_candidates(root, schematic, {}) == ()


def test_source_hash_is_required_and_stale_rule_bytes_fail_closed(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)

    with pytest.raises(ValueError, match="outside source-bound"):
        ignored_custom_drc_rule_candidates(root, config, {})

    stale_hash = digest(rules)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        ignored_custom_drc_rule_candidates(root, config, {RULES_RELATIVE: stale_hash})


def test_linked_custom_rules_are_rejected(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    external = tmp_path / "external.kicad_dru"
    external.write_bytes(rules.read_bytes())
    rules.unlink()
    try:
        rules.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    with pytest.raises(ValueError, match="Linked repository path"):
        ignored_custom_drc_rule_candidates(root, config, {RULES_RELATIVE: digest(external)})


def test_scan_is_deterministic_and_an_appended_active_rule_stays_quiet(
    tmp_path: Path,
) -> None:
    root, rules, config = _project(tmp_path)

    first = _scan(root, rules, config)
    assert _scan(root, rules, config) == first
    rules.write_text(
        rules.read_text(encoding="utf-8")
        + '\n(rule "SyntheticLaterActive"\n'
        + "  (condition \"A.NetName == 'SYNTHETIC_NET'\")\n"
        + "  (severity error)\n"
        + "  (constraint track_width (min 0.25mm)))\n",
        encoding="utf-8",
    )
    after_active_rule = _scan(root, rules, config)

    assert len(after_active_rule) == 1
    assert after_active_rule[0].subject == first[0].subject


def test_custom_rule_findings_use_the_standard_project_dispositions(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    candidate = _scan(root, rules, config)[0]
    observed = coach(NetlistContract(components={}, nets={}))

    default = evaluate(
        "synthetic-dru",
        observed,
        DesignLintPolicy(),
        pcb_dru_rule_candidates=(candidate,),
    )
    default_finding = next(item for item in default.findings if item.rule_id == RULE_ID)
    assert default_finding.mode == "review"
    assert default_finding.disposition == "OPEN"

    blocked = evaluate(
        "synthetic-dru",
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires review of disabled custom rules",
                ),
            )
        ),
        pcb_dru_rule_candidates=(candidate,),
    )
    blocked_finding = next(item for item in blocked.findings if item.rule_id == RULE_ID)
    assert blocked_finding.mode == "block"
    assert blocked_finding.disposition == "OPEN"

    ignored = evaluate(
        "synthetic-dru",
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=default_finding.fingerprint,
                    reason="Synthetic project reviewed the intentionally disabled rule",
                ),
            )
        ),
        pcb_dru_rule_candidates=(candidate,),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"
    assert ignored_finding.reason == "Synthetic project reviewed the intentionally disabled rule"

    off = evaluate(
        "synthetic-dru",
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project disables this review prompt",
                ),
            )
        ),
        pcb_dru_rule_candidates=(candidate,),
    )
    off_finding = next(item for item in off.findings if item.rule_id == RULE_ID)
    assert off_finding.mode == "off"
    assert off_finding.disposition == "RULE_OFF"
