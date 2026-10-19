"""Synthetic source-bound checks for custom DRC exclusion severities."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import NetlistContract, ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_dru_rule_review import excluded_custom_drc_rule_candidates
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-severity-exclusions"
RULE_ID = "pcb.custom_drc_rule_excluded"
RULES_RELATIVE = "projects/controller.kicad_dru"


def _project(
    tmp_path: Path,
    fixture: str = "fault.kicad_dru",
    kicad_version: str = "10.0.5",
):
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
            kicad_version=kicad_version,
        ),
    )
    return root, rules, config


def _scan(root: Path, rules: Path, config: ProjectConfig):
    return excluded_custom_drc_rule_candidates(root, config, {RULES_RELATIVE: digest(rules)})


def test_exclusion_severity_creates_a_source_bound_review_candidate(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)

    candidates = _scan(root, rules, config)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{RULES_RELATIVE}#rule[2] SyntheticExcludedClearance"
    assert "excluding its matching violations is intentional" in candidate.message
    assert candidate.evidence == {
        "source_path": (RULES_RELATIVE,),
        "source_sha256": (digest(rules),),
        "kicad_version": ("10.0.5",),
        "rule_name": ("SyntheticExcludedClearance",),
        "rule_ordinal": ("2",),
        "severity": ("exclusion",),
    }


def test_error_warning_and_ignore_severities_are_valid_controls(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path, "control.kicad_dru")

    assert _scan(root, rules, config) == ()


@pytest.mark.parametrize("version", ("9.0.7", "11.0.0"))
def test_unreviewed_kicad_major_versions_are_out_of_scope(tmp_path: Path, version: str) -> None:
    root, rules, config = _project(tmp_path, kicad_version=version)

    assert _scan(root, rules, config) == ()


def test_unsupported_custom_rule_file_version_fails_closed(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    rules.write_text(
        rules.read_text(encoding="utf-8").replace("(version 1)", "(version 2)"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="version 1"):
        excluded_custom_drc_rule_candidates(root, config, {RULES_RELATIVE: digest(rules)})


def test_source_hash_is_required_and_stale_rule_bytes_fail_closed(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)

    with pytest.raises(ValueError, match="outside source-bound"):
        excluded_custom_drc_rule_candidates(root, config, {})

    stale_hash = digest(rules)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        excluded_custom_drc_rule_candidates(root, config, {RULES_RELATIVE: stale_hash})


def test_scan_is_deterministic_and_appended_warning_stays_quiet(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)

    first = _scan(root, rules, config)
    assert _scan(root, rules, config) == first
    rules.write_text(
        rules.read_text(encoding="utf-8")
        + '\n(rule "SyntheticLaterWarning"\n'
        + "  (condition \"A.NetName == 'SYNTHETIC_NET'\")\n"
        + "  (severity warning)\n"
        + "  (constraint track_width (min 0.25mm)))\n",
        encoding="utf-8",
    )

    after_warning = _scan(root, rules, config)
    assert len(after_warning) == 1
    assert after_warning[0].subject == first[0].subject


def test_exclusion_review_uses_standard_default_review_policy(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    candidate = _scan(root, rules, config)[0]
    report = evaluate(
        "synthetic-dru-exclusion",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(),
        pcb_dru_rule_candidates=(candidate,),
    )

    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"
