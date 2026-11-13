"""Review native track-width rules omitted from mapped geometry scope."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence
from kicad_tooling.hwrepo.pcb_track_width_models import (
    PcbTrackWidthMap,
    PcbTrackWidthRequirement,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.track_width_unmapped_native_rule"),
]

RULE_ID = "pcb.track_width_unmapped_native_rule"
GEOMETRY_RULE_ID = "pcb.minimum_track_width"


def _native_rule(
    name: str,
    net: str,
    *,
    condition: str | None = None,
    constraint: str = "track_width",
) -> str:
    selector = f"A.NetName == '{net}'" if condition is None else condition
    return (
        f'(rule "{name}" (severity error) (condition "{selector}") '
        f"(constraint {constraint} (min 0.25mm)))"
    )


def _map(*nets: str) -> PcbTrackWidthMap:
    return PcbTrackWidthMap(
        basis="Synthetic reviewed geometry-review scope",
        requirements=tuple(
            PcbTrackWidthRequirement(
                id=f"net-{index}",
                basis="Synthetic exact-net width review",
                net=net,
                minimum_width_um=250,
            )
            for index, net in enumerate(nets, start=1)
        ),
    )


def _policy(
    requirements: PcbTrackWidthMap | None,
    *,
    geometry_mode: str = "review",
    unmapped_mode: str = "review",
) -> DesignLintPolicy:
    return DesignLintPolicy(
        pcb_track_width_map=requirements,
        rules=(
            DesignLintRuleOverride(
                rule_id=GEOMETRY_RULE_ID,
                mode=geometry_mode,  # type: ignore[arg-type]
                reason="Synthetic test policy",
            ),
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=unmapped_mode,  # type: ignore[arg-type]
                reason="Synthetic test policy",
            ),
        ),
    )


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
    requirements: PcbTrackWidthMap | None,
    policy: DesignLintPolicy | None = None,
):
    import kicad_tooling.hwrepo.pcb_track_width_rule_coverage as owner

    evidence = _bound_evidence(tmp_path, source)
    monkeypatch.setattr(owner, "source_bound_drc_evidence", lambda *_args: evidence)
    monkeypatch.setattr(owner, "verify_source_bound_drc_unchanged", lambda *_args: None)
    config = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"))
    return owner.track_width_rule_scope_candidates(
        tmp_path,
        config,
        _policy(requirements) if policy is None else policy,
        {},
        tmp_path / "build/native",
    )


def test_unmapped_exact_native_track_width_scope_is_reviewed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "(version 1)\n" + _native_rule("data-width", "DATA")

    (finding,) = _scan(tmp_path, monkeypatch, source, _map("CLOCK"))

    assert finding.rule_id == RULE_ID
    assert finding.subject == "data-width: DATA is absent from track-width geometry scope"
    assert finding.evidence["net"] == ("DATA",)
    assert finding.evidence["native_rule_name"] == ("data-width",)
    assert finding.evidence["native_width_bounds_nm"] == ("min=250000;max=None",)
    assert finding.evidence["source_sha256"] == ("b" * 64,)
    assert finding.evidence["native_drc_kicad_version"] == ("10.0.5",)
    assert "not an ampacity calculation" in finding.message


def test_mapped_exact_net_and_board_wide_scopes_are_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "(version 1)\n" + _native_rule("data-width", "DATA")

    assert not _scan(tmp_path, monkeypatch, source, _map("data"))
    assert not _scan(tmp_path, monkeypatch, source, _map("*"))


def test_nonliteral_scope_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = "\n".join(
        (
            "(version 1)",
            _native_rule("family-width", "DATA", condition="A.NetName =~ 'DATA.*'"),
            _native_rule("angle-only", "MISSING", constraint="track_angle"),
        )
    )

    assert not _scan(tmp_path, monkeypatch, source, _map("CLOCK"))


@pytest.mark.parametrize(
    ("geometry_mode", "unmapped_mode"),
    (("off", "review"), ("review", "off")),
    ids=("geometry-disabled", "heuristic-disabled"),
)
def test_geometry_and_new_rule_overrides_disable_source_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    geometry_mode: str,
    unmapped_mode: str,
) -> None:
    import kicad_tooling.hwrepo.pcb_track_width_rule_coverage as owner

    monkeypatch.setattr(
        owner,
        "source_bound_drc_evidence",
        lambda *_args: pytest.fail("disabled scope must not read source evidence"),
    )
    config = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"))

    assert not owner.track_width_rule_scope_candidates(
        tmp_path,
        config,
        _policy(_map("CLOCK"), geometry_mode=geometry_mode, unmapped_mode=unmapped_mode),
        {},
        tmp_path / "build/native",
    )


def test_missing_map_and_non_pcb_project_do_not_read_source_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import kicad_tooling.hwrepo.pcb_track_width_rule_coverage as owner

    monkeypatch.setattr(
        owner,
        "source_bound_drc_evidence",
        lambda *_args: pytest.fail("unconfigured scope must not read source evidence"),
    )
    config = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"))
    schematic = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.SCHEMATIC, kicad_version="10.0.5"),
    )

    assert not owner.track_width_rule_scope_candidates(
        tmp_path, config, _policy(None), {}, tmp_path / "build/native"
    )
    assert not owner.track_width_rule_scope_candidates(
        tmp_path, schematic, _policy(_map("CLOCK")), {}, tmp_path / "build/native"
    )


@pytest.mark.parametrize("reverse", (False, True), ids=("normal-order", "reversed-order"))
def test_rule_order_does_not_change_unmapped_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reverse: bool
) -> None:
    rules = (_native_rule("alpha-width", "DATA"), _native_rule("beta-width", "AUX"))
    if reverse:
        rules = tuple(reversed(rules))
    source = "(version 1)\n" + "\n".join(rules)

    findings = _scan(tmp_path, monkeypatch, source, _map("CLOCK"))

    assert tuple((item.subject, item.evidence["net"]) for item in findings) == (
        ("alpha-width: DATA is absent from track-width geometry scope", ("DATA",)),
        ("beta-width: AUX is absent from track-width geometry scope", ("AUX",)),
    )


def test_native_parser_preserves_exact_track_width_scope_and_bounds() -> None:
    parsed = native_constraints("(version 1)\n" + _native_rule("data-width", "DATA"))

    assert len(parsed) == 1
    assert parsed[0].name == "track_width"
    assert parsed[0].condition == "A.NetName == 'DATA'"
    assert parsed[0].minimum_nm == 250_000
