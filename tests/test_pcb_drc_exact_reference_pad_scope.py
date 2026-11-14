"""Review unmatched exact custom DRC reference-and-pad selectors."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_drc_exact_reference_pad_scope import (
    RULE_ID,
    unmatched_exact_reference_pad_scope_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence
from kicad_tooling.hwrepo.pcb_footprint_reference_inventory import (
    pcb_board_footprint_pad_number_inventory,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exact-reference-pad-scope"
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


def _candidates(
    rules: str,
    tmp_path: Path,
    *,
    board_source: str | None = None,
    footprint_pads: tuple[tuple[str, tuple[str, ...]], ...] | None = None,
    version: str = "10.0.5",
) -> tuple[Candidate, ...]:
    evidence = _evidence(tmp_path, rules, board_source)
    inventory = footprint_pads or pcb_board_footprint_pad_number_inventory(
        evidence.board_file.read_text(encoding="utf-8")
    )
    assert inventory is not None
    return unmatched_exact_reference_pad_scope_candidates(
        native_constraints(rules), inventory, evidence, kicad_version=version
    )


def test_complete_footprint_pad_inventory_is_stable_and_rejects_ambiguity() -> None:
    board = BOARD.read_text(encoding="utf-8")
    assert pcb_board_footprint_pad_number_inventory(board) == (("J1", ("1",)),)
    assert pcb_board_footprint_pad_number_inventory("not a PCB") is None

    duplicate = (
        "(kicad_pcb (version 20250114) "
        '(footprint "Synthetic:A" (property "Reference" "J1") (pad "1" smd rect)) '
        '(footprint "Synthetic:B" (property "Reference" "j1") (pad "2" smd rect)))'
    )
    assert pcb_board_footprint_pad_number_inventory(duplicate) is None


def test_absent_exact_pad_selector_is_reviewed_with_source_identity(tmp_path: Path) -> None:
    rules = _rules("absent-pad")
    evidence = _evidence(tmp_path, rules)
    inventory = pcb_board_footprint_pad_number_inventory(
        evidence.board_file.read_text(encoding="utf-8")
    )
    assert inventory == (("J1", ("1",)),)

    (finding,) = unmatched_exact_reference_pad_scope_candidates(
        native_constraints(rules), inventory, evidence, kicad_version="10.0.5"
    )

    assert finding.rule_id == RULE_ID
    assert finding.subject.startswith("J1 pad 9:")
    assert finding.evidence["reference_selectors"] == ("J1",)
    assert finding.evidence["pad_number_selectors"] == ("9",)
    assert finding.evidence["current_footprint_pad_inventory"] == ('["J1",["1"]]',)
    assert finding.evidence["project_sha256"] == (evidence.project_sha256,)
    assert finding.evidence["board_sha256"] == (evidence.board_sha256,)
    assert finding.evidence["rules_sha256"] == (evidence.rules_sha256,)
    assert finding.evidence["native_drc_kicad_version"] == ("10.0.5",)
    assert "does not decide that a pad should exist" in finding.message


def test_casefolded_absent_pads_group_stably_and_existing_pad_is_a_control(
    tmp_path: Path,
) -> None:
    rules = "\n".join(
        (
            "(version 1)",
            *(_rules(name).split("\n", 1)[1] for name in ("pad-uppercase", "pad-lowercase")),
        )
    )
    (finding,) = _candidates(rules, tmp_path)
    reverse = "\n".join(
        (
            "(version 1)",
            *(_rules(name).split("\n", 1)[1] for name in ("pad-lowercase", "pad-uppercase")),
        )
    )
    (reordered,) = _candidates(reverse, tmp_path)
    assert finding.evidence["reference_selectors"] == ("J1",)
    assert finding.evidence["pad_number_selectors"] == ("A1", "a1")
    assert finding.subject == reordered.subject
    assert finding.evidence["native_conditions"] == reordered.evidence["native_conditions"]

    board = BOARD.read_text(encoding="utf-8").replace('(pad "1" smd', '(pad "A1" smd')
    assert board != BOARD.read_text(encoding="utf-8")
    assert not _candidates(rules, tmp_path, board_source=board)


def test_unsupported_scopes_and_missing_footprints_stay_quiet(tmp_path: Path) -> None:
    rules = """(version 1)
(rule "wildcard" (severity warning)
  (condition "A.Reference == 'J1' && A.Pad_Number == '*'")
  (constraint edge_clearance (min 5mm)))
(rule "compound" (severity warning)
  (condition "A.Reference == 'J1' && A.Pad_Number == '9' && A.Layer == 'F.Cu'")
  (constraint edge_clearance (min 5mm)))
(rule "ignored" (severity ignore)
  (condition "A.Reference == 'J1' && A.Pad_Number == '9'")
  (constraint edge_clearance (min 5mm)))
"""
    assert not _candidates(rules, tmp_path)
    assert not _candidates(_rules("absent-pad"), tmp_path, footprint_pads=(("J2", ("1",)),))
    assert not _candidates(_rules("absent-pad"), tmp_path, version="10.0.0")


def test_scan_skips_disabled_unsupported_and_non_pcb_requests_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import kicad_tooling.hwrepo.pcb_drc_exact_reference_pad_scope_scan as owner

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
        return owner.scan_unmatched_exact_reference_pad_drc_scopes(
            tmp_path, config, policy, {}, tmp_path / "build/native"
        )

    assert not scan(kind=ProjectKind.SCHEMATIC)
    assert not scan(version="10.0.0")
    assert not scan(mode="off")
