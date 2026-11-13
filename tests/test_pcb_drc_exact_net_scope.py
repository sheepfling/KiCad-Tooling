"""Review exact custom DRC net selectors absent from the current PCB net table."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_board_net_inventory import pcb_board_net_names
from kicad_tooling.hwrepo.pcb_drc_exact_net_scope import (
    RULE_ID,
    unmatched_exact_net_scope_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exact-net-scope"
BOARD = FIXTURES / "board.kicad_pcb"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _evidence(tmp_path: Path, source: str, board: Path | None = None) -> BoundDrcEvidence:
    project = tmp_path / "board.kicad_pro"
    project.write_text("{}", encoding="utf-8")
    board_file = tmp_path / "board.kicad_pcb"
    board_file.write_text((board or BOARD).read_text(encoding="utf-8"), encoding="utf-8")
    return BoundDrcEvidence(
        project_path="projects/synthetic/board.kicad_pro",
        project_sha256=hashlib.sha256(project.read_bytes()).hexdigest(),
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
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
        rules_source=source,
        ignored_checks=frozenset(),
    )


def _rule(name: str, net: str, *, severity: str = "warning") -> str:
    condition = f"A.NetName == '{net}'"
    return (
        f'(rule "{name}" (severity {severity}) (condition "{condition}") '
        "(constraint track_width (min 0.4mm)))"
    )


def _scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    *,
    kind: ProjectKind = ProjectKind.PCB,
    version: str = "10.0.5",
    mode: str = "review",
    board: Path | None = None,
):
    import kicad_tooling.hwrepo.pcb_drc_exact_net_scope_scan as owner

    evidence = _evidence(tmp_path, source, board)
    monkeypatch.setattr(owner, "source_bound_drc_evidence", lambda *_args: evidence)
    monkeypatch.setattr(owner, "verify_source_bound_drc_unchanged", lambda *_args: None)
    config = cast(ProjectConfig, SimpleNamespace(kind=kind, kicad_version=version))
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,  # type: ignore[arg-type]
                reason="Synthetic project policy",
            ),
        )
    )
    return owner.scan_unmatched_exact_net_drc_scopes(
        tmp_path,
        config,
        policy,
        {},
        tmp_path / "build/native",
    )


def test_pcb_net_table_reader_returns_sorted_exact_names() -> None:
    assert pcb_board_net_names(BOARD.read_text(encoding="utf-8")) == ("N1", "N2")


def test_exact_net_selector_missing_from_board_is_reviewed_with_native_evidence(
    tmp_path: Path,
) -> None:
    source = "(version 1)\n" + "\n".join(
        (
            _rule("stale-width", "GHOST"),
            _rule("stale-width-secondary", "GHOST"),
            _rule("matched-width", "N1"),
            _rule("ignored-width", "ABSENT_IGNORE", severity="ignore"),
        )
    )
    evidence = _evidence(tmp_path, source)
    board_nets = pcb_board_net_names(evidence.board_file.read_text(encoding="utf-8"))
    assert board_nets is not None

    (finding,) = unmatched_exact_net_scope_candidates(
        native_constraints(source),
        board_nets,
        evidence,
        kicad_version="10.0.5",
    )

    assert finding.rule_id == RULE_ID
    assert finding.subject == "GHOST: exact custom DRC net selector is absent from the current PCB"
    assert finding.evidence["net_selector"] == ("GHOST",)
    assert finding.evidence["native_rule_names"] == ("stale-width", "stale-width-secondary")
    assert finding.evidence["native_constraint_count"] == ("2",)
    assert finding.evidence["native_conditions"] == ("A.NetName == 'GHOST'",)
    assert finding.evidence["rules_sha256"] == (hashlib.sha256(source.encode()).hexdigest(),)
    assert finding.evidence["board_sha256"] == (evidence.board_sha256,)
    assert finding.evidence["native_drc_kicad_version"] == ("10.0.5",)
    assert "does not decide that the net should exist" in finding.message


def test_current_net_names_and_unsupported_condition_shapes_are_quiet(tmp_path: Path) -> None:
    source = "(version 1)\n" + "\n".join(
        (
            _rule("present", "N1"),
            _rule("case-insensitive-present", "n1"),
            (
                '(rule "wildcard" (condition "A.NetName == \'GHOST*\'") '
                "(constraint track_width (min 0.4mm)))"
            ),
            (
                "(rule \"compound\" (condition \"A.NetName == 'GHOST' || A.NetName == 'N1'\") "
                "(constraint track_width (min 0.4mm)))"
            ),
        )
    )
    evidence = _evidence(tmp_path, source)
    board_nets = pcb_board_net_names(evidence.board_file.read_text(encoding="utf-8"))
    assert board_nets is not None

    assert not unmatched_exact_net_scope_candidates(
        native_constraints(source),
        board_nets,
        evidence,
        kicad_version="10.0.5",
    )


def test_casefold_colliding_board_names_are_not_called_unmatched(tmp_path: Path) -> None:
    source = "(version 1)\n" + _rule("present", "n1")
    evidence = _evidence(tmp_path, source)

    assert not unmatched_exact_net_scope_candidates(
        native_constraints(source),
        ("N1", "n1"),
        evidence,
        kicad_version="10.0.5",
    )


def test_scanner_runs_for_pcb_only_and_skips_unsupported_or_disabled_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = "(version 1)\n" + _rule("stale-width", "GHOST")
    pcb_only = _scan(tmp_path, monkeypatch, source, kind=ProjectKind.PCB_ONLY)
    assert len(pcb_only) == 1

    import kicad_tooling.hwrepo.pcb_drc_exact_net_scope_scan as owner

    monkeypatch.setattr(
        owner,
        "source_bound_drc_evidence",
        lambda *_args: pytest.fail(
            "unsupported and disabled requests must not read native sources"
        ),
    )
    assert not _scan(tmp_path, monkeypatch, source, version="10.0.8")
    assert not _scan(tmp_path, monkeypatch, source, kind=ProjectKind.SCHEMATIC)
    assert not _scan(tmp_path, monkeypatch, source, mode="off")


def test_malformed_board_net_inventory_does_not_create_a_stale_scope_finding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    malformed = tmp_path / "malformed.kicad_pcb"
    malformed.write_text("(kicad_pcb (net 1 N1) (net 1 N2))", encoding="utf-8")
    source = "(version 1)\n" + _rule("stale-width", "GHOST")
    assert not _scan(tmp_path, monkeypatch, source, board=malformed)


def test_rule_order_does_not_change_grouping_or_subject_order(tmp_path: Path) -> None:
    rules = (_rule("zeta", "Z_GHOST"), _rule("alpha", "A_GHOST"), _rule("beta", "Z_GHOST"))
    first_source = "(version 1)\n" + "\n".join(rules)
    second_source = "(version 1)\n" + "\n".join(reversed(rules))
    evidence = _evidence(tmp_path, first_source)
    board_nets = pcb_board_net_names(evidence.board_file.read_text(encoding="utf-8"))
    assert board_nets is not None

    first = unmatched_exact_net_scope_candidates(
        native_constraints(first_source), board_nets, evidence, kicad_version="10.0.5"
    )
    second = unmatched_exact_net_scope_candidates(
        native_constraints(second_source), board_nets, evidence, kicad_version="10.0.5"
    )

    assert tuple(item.subject for item in first) == tuple(item.subject for item in second)
    assert tuple(item.evidence["native_rule_names"] for item in first) == tuple(
        item.evidence["native_rule_names"] for item in second
    )
