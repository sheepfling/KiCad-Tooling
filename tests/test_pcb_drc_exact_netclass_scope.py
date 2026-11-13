"""Review exact custom DRC class selectors absent from current project settings."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_drc_exact_netclass_scope import (
    RULE_ID,
    unmatched_exact_netclass_scope_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_netclass_scope_inventory import (
    pcb_project_netclass_scope_names,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exact-netclass-scope"
BOARD = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exact-net-scope/board.kicad_pcb"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _evidence(tmp_path: Path, settings: str, rules: str) -> BoundDrcEvidence:
    project = tmp_path / "board.kicad_pro"
    project.write_text(settings, encoding="utf-8")
    board_file = tmp_path / "board.kicad_pcb"
    board_file.write_bytes(BOARD.read_bytes())
    return BoundDrcEvidence(
        project_path="projects/synthetic/board.kicad_pro",
        project_sha256=hashlib.sha256(project.read_bytes()).hexdigest(),
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256=hashlib.sha256(rules.encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=hashlib.sha256(board_file.read_bytes()).hexdigest(),
        native_summary_path="build/native/summary.json",
        native_summary_sha256="d" * 64,
        native_drc_path="build/native/drc.json",
        native_drc_sha256="e" * 64,
        project_file=project,
        board_file=board_file,
        summary_file=tmp_path / "summary.json",
        summary_sha256_before="d" * 64,
        drc_file=tmp_path / "drc.json",
        command_file=tmp_path / "drc.command.json",
        command_sha256="f" * 64,
        rules_source=rules,
        ignored_checks=frozenset(),
    )


def _settings(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _rules(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _dru_rule(name: str, condition: str) -> str:
    return (
        f'(rule "{name}" (severity warning) (condition "{condition}") '
        "(constraint track_width (min 0.4mm)))"
    )


def _candidates(
    settings: str,
    rules: str,
    tmp_path: Path,
) -> tuple[Candidate, ...]:
    evidence = _evidence(tmp_path, settings, rules)
    names = pcb_project_netclass_scope_names(settings)
    assert names is not None
    return unmatched_exact_netclass_scope_candidates(
        native_constraints(rules), names, evidence, kicad_version="10.0.5"
    )


@pytest.mark.parametrize(
    ("settings_name", "rules_name"),
    (
        ("declared.kicad_pro", "declared.kicad_dru"),
        ("declared.kicad_pro", "case-variant.kicad_dru"),
        ("assigned-implicit.kicad_pro", "assigned-implicit.kicad_dru"),
        ("pattern-implicit.kicad_pro", "pattern-implicit.kicad_dru"),
    ),
)
def test_project_class_sources_and_casefold_controls_are_quiet(
    tmp_path: Path,
    settings_name: str,
    rules_name: str,
) -> None:
    assert not _candidates(_settings(settings_name), _rules(rules_name), tmp_path)


def test_absent_exact_class_selector_is_reviewed_with_bound_sources(tmp_path: Path) -> None:
    settings = _settings("declared.kicad_pro")
    rules = _rules("absent.kicad_dru")
    evidence = _evidence(tmp_path, settings, rules)
    names = pcb_project_netclass_scope_names(settings)
    assert names == ("Default", "Narrow")

    (finding,) = unmatched_exact_netclass_scope_candidates(
        native_constraints(rules), names, evidence, kicad_version="10.0.5"
    )

    assert finding.rule_id == RULE_ID
    assert finding.subject.startswith("GhostClass: exact custom DRC netclass selector")
    assert finding.evidence["netclass_selectors"] == ("GhostClass",)
    assert finding.evidence["project_netclass_names"] == names
    assert finding.evidence["project_sha256"] == (evidence.project_sha256,)
    assert finding.evidence["board_sha256"] == (evidence.board_sha256,)
    assert finding.evidence["rules_sha256"] == (evidence.rules_sha256,)
    assert finding.evidence["native_drc_kicad_version"] == ("10.0.5",)


def test_casefold_equivalent_absent_selectors_group_deterministically(tmp_path: Path) -> None:
    settings = _settings("declared.kicad_pro")
    rule_bodies = (
        _dru_rule("zeta", "A.NetClass == 'GHOST'"),
        _dru_rule("alpha", "A.NetClass == 'Ghost'"),
    )
    first_rules = f"(version 1)\n{rule_bodies[0]}\n{rule_bodies[1]}"
    second_rules = f"(version 1)\n{rule_bodies[1]}\n{rule_bodies[0]}"
    first = _candidates(settings, first_rules, tmp_path)
    second = _candidates(settings, second_rules, tmp_path)

    assert len(first) == len(second) == 1
    assert first[0].evidence["netclass_selectors"] == ("GHOST", "Ghost")
    assert first[0].evidence["native_rule_names"] == ("alpha", "zeta")
    assert first[0].subject == second[0].subject
    assert first[0].evidence["native_rule_names"] == second[0].evidence["native_rule_names"]


def test_unsupported_shapes_and_ambiguous_project_inventories_stay_quiet(
    tmp_path: Path,
) -> None:
    settings = _settings("declared.kicad_pro")
    rules = "\n".join(
        (
            "(version 1)",
            _dru_rule("wildcard", "A.NetClass == 'Ghost*'"),
            _dru_rule("composite", "A.NetClass == 'Ghost,Default'"),
            _dru_rule("function", "A.hasNetClass('Ghost')"),
            _dru_rule("variable", "A.NetClass == '${CLASS}'"),
        )
    )
    assert not _candidates(settings, rules, tmp_path)

    malformed = (
        '{"net_settings":{"classes":[{"name":"Default"},{"name":"Foo"},'
        '{"name":"foo"}],"netclass_assignments":{},"netclass_patterns":[]}}'
    )
    assert pcb_project_netclass_scope_names(malformed) is None
    assert pcb_project_netclass_scope_names("not JSON") is None


def test_disabled_or_unmeasured_scans_do_not_read_native_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import kicad_tooling.hwrepo.pcb_drc_exact_netclass_scope_scan as owner

    monkeypatch.setattr(
        owner,
        "source_bound_drc_evidence",
        lambda *_args: pytest.fail("disabled or unsupported requests must not read sources"),
    )

    def scan(
        *,
        kind: ProjectKind = ProjectKind.PCB,
        version: str = "10.0.5",
        mode: str = "review",
    ) -> tuple[Candidate, ...]:
        config = cast(ProjectConfig, SimpleNamespace(kind=kind, kicad_version=version))
        policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode=mode,  # type: ignore[arg-type]
                    reason="Synthetic policy case",
                ),
            )
        )
        return owner.scan_unmatched_exact_netclass_drc_scopes(
            tmp_path, config, policy, {}, tmp_path / "build/native"
        )

    assert not scan(kind=ProjectKind.SCHEMATIC)
    assert not scan(version="10.0.8")
    assert not scan(mode="off")
