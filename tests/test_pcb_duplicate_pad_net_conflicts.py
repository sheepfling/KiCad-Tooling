"""Source-bound reviews for conflicting assignments on duplicate PCB pad numbers."""

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
from kicad_tooling.hwrepo.pcb_duplicate_pad_net_conflicts import (
    duplicate_pad_net_conflict_candidates,
)
from tests.design_lint_fixtures.pcb_component_inventory import coach, netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.duplicate_pad_net_conflict"),
]

RULE_ID: DesignLintRuleId = "pcb.duplicate_pad_net_conflict"
PROJECT = "projects/synthetic/controller.kicad_pro"
BOARD = "projects/synthetic/controller.kicad_pcb"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-duplicate-pad-net-conflict"


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


def _netlist(*, pin_numbers: tuple[str, ...] = ("1",)) -> NetlistContract:
    return netlist(
        components={"J1": "Synthetic:TwoPadConnector"},
        nets={"SIGNAL": ("J1.1",)},
        component_pin_numbers={"J1": pin_numbers},
    )


def _scan(
    root: Path,
    config: ProjectConfig,
    source_hashes: dict[str, str],
    observed: NetlistContract | None = None,
) -> tuple[Candidate, ...]:
    return duplicate_pad_net_conflict_candidates(
        root,
        config,
        source_hashes,
        observed or _netlist(),
    )


def _evaluate(
    observed: NetlistContract,
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


def test_different_net_assignments_on_duplicate_schematic_pads_are_reviewed(
    tmp_path: Path,
) -> None:
    root, board, config, hashes = _project(tmp_path)

    (candidate,) = _scan(root, config, hashes)

    assert candidate.rule_id == RULE_ID
    assert candidate.subject.endswith(":J1.1")
    assert candidate.evidence["source_path"] == (BOARD,)
    assert candidate.evidence["source_sha256"] == (digest(board),)
    assert candidate.evidence["reference"] == ("J1",)
    assert candidate.evidence["pad_number"] == ("1",)
    assert candidate.evidence["schematic_pin"] == ("J1.1",)
    assert candidate.evidence["pad_assignments"] == (
        "pad 1, line 17: 1:SIGNAL",
        "pad 2, line 18: 2:RETURN",
    )

    report = _evaluate(_netlist(), (candidate,))
    assert report.status == "REVIEW"
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert "different net assignments" in finding.message


def test_same_net_duplicate_schematic_pads_are_a_control(tmp_path: Path) -> None:
    root, _board, config, hashes = _project(tmp_path, "control")

    assert _scan(root, config, hashes) == ()


def test_assigned_and_unassigned_duplicate_pads_are_reviewed(tmp_path: Path) -> None:
    root, board, config, _hashes = _project(tmp_path)
    source = board.read_text(encoding="utf-8").replace('(net 2 "RETURN")', '(net 0 "")')
    board.write_text(source, encoding="utf-8")

    (candidate,) = _scan(root, config, {BOARD: digest(board)})

    assert candidate.evidence["pad_assignments"] == (
        "pad 1, line 17: 1:SIGNAL",
        "pad 2, line 18: <unassigned>",
    )


def test_unmatched_pad_number_and_non_copper_duplicate_are_controls(tmp_path: Path) -> None:
    root, board, config, hashes = _project(tmp_path)

    assert _scan(root, config, hashes, _netlist(pin_numbers=("2",))) == ()

    source = board.read_text(encoding="utf-8").replace(
        '(pad "1" smd circle (at 2 0) (size 1 1) (layers "F.Cu" "F.Mask") (net 2 "RETURN"))',
        '(pad "1" smd circle (at 2 0) (size 1 1) (layers "F.SilkS"))',
    )
    board.write_text(source, encoding="utf-8")
    assert _scan(root, config, {BOARD: digest(board)}) == ()


@pytest.mark.parametrize("attribute", ("dnp", "board_only"))
def test_dnp_and_board_only_footprints_are_controls(tmp_path: Path, attribute: str) -> None:
    root, board, config, _hashes = _project(tmp_path)
    source = board.read_text(encoding="utf-8").replace(
        "(duplicate_pad_numbers_are_jumpers yes)",
        f"(duplicate_pad_numbers_are_jumpers yes) (attr {attribute})",
    )
    board.write_text(source, encoding="utf-8")

    assert _scan(root, config, {BOARD: digest(board)}) == ()


def test_unknown_version_and_non_pcb_project_are_outside_scope(tmp_path: Path) -> None:
    root, _board, _config, hashes = _project(tmp_path)

    assert (
        _scan(
            root,
            cast(
                ProjectConfig,
                SimpleNamespace(kind=ProjectKind.PCB, project=PROJECT, kicad_version="10.0.8"),
            ),
            hashes,
        )
        == ()
    )
    assert (
        _scan(
            root,
            cast(
                ProjectConfig,
                SimpleNamespace(kind=ProjectKind.PCB_ONLY, project=PROJECT, kicad_version="10.0.5"),
            ),
            hashes,
        )
        == ()
    )


def test_stale_source_hash_is_rejected(tmp_path: Path) -> None:
    root, _board, config, _hashes = _project(tmp_path)

    with pytest.raises(ValueError, match="source differs from the source-bound hashes"):
        _scan(root, config, {BOARD: "0" * 64})


def test_project_policy_can_block_or_ignore_the_exact_candidate(tmp_path: Path) -> None:
    root, _board, config, hashes = _project(tmp_path)
    (candidate,) = _scan(root, config, hashes)
    observed = _netlist()

    blocked = _evaluate(
        observed,
        (candidate,),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic duplicate-pad pin assignment requires review",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    ignored = _evaluate(
        observed,
        (candidate,),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint(candidate),
                    reason="Synthetic same-numbered test pads are intentionally assigned separately",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert ignored.findings[0].disposition == "IGNORED"


def test_assigning_the_duplicate_group_to_one_net_clears_the_finding(tmp_path: Path) -> None:
    root, board, config, _hashes = _project(tmp_path)
    board.write_text(
        board.read_text(encoding="utf-8").replace('(net 2 "RETURN")', '(net 1 "SIGNAL")'),
        encoding="utf-8",
    )

    assert _scan(root, config, {BOARD: digest(board)}) == ()
