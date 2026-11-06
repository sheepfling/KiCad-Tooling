"""Source-bound review of custom DRC rules with conflicting severities."""

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
    PcbDruConflictingSeveritiesCandidate,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_rules_with_conflicting_severities
from kicad_tooling.hwrepo.pcb_dru_rule_review import custom_drc_conflicting_severity_candidates
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]
RULE_ID = "pcb.custom_drc_conflicting_severities"
RULES_RELATIVE = "projects/controller.kicad_dru"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-conflicting-severities"
FAULT = (FIXTURES / "fault-multiple-severities.kicad_dru").read_text(encoding="utf-8")


def _project(
    tmp_path: Path,
    source: str = FAULT,
    *,
    kind: ProjectKind = ProjectKind.PCB,
    kicad_version: str = "10.0.5",
) -> tuple[Path, Path, ProjectConfig]:
    root = tmp_path / "repository"
    project = root / "projects/controller.kicad_pro"
    rules = root / RULES_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_text("{}", encoding="utf-8")
    rules.write_text(source, encoding="utf-8")
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
    return custom_drc_conflicting_severity_candidates(root, config, {RULES_RELATIVE: digest(rules)})


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_conflicting_direct_severities_request_source_bound_review(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)

    (candidate,) = _scan(root, rules, config)

    assert isinstance(candidate, PcbDruConflictingSeveritiesCandidate)
    assert candidate.subject == f"{RULES_RELATIVE}#rule[1] SyntheticTrackWidth"
    assert candidate.source_evidence.rule.severities == ("error", "warning")
    assert candidate.evidence == {
        "source_path": (RULES_RELATIVE,),
        "source_sha256": (digest(rules),),
        "kicad_version": ("10.0.5",),
        "rule_name": ("SyntheticTrackWidth",),
        "rule_ordinal": ("1",),
        "severities": ("error", "warning"),
    }
    assert "intended severity" in candidate.message
    assert _scan(root, rules, config) == (candidate,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_single_identical_and_invalid_severities_are_quiet(tmp_path: Path) -> None:
    sources = (
        '(version 1)\n(rule "One" (severity error) (constraint track_width (min 0.2mm)))\n',
        (
            '(version 1)\n(rule "Same" (severity error) (severity error) '
            "(constraint track_width (min 0.2mm)))\n"
        ),
        (
            '(version 1)\n(rule "Bad" (severity error) (severity unknown) '
            "(constraint track_width (min 0.2mm)))\n"
        ),
        (
            "(version 1)\n# (severity warning)\n"
            '(rule "Nested" (condition "(severity warning)") '
            "(constraint track_width (min 0.2mm)))\n"
        ),
    )
    for index, source in enumerate(sources):
        root, rules, config = _project(tmp_path / str(index), source)
        assert _scan(root, rules, config) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_parser_preserves_each_direct_severity_in_source_order() -> None:
    parsed = native_rules_with_conflicting_severities(FAULT)

    assert len(parsed) == 1
    assert (parsed[0].name, parsed[0].ordinal, parsed[0].severities) == (
        "SyntheticTrackWidth",
        1,
        ("error", "warning"),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_exactly_ignore(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    (candidate,) = _scan(root, rules, config)
    observed = coach(NetlistContract(components={}, nets={}))

    def report(policy: DesignLintPolicy) -> DesignLintReport:
        return evaluate(
            "synthetic-dru-severity-conflict",
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


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_conflict_fingerprint_tracks_source_and_rule_order(tmp_path: Path) -> None:
    root, rules, config = _project(tmp_path)
    (before,) = _scan(root, rules, config)
    rules.write_text(
        '(version 1)\n(rule "Unrelated" (severity error) '
        "(constraint clearance (min 1mm)))\n" + FAULT.removeprefix("(version 1)\n"),
        encoding="utf-8",
    )

    (after,) = _scan(root, rules, config)

    assert after.subject.endswith("#rule[2] SyntheticTrackWidth")
    assert after.evidence["source_sha256"] != before.evidence["source_sha256"]
    assert fingerprint(after) != fingerprint(before)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_stale_unexpanded_non_pcb_and_unsupported_sources_do_not_trigger(
    tmp_path: Path,
) -> None:
    root, rules, config = _project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        custom_drc_conflicting_severity_candidates(root, config, {})
    stale = digest(rules)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        custom_drc_conflicting_severity_candidates(root, config, {RULES_RELATIVE: stale})

    rules.write_text(
        '(version 1)\n(rule "${NAME}" (severity error) (severity warning) '
        "(constraint track_width (min 0.2mm)))\n",
        encoding="utf-8",
    )
    assert _scan(root, rules, config) == ()

    root, rules, schematic = _project(tmp_path / "schematic", kind=ProjectKind.SCHEMATIC)
    assert _scan(root, rules, schematic) == ()
    root, rules, unsupported = _project(tmp_path / "unsupported", kicad_version="9.0.7")
    assert _scan(root, rules, unsupported) == ()
