"""Review native per-net track-angle rules omitted from geometry scope."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence
from kicad_tooling.hwrepo.pcb_track_angle_models import (
    PcbTrackAngleMap,
    PcbTrackAngleRequirement,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.track_angle_unmapped_native_rule"),
]

RULE_ID = "pcb.track_angle_unmapped_native_rule"
GEOMETRY_RULE_ID = "pcb.track_angle_geometry_review"
COVERAGE_RULE_ID = "pcb.track_angle_rule_coverage"


def _native_rule(name: str, net: str, *, condition: str | None = None) -> str:
    selector = f"A.NetName == '{net}'" if condition is None else condition
    return (
        f'(rule "{name}" (severity error) (condition "{selector}") '
        "(constraint track_angle (min 150)))"
    )


def _map(*nets: str) -> PcbTrackAngleMap:
    return PcbTrackAngleMap(
        basis="Synthetic reviewed geometry-review scope",
        requirements=tuple(
            PcbTrackAngleRequirement(
                id=f"net-{index}",
                basis="Synthetic exact-net routing requirement",
                net=net,
                rule_name=f"{net.lower()}-angle",
                minimum_degrees=150,
            )
            for index, net in enumerate(nets, start=1)
        ),
    )


def _policy(
    requirements: PcbTrackAngleMap,
    *,
    geometry_mode: str | None = "review",
    coverage_mode: str = "review",
    unmapped_mode: str = "review",
) -> DesignLintPolicy:
    overrides = [
        DesignLintRuleOverride(
            rule_id=COVERAGE_RULE_ID,
            mode=coverage_mode,  # type: ignore[arg-type]
            reason="Synthetic test policy",
        ),
        DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode=unmapped_mode,  # type: ignore[arg-type]
            reason="Synthetic test policy",
        ),
    ]
    if geometry_mode is not None:
        overrides.append(
            DesignLintRuleOverride(
                rule_id=GEOMETRY_RULE_ID,
                mode=geometry_mode,  # type: ignore[arg-type]
                reason="Synthetic test policy",
            )
        )
    return DesignLintPolicy(pcb_track_angle_map=requirements, rules=tuple(overrides))


def _bound_evidence(tmp_path: Path, source: str) -> BoundDrcEvidence:
    project_file = tmp_path / "board.kicad_pro"
    project_file.write_text(
        '{"board":{"design_settings":{"rule_severities":{}}}}', encoding="utf-8"
    )
    return BoundDrcEvidence(
        project_path="projects/synthetic/board.kicad_pro",
        project_sha256="a" * 64,
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256="b" * 64,
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256="c" * 64,
        native_summary_path="build/native/summary.json",
        native_summary_sha256="d" * 64,
        native_drc_path="build/native/drc.json",
        native_drc_sha256="e" * 64,
        project_file=project_file,
        board_file=tmp_path / "board.kicad_pcb",
        summary_file=tmp_path / "summary.json",
        summary_sha256_before="d" * 64,
        drc_file=tmp_path / "drc.json",
        command_file=tmp_path / "drc.command.json",
        command_sha256="f" * 64,
        rules_source=source,
        ignored_checks=frozenset(),
    )


def _scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    requirements: PcbTrackAngleMap,
    policy: DesignLintPolicy | None = None,
) -> tuple[Candidate, ...]:
    import kicad_tooling.hwrepo.pcb_track_angle as owner

    evidence = _bound_evidence(tmp_path, source)
    monkeypatch.setattr(owner, "source_bound_drc_evidence", lambda *_args: evidence)
    monkeypatch.setattr(owner, "verify_source_bound_drc_unchanged", lambda *_args: None)
    config = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"))
    return owner.track_angle_rule_coverage_candidates(
        tmp_path,
        config,
        _policy(requirements) if policy is None else policy,
        {},
        tmp_path / "build/native",
    )


def test_unmapped_exact_per_net_rule_is_reviewed_when_geometry_lint_is_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "(version 1)\n"
        + _native_rule("clock_out-angle", "CLOCK_OUT")
        + "\n"
        + _native_rule("data-angle", "DATA")
    )

    findings = _scan(tmp_path, monkeypatch, source, _map("CLOCK_OUT"))
    (finding,) = (item for item in findings if item.rule_id == RULE_ID)

    assert finding.subject == "data-angle: DATA is absent from track-angle geometry scope"
    assert finding.evidence["net"] == ("DATA",)
    assert finding.evidence["native_rule_name"] == ("data-angle",)
    assert finding.evidence["source_sha256"] == ("b" * 64,)
    assert finding.evidence["native_drc_kicad_version"] == ("10.0.5",)
    assert "Native DRC remains the authority" in finding.message


def test_map_entry_covers_the_exact_native_net_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "(version 1)\n"
        + _native_rule("clock_out-angle", "CLOCK_OUT")
        + "\n"
        + _native_rule("data-angle", "DATA")
    )

    findings = _scan(tmp_path, monkeypatch, source, _map("CLOCK_OUT", "DATA"))

    assert not findings


def test_nonliteral_rule_scope_is_not_treated_as_an_unmapped_exact_net(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "(version 1)\n"
        + _native_rule("clock_out-angle", "CLOCK_OUT")
        + "\n"
        + _native_rule("data-family-angle", "DATA", condition="A.NetName =~ 'DATA.*'")
    )

    findings = _scan(tmp_path, monkeypatch, source, _map("CLOCK_OUT"))

    assert RULE_ID not in {item.rule_id for item in findings}


def test_geometry_review_scope_is_opt_in_and_new_rule_can_be_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "(version 1)\n"
        + _native_rule("clock_out-angle", "CLOCK_OUT")
        + "\n"
        + _native_rule("data-angle", "DATA")
    )

    default_policy = _policy(_map("CLOCK_OUT"), geometry_mode=None)
    assert not _scan(tmp_path, monkeypatch, source, _map("CLOCK_OUT"), default_policy)

    disabled_policy = _policy(_map("CLOCK_OUT"), unmapped_mode="off")
    assert not _scan(tmp_path, monkeypatch, source, _map("CLOCK_OUT"), disabled_policy)


def test_unmapped_review_remains_active_when_mapped_coverage_is_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "(version 1)\n"
        + _native_rule("clock_out-angle", "CLOCK_OUT")
        + "\n"
        + _native_rule("data-angle", "DATA")
    )
    policy = _policy(_map("CLOCK_OUT"), coverage_mode="off")

    findings = _scan(tmp_path, monkeypatch, source, _map("CLOCK_OUT"), policy)

    assert {item.rule_id for item in findings} == {RULE_ID}


@pytest.mark.parametrize("reverse", (False, True), ids=("normal-order", "reversed-order"))
def test_rule_order_does_not_change_the_unmapped_scope_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reverse: bool
) -> None:
    rules = (_native_rule("clock_out-angle", "CLOCK_OUT"), _native_rule("data-angle", "DATA"))
    if reverse:
        rules = tuple(reversed(rules))
    source = "(version 1)\n" + "\n".join(rules)

    findings = _scan(tmp_path, monkeypatch, source, _map("CLOCK_OUT"))
    semantic_findings = tuple(
        (item.subject, item.evidence["net"], item.evidence["native_rule_name"])
        for item in findings
        if item.rule_id == RULE_ID
    )

    assert semantic_findings == (
        ("data-angle: DATA is absent from track-angle geometry scope", ("DATA",), ("data-angle",)),
    )


def test_native_exact_net_condition_requires_one_literal_selector() -> None:
    from kicad_tooling.hwrepo.pcb_drc_conditions import native_exact_net_condition

    assert native_exact_net_condition("A.NetName == 'CLOCK_OUT'") == "CLOCK_OUT"
    assert native_exact_net_condition("A.NetName =~ 'CLOCK.*'") is None
    assert native_exact_net_condition("A.NetName == 'DATA' || A.NetName == 'CLOCK_OUT'") is None


def test_native_constraints_are_parsed_without_touching_unrelated_project_files() -> None:
    parsed = native_constraints("(version 1)\n" + _native_rule("clock_out-angle", "CLOCK_OUT"))

    assert len(parsed) == 1
    assert parsed[0].name == "track_angle"
    assert parsed[0].condition == "A.NetName == 'CLOCK_OUT'"
