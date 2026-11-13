"""Source-bound regression tests for mixed-net footprints with unassigned pads."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_component_coverage import ComponentMapCoverageInputs
from kicad_tooling.hwrepo.design_lint_evaluation_types import DesignLintEvaluationRequest
from kicad_tooling.hwrepo.design_lint_evaluator import evaluate_request
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    ProjectConfig,
    ProjectKind,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_pad_net_comparison import compare_schematic_pcb_pad_nets
from kicad_tooling.hwrepo.pcb_unassigned_copper_pad import unassigned_copper_pad_candidates
from tests.design_lint_fixtures.pcb_component_inventory import coach, netlist, snapshot

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.unassigned_copper_pad_review"),
]

RULE_ID: DesignLintRuleId = "pcb.unassigned_copper_pad_review"
PROJECT = "projects/synthetic/controller.kicad_pro"
BOARD = "projects/synthetic/controller.kicad_pcb"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-unassigned-copper-pad"
FOOTPRINT = "Synthetic:TwoPadConnector"


def _project(
    tmp_path: Path,
    case: str = "fault",
    *,
    version: str = "10.0.5",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    board_path = root / BOARD
    board_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_pcb", board_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=PROJECT, kicad_version=version),
    )
    return root, board_path, config, {BOARD: digest(board_path)}


def _observed(*, pin_numbers: tuple[str, ...] = ("1",)) -> NetlistContract:
    return netlist(
        components={"J1": FOOTPRINT},
        nets={"SIGNAL": ("J1.1",)},
        component_pin_numbers={"J1": pin_numbers},
    )


def _scan(
    root: Path,
    config: ProjectConfig,
    hashes: dict[str, str],
    *,
    observed: NetlistContract | None = None,
) -> tuple[Candidate, ...]:
    return unassigned_copper_pad_candidates(root, config, hashes, observed or _observed())


def _evaluate(
    observed,
    candidates: tuple[Candidate, ...],
    policy: DesignLintPolicy | None = None,
):
    return evaluate_request(
        DesignLintEvaluationRequest(
            project_id="synthetic",
            coach=coach(observed),
            policy=policy or DesignLintPolicy(),
            component_map_coverage=ComponentMapCoverageInputs(),
            pcb_source_candidates=candidates,
        )
    )


def test_mixed_net_footprint_reports_unassigned_copper_pad(tmp_path: Path) -> None:
    root, board, config, hashes = _project(tmp_path)

    (candidate,) = _scan(root, config, hashes)

    assert candidate.rule_id == RULE_ID
    assert candidate.subject.endswith(":J1.2")
    assert "schematic pin inventory" in candidate.message
    assert candidate.evidence["source_path"] == (BOARD,)
    assert candidate.evidence["source_sha256"] == (digest(board),)
    assert candidate.evidence["reference"] == ("J1",)
    assert candidate.evidence["pad_number"] == ("2",)
    assert candidate.evidence["assigned_pad_numbers"] == ("1",)


def test_mixed_net_footprint_reports_unassigned_unnumbered_copper_pad(
    tmp_path: Path,
) -> None:
    root, board, config, _hashes = _project(tmp_path)
    source = board.read_text(encoding="utf-8").replace('(pad "2" smd', '(pad "" smd', 1)
    board.write_text(source, encoding="utf-8")

    (candidate,) = _scan(root, config, {BOARD: digest(board)})

    assert candidate.rule_id == RULE_ID
    assert candidate.subject.endswith(":J1.unnumbered-copper-pad-2")
    assert "unnumbered copper pad 2" in candidate.message
    assert candidate.evidence["pad_number"] == ("<unnumbered>",)
    assert candidate.evidence["pad_index"] == ("2",)
    assert candidate.evidence["assigned_pad_numbers"] == ("1",)


def test_extra_pad_is_not_covered_by_schematic_pad_net_comparison(tmp_path: Path) -> None:
    root, _board, config, hashes = _project(tmp_path)
    observed = _observed()
    board_snapshot = snapshot(
        "J1",
        footprint_by_reference={"J1": FOOTPRINT},
        pad_net_by_reference={"J1.1": "SIGNAL", "J1.2": None},
    )

    assert compare_schematic_pcb_pad_nets(observed, board_snapshot) == ()
    (candidate,) = _scan(root, config, hashes, observed=observed)
    assert candidate.evidence["pad_number"] == ("2",)


def test_known_unconnected_schematic_pin_is_not_duplicated(tmp_path: Path) -> None:
    root, _board, config, hashes = _project(tmp_path)
    observed = netlist(
        components={"J1": FOOTPRINT},
        nets={"SIGNAL": ("J1.1", "J1.2")},
        component_pin_numbers={"J1": ("1", "2")},
    )
    board_snapshot = snapshot(
        "J1",
        footprint_by_reference={"J1": FOOTPRINT},
        pad_net_by_reference={"J1.1": "SIGNAL", "J1.2": None},
    )

    (known_pin_mismatch,) = compare_schematic_pcb_pad_nets(observed, board_snapshot)
    assert known_pin_mismatch.reference == "J1"
    assert known_pin_mismatch.pin == "2"
    assert _scan(root, config, hashes, observed=observed) == ()


def test_duplicate_pad_numbers_are_outside_the_predicate(tmp_path: Path) -> None:
    root, board, config, _hashes = _project(tmp_path)
    source = board.read_text(encoding="utf-8").replace('(pad "1" smd', '(pad "2" smd', 1)
    board.write_text(source, encoding="utf-8")

    assert _scan(root, config, {BOARD: digest(board)}) == ()


def test_assigned_pads_and_non_suspicious_footprints_are_controls(tmp_path: Path) -> None:
    root, _board, config, hashes = _project(tmp_path, "control")
    assert _scan(root, config, hashes) == ()

    root, board, config, _hashes = _project(tmp_path / "all-netless")
    source = board.read_text(encoding="utf-8")
    source = source.replace('(net 1 "SIGNAL"))\n    (pad "2"', '(net 0 ""))\n    (pad "2"', 1)
    board.write_text(source, encoding="utf-8")
    assert _scan(root, config, {BOARD: digest(board)}) == ()

    root, board, config, _hashes = _project(tmp_path / "unnumbered-assigned", "control")
    source = board.read_text(encoding="utf-8").replace('(pad "2" smd', '(pad "" smd', 1)
    board.write_text(source, encoding="utf-8")
    assert _scan(root, config, {BOARD: digest(board)}) == ()


@pytest.mark.parametrize(
    "change",
    (
        "(attr smd dnp)",
        "(attr smd board_only)",
    ),
)
def test_board_only_dnp_and_non_copper_pads_are_controls(
    tmp_path: Path,
    change: str,
) -> None:
    root, board, config, _hashes = _project(tmp_path)
    source = board.read_text(encoding="utf-8").replace(
        '(property "Reference" "J1"', f'{change}\n    (property "Reference" "J1"', 1
    )
    board.write_text(source, encoding="utf-8")
    assert _scan(root, config, {BOARD: digest(board)}) == ()

    root, board, config, _hashes = _project(tmp_path / "non-copper")
    source = board.read_text(encoding="utf-8").replace(
        '(layers "F.Cu" "F.Mask") (net 0 ""))', '(layers "F.Mask") (net 0 ""))', 1
    )
    board.write_text(source, encoding="utf-8")
    assert _scan(root, config, {BOARD: digest(board)}) == ()


def test_review_block_off_and_exact_ignore_are_project_configurable(tmp_path: Path) -> None:
    root, _board, config, hashes = _project(tmp_path)
    (candidate,) = _scan(root, config, hashes)
    observed = _observed()

    reviewed = _evaluate(observed, (candidate,))
    assert reviewed.status == "REVIEW"
    assert tuple(item.rule_id for item in reviewed.findings) == (RULE_ID,)

    blocked = _evaluate(
        observed,
        (candidate,),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="release"),)
        ),
    )
    assert blocked.status == "FAIL"

    disabled = _evaluate(
        observed,
        (candidate,),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="approved"),)
        ),
    )
    assert disabled.status == "PASS"

    ignored = _evaluate(
        observed,
        (candidate,),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint(candidate),
                    reason="reviewed connector mounting pad",
                ),
            )
        ),
    )
    assert ignored.findings[0].disposition == "IGNORED"


@pytest.mark.parametrize(
    "version,kind",
    (
        ("10.0.4", ProjectKind.PCB),
        ("11.0.0", ProjectKind.PCB),
        ("10.0.5", ProjectKind.SCHEMATIC),
        ("10.0.5", ProjectKind.PCB_ONLY),
    ),
)
def test_unmeasured_versions_and_projects_without_authoritative_pcb_schematic_are_outside_scope(
    tmp_path: Path,
    version: str,
    kind: ProjectKind,
) -> None:
    root, _board, config, hashes = _project(tmp_path, version=version, kind=kind)
    assert _scan(root, config, hashes) == ()


def test_stale_board_hash_is_rejected_and_uninventoried_source_is_not_scanned(
    tmp_path: Path,
) -> None:
    root, _board, config, _hashes = _project(tmp_path)

    assert _scan(root, config, {}) == ()
    with pytest.raises(ValueError, match="differs from the source-bound hashes"):
        _scan(root, config, {BOARD: "0" * 64})


def test_irrelevant_source_edit_preserves_candidate_identity_and_refreshes_hash(
    tmp_path: Path,
) -> None:
    root, board, config, hashes = _project(tmp_path)
    (before,) = _scan(root, config, hashes)
    board.write_bytes(board.read_bytes() + b"\n# harmless source comment\n")

    (after,) = _scan(root, config, {BOARD: digest(board)})

    assert after.subject == before.subject
    assert after.evidence["source_sha256"] == (digest(board),)
    assert after.evidence["source_sha256"] != before.evidence["source_sha256"]


def test_assigning_only_the_candidate_pad_clears_the_finding(tmp_path: Path) -> None:
    root, board, config, hashes = _project(tmp_path)
    (fault,) = _scan(root, config, hashes)
    source = board.read_text(encoding="utf-8").replace(
        '(net 0 "")))\n  (gr_line', '(net 2 "RETURN")))\n  (gr_line', 1
    )
    source = source.replace(
        '(net 0 "") (net 1 "SIGNAL")',
        '(net 0 "") (net 1 "SIGNAL") (net 2 "RETURN")',
        1,
    )
    board.write_text(source, encoding="utf-8")

    assert _scan(root, config, {BOARD: digest(board)}) == ()
    assert fault.evidence["pad_number"] == ("2",)


def test_assigning_only_an_unnumbered_candidate_pad_clears_the_finding(
    tmp_path: Path,
) -> None:
    root, board, config, _hashes = _project(tmp_path)
    source = board.read_text(encoding="utf-8").replace('(pad "2" smd', '(pad "" smd', 1)
    board.write_text(source, encoding="utf-8")
    (fault,) = _scan(root, config, {BOARD: digest(board)})

    source = board.read_text(encoding="utf-8").replace(
        '(net 0 "")))\n  (gr_line', '(net 2 "RETURN")))\n  (gr_line', 1
    )
    source = source.replace(
        '(net 0 "") (net 1 "SIGNAL")',
        '(net 0 "") (net 1 "SIGNAL") (net 2 "RETURN")',
        1,
    )
    board.write_text(source, encoding="utf-8")

    assert fault.evidence["pad_number"] == ("<unnumbered>",)
    assert _scan(root, config, {BOARD: digest(board)}) == ()
