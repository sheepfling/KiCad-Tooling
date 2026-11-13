"""Per-project KiCad track-angle requirements and DRC rule coverage."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_drc_conditions import native_net_conditions_are_disjoint
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_track_angle import (
    RULE_ID,
    track_angle_rule_coverage_candidates,
    track_angle_rule_coverage_issue,
)
from kicad_tooling.hwrepo.pcb_track_angle_models import (
    PcbTrackAngleMap,
    PcbTrackAngleRequirement,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _requirement(**updates: object) -> PcbTrackAngleRequirement:
    values: dict[str, object] = {
        "id": "clock-output",
        "basis": "Reviewed signal-integrity routing requirement",
        "net": "CLOCK_OUT",
        "rule_name": "clock-track-angle",
        "minimum_degrees": 150,
    }
    values.update(updates)
    return PcbTrackAngleRequirement.model_validate(values)


def _rule(
    *,
    name: str = "clock-track-angle",
    net: str = "CLOCK_OUT",
    minimum: str = "150",
    maximum: str | None = None,
    severity: str | None = "error",
    condition: str | None = None,
) -> str:
    severity_clause = "" if severity is None else f"(severity {severity})"
    condition_clause = (
        f"(condition \"A.NetName == '{net}'\")"
        if condition is None
        else f'(condition "{condition}")'
    )
    bounds = f"(min {minimum})"
    if maximum is not None:
        bounds += f" (max {maximum})"
    return f'(rule "{name}" {severity_clause} {condition_clause} (constraint track_angle {bounds}))'


def _coverage(
    source: str | None = None,
    *,
    settings: str = '{"board":{"design_settings":{"rule_severities":{}}}}',
    requirement: PcbTrackAngleRequirement | None = None,
    ignored_checks: frozenset[str] = frozenset(),
    kicad_version: str = "10.0.5",
) -> str | None:
    rules_source = _rule() if source is None else source
    return track_angle_rule_coverage_issue(
        requirement or _requirement(),
        native_constraints("(version 1)\n" + rules_source),
        settings,
        ignored_checks=ignored_checks,
        kicad_version=kicad_version,
    )


def test_native_parser_reads_unitless_integer_angle_bounds() -> None:
    (parsed,) = native_constraints("(version 1)\n" + _rule(maximum="180"))

    assert parsed.name == "track_angle"
    assert parsed.minimum_angle_degrees == 150
    assert parsed.maximum_angle_degrees == 180
    assert parsed.minimum_nm is None and parsed.maximum_nm is None
    assert parsed.issue is None


@pytest.mark.parametrize(
    ("literal", "message"),
    (
        ("150deg", "Unsupported native DRC angle literal"),
        ("150mm", "Unsupported native DRC angle literal"),
        ("150.5", "not an integer degree value"),
        ("181", "outside the range 0 through 180"),
        ("${ANGLE}", "text variable substitution"),
    ),
)
def test_native_parser_marks_unsupported_angle_bounds(literal: str, message: str) -> None:
    (parsed,) = native_constraints("(version 1)\n" + _rule(minimum=literal))

    assert parsed.issue is not None and message in parsed.issue


def test_exact_project_requirement_is_covered_by_the_saved_rule() -> None:
    assert _coverage() is None
    assert _coverage(_rule(severity=None)) is None
    assert _coverage(_rule(maximum="180"), requirement=_requirement(maximum_degrees=180)) is None


def test_native_parser_rejects_repeated_or_reversed_angle_bounds() -> None:
    repeated = _rule().replace(
        "(constraint track_angle (min 150))",
        "(constraint track_angle (min 150) (min 150))",
    )
    (repeated_constraint,) = native_constraints("(version 1)\n" + repeated)
    assert repeated_constraint.issue is not None
    assert "Repeated min bound" in repeated_constraint.issue

    reversed_bounds = _rule(maximum="140")
    (reversed_constraint,) = native_constraints("(version 1)\n" + reversed_bounds)
    assert reversed_constraint.issue is not None
    assert "minimum angle above its maximum" in reversed_constraint.issue


@pytest.mark.parametrize(
    ("source", "settings", "ignored", "version", "message"),
    (
        (
            "",
            '{"board":{"design_settings":{"rule_severities":{}}}}',
            frozenset(),
            "10.0.5",
            "no track_angle",
        ),
        (
            _rule(net="DATA"),
            '{"board":{"design_settings":{"rule_severities":{}}}}',
            frozenset(),
            "10.0.5",
            "exact project-authored net scope",
        ),
        (
            _rule(minimum="149"),
            '{"board":{"design_settings":{"rule_severities":{}}}}',
            frozenset(),
            "10.0.5",
            "bounds differ",
        ),
        (
            _rule(severity="warning"),
            '{"board":{"design_settings":{"rule_severities":{}}}}',
            frozenset(),
            "10.0.5",
            "not a blocking error",
        ),
        (
            _rule(severity="ignore"),
            '{"board":{"design_settings":{"rule_severities":{}}}}',
            frozenset(),
            "10.0.5",
            "not a blocking error",
        ),
        (
            _rule(),
            '{"board":{"design_settings":{"rule_severities":{"track_angle":"warning"}}}}',
            frozenset(),
            "10.0.5",
            "global KiCad track_angle",
        ),
        (
            _rule(),
            '{"board":{"design_settings":{"rule_severities":{"track_angle":"ignore"}}}}',
            frozenset(),
            "10.0.5",
            "global KiCad track_angle",
        ),
        (
            _rule(),
            '{"board":{"design_settings":{"rule_severities":{}}}}',
            frozenset({"track_angle"}),
            "10.0.5",
            "records track_angle as ignored",
        ),
        (
            _rule(),
            '{"board":{"design_settings":{"rule_severities":{},"drc_exclusions":["track_angle|item"]}}}',
            frozenset(),
            "10.0.5",
            "track_angle DRC exclusion",
        ),
        (
            _rule(),
            '{"board":{"design_settings":{"rule_severities":{}}}}',
            frozenset(),
            "10.0.6",
            "not been audited",
        ),
    ),
)
def test_missing_mismatched_or_suppressed_coverage_is_reported(
    source: str,
    settings: str,
    ignored: frozenset[str],
    version: str,
    message: str,
) -> None:
    issue = _coverage(source, settings=settings, ignored_checks=ignored, kicad_version=version)

    assert issue is not None and message in issue


def test_duplicate_or_overriding_rules_are_not_credited() -> None:
    duplicate = _rule().replace(
        "(constraint track_angle (min 150))",
        "(constraint track_angle (min 150)) (constraint track_angle (min 150))",
    )
    assert _coverage(duplicate) == "The named native DRC rule has multiple track_angle constraints."

    later_generic = (
        _rule() + "\n" + _rule(name="later-generic", condition="A.NetName != 'CLOCK_OUT'")
    )
    assert "Later native track_angle rules may override" in (_coverage(later_generic) or "")

    later_other_net = _rule() + "\n" + _rule(name="later-data", net="DATA")
    assert _coverage(later_other_net) is None

    unresolved = _rule() + '\n(rule "with-variable" (constraint track_angle (min ${ANGLE})))'
    assert "text variable" in (_coverage(unresolved) or "")


def test_exact_net_condition_disjointness_proves_only_literal_inequality() -> None:
    assert native_net_conditions_are_disjoint("A.NetName == 'CLOCK_OUT'", "A.NetName == 'DATA'")
    assert not native_net_conditions_are_disjoint(
        "A.NetName == 'CLOCK_OUT'", "A.NetName == 'clock_out'"
    )
    assert not native_net_conditions_are_disjoint(
        "A.NetName == 'CLOCK_OUT'", "A.NetName != 'CLOCK_OUT'"
    )


def test_map_requires_reviewable_unique_exact_net_scopes() -> None:
    first = _requirement()
    second = _requirement(id="data", net="DATA", rule_name="data-angle")
    assert PcbTrackAngleMap(basis="Reviewed routing plan", requirements=(first, second))

    with pytest.raises(ValueError, match="at least one degree bound"):
        _requirement(minimum_degrees=None)
    with pytest.raises(ValueError, match="cannot exceed"):
        _requirement(minimum_degrees=160, maximum_degrees=150)
    with pytest.raises(ValueError, match="less than or equal to 180"):
        _requirement(minimum_degrees=181)
    with pytest.raises(ValueError, match="represented by an exact native rule"):
        _requirement(net="DATA' OR true")
    with pytest.raises(ValueError, match="only one track-angle requirement"):
        PcbTrackAngleMap(
            basis="Duplicate",
            requirements=(first, first.model_copy(update={"id": "copy", "rule_name": "copy"})),
        )


def test_candidate_is_review_mode_and_policy_off_skips_source_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kicad_tooling.hwrepo.pcb_track_angle as owner

    project_file = tmp_path / "board.kicad_pro"
    project_file.write_text(
        '{"board":{"design_settings":{"rule_severities":{}}}}', encoding="utf-8"
    )
    evidence = SimpleNamespace(
        rules_source="(version 1)\n" + _rule(minimum="149"),
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256="a" * 64,
        project_path="projects/synthetic/board.kicad_pro",
        project_sha256="b" * 64,
        project_file=project_file,
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256="c" * 64,
        native_drc_path="build/native/drc.json",
        native_drc_sha256="d" * 64,
        native_drc_kicad_version="10.0.5",
        native_summary_path="build/native/summary.json",
        native_summary_sha256="e" * 64,
        ignored_checks=frozenset(),
    )
    monkeypatch.setattr(owner, "source_bound_drc_evidence", lambda *args: evidence)
    monkeypatch.setattr(owner, "verify_source_bound_drc_unchanged", lambda *args: None)
    config = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"))
    policy = DesignLintPolicy(pcb_track_angle_map=map_for_test())

    (candidate,) = track_angle_rule_coverage_candidates(
        tmp_path, config, policy, {}, tmp_path / "build/native"
    )
    assert candidate.rule_id == RULE_ID
    assert candidate.evidence["net"] == ("CLOCK_OUT",)
    assert "confirmed, unambiguous source-bound native DRC coverage" in candidate.message

    monkeypatch.setattr(
        owner,
        "source_bound_drc_evidence",
        lambda *args: pytest.fail("disabled map must not read native DRC evidence"),
    )
    off_policy = DesignLintPolicy(
        rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Reviewed exception"),),
        pcb_track_angle_map=map_for_test(),
    )
    assert (
        track_angle_rule_coverage_candidates(
            tmp_path, config, off_policy, {}, tmp_path / "build/native"
        )
        == ()
    )


def map_for_test() -> PcbTrackAngleMap:
    return PcbTrackAngleMap(
        basis="Reviewed synthetic routing requirement",
        requirements=(_requirement(),),
    )
