"""Review exact custom DRC reference selectors absent from the current PCB."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_drc_exact_reference_scope import (
    RULE_ID,
    unmatched_exact_reference_scope_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence
from kicad_tooling.hwrepo.pcb_footprint_reference_inventory import (
    pcb_board_footprint_reference_names,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exact-reference-scope"
BOARD = (
    Path(__file__).parent / "fixtures/design_lint/pcb-mechanical-edge-clearance/control.kicad_pcb"
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _evidence(tmp_path: Path, rules: str, board_source: str | None = None) -> BoundDrcEvidence:
    project = tmp_path / "board.kicad_pro"
    project.write_text("{}", encoding="utf-8")
    board_file = tmp_path / "board.kicad_pcb"
    board_file.write_text(
        board_source if board_source is not None else BOARD.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
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


def _rules(name: str) -> str:
    return (FIXTURES / f"{name}.kicad_dru").read_text(encoding="utf-8")


def _rule(name: str, reference: str, *, severity: str = "warning") -> str:
    return (
        f'(rule "{name}" (severity {severity}) '
        f"(condition \"A.Reference == '{reference}'\") "
        "(constraint edge_clearance (min 5mm)))"
    )


def _candidates(
    rules: str,
    tmp_path: Path,
    *,
    board_source: str | None = None,
    references: tuple[str, ...] = ("J1",),
    version: str = "10.0.5",
) -> tuple[Candidate, ...]:
    evidence = _evidence(tmp_path, rules, board_source)
    return unmatched_exact_reference_scope_candidates(
        native_constraints(rules), references, evidence, kicad_version=version
    )


def test_complete_board_inventory_returns_sorted_unique_references() -> None:
    board = BOARD.read_text(encoding="utf-8")
    assert pcb_board_footprint_reference_names(board) == ("J1",)
    assert pcb_board_footprint_reference_names("not a PCB") is None

    duplicate = (
        "(kicad_pcb (version 20250114) "
        '(footprint "Synthetic:A" (property "Reference" "J1")) '
        '(footprint "Synthetic:B" (property "Reference" "j1")))'
    )
    assert pcb_board_footprint_reference_names(duplicate) is None


def test_absent_exact_selector_is_reviewed_with_bound_sources(tmp_path: Path) -> None:
    rules = _rules("absent")
    evidence = _evidence(tmp_path, rules)
    references = pcb_board_footprint_reference_names(evidence.board_file.read_text())
    assert references == ("J1",)

    (finding,) = unmatched_exact_reference_scope_candidates(
        native_constraints(rules), references, evidence, kicad_version="10.0.5"
    )

    assert finding.rule_id == RULE_ID
    assert finding.subject.startswith("GHOST: exact custom DRC reference selector")
    assert finding.evidence["reference_selectors"] == ("GHOST",)
    assert finding.evidence["current_footprint_references"] == references
    assert finding.evidence["project_sha256"] == (evidence.project_sha256,)
    assert finding.evidence["board_sha256"] == (evidence.board_sha256,)
    assert finding.evidence["rules_sha256"] == (evidence.rules_sha256,)
    assert finding.evidence["native_drc_kicad_version"] == ("10.0.5",)
    assert "does not decide that the footprint should exist" in finding.message


def test_present_and_casefold_equivalent_selectors_are_quiet_or_grouped(
    tmp_path: Path,
) -> None:
    present = f"(version 1)\n{_rule('present', 'J1')}"
    lowercase = f"(version 1)\n{_rule('lowercase', 'j1')}"
    assert not _candidates(present, tmp_path)
    assert not _candidates(lowercase, tmp_path)

    rules = f"(version 1)\n{_rule('zeta', 'GHOST')}\n{_rule('alpha', 'ghost')}"
    reversed_rules = f"(version 1)\n{_rule('alpha', 'ghost')}\n{_rule('zeta', 'GHOST')}"
    first = _candidates(rules, tmp_path)
    second = _candidates(reversed_rules, tmp_path)
    assert len(first) == len(second) == 1
    assert first[0].evidence["reference_selectors"] == ("GHOST", "ghost")
    assert first[0].evidence["native_rule_names"] == ("alpha", "zeta")
    assert first[0].subject == second[0].subject
    assert first[0].evidence["native_conditions"] == second[0].evidence["native_conditions"]


def test_unsupported_shapes_ignored_constraints_and_ambiguous_inventory_stay_quiet(
    tmp_path: Path,
) -> None:
    rules = "\n".join(
        (
            "(version 1)",
            _rule("wildcard", "GHOST*"),
            (
                '(rule "compound" (condition "A.Reference == \'GHOST\' || '
                "A.Reference == 'J1'\") (constraint edge_clearance (min 5mm)))"
            ),
            (
                '(rule "function" (condition "A.hasReference(\'GHOST\')") '
                "(constraint edge_clearance (min 5mm)))"
            ),
            _rule("ignored", "IGNORED", severity="ignore"),
        )
    )
    assert not _candidates(rules, tmp_path)

    colliding_references = (
        "(kicad_pcb (version 20250114) "
        '(footprint "Synthetic:A" (property "Reference" "J1")) '
        '(footprint "Synthetic:B" (property "Reference" "j1")))'
    )
    evidence = _evidence(tmp_path, rules, colliding_references)
    references = pcb_board_footprint_reference_names(evidence.board_file.read_text())
    assert references is None


def test_candidate_support_is_limited_to_native_verified_kicad_version(
    tmp_path: Path,
) -> None:
    assert not _candidates(_rules("absent"), tmp_path, version="10.0.0")
    assert not _candidates(_rules("absent"), tmp_path, references=("J1", "j1"))


def test_scan_skips_disabled_unsupported_and_non_pcb_requests_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import kicad_tooling.hwrepo.pcb_drc_exact_reference_scope_scan as owner

    monkeypatch.setattr(
        owner,
        "source_bound_drc_evidence",
        lambda *_args: pytest.fail("out-of-scope scans must not read native sources"),
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
        return owner.scan_unmatched_exact_reference_drc_scopes(
            tmp_path, config, policy, {}, tmp_path / "build/native"
        )

    assert not scan(kind=ProjectKind.SCHEMATIC)
    assert not scan(version="10.0.0")
    assert not scan(mode="off")
