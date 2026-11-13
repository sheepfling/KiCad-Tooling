"""Source-bound checks for PCB netclass patterns with no current net match."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_netclass_pattern_review import (
    PcbUnmatchedNetClassPatternCandidate,
    source_bound_pcb_netclass_pattern_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_netclass_patterns import unmatched_pcb_netclass_patterns

RULE_ID = "pcb.drc_netclass_pattern_unmatched"
PROJECT_RELATIVE = "projects/controller.kicad_pro"
BOARD_RELATIVE = "projects/controller.kicad_pcb"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings"
BOARD = FIXTURES / "board.kicad_pcb"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str,
    *,
    kicad_version: str = "10.0.8",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    board = root / BOARD_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_bytes((FIXTURES / fixture).read_bytes())
    board.write_bytes(BOARD.read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=PROJECT_RELATIVE, kicad_version=kicad_version),
    )
    return (
        root,
        project,
        board,
        config,
        {
            PROJECT_RELATIVE: digest(project),
            BOARD_RELATIVE: digest(board),
        },
    )


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return source_bound_pcb_netclass_pattern_candidates(root, config, source_hashes)


def test_unmatched_pattern_fixture_has_reviewed_source_hash() -> None:
    source = FIXTURES / "fault-unmatched.kicad_pro"

    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "35abfae4d4c3d4ceb286eee4cd2458a50a19737c4874739875650973cac27ede"
    )


def test_case_mismatch_fixture_has_reviewed_source_hash() -> None:
    source = FIXTURES / "fault-case-mismatch.kicad_pro"

    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "ce1892fa119f1dfb4023a7cc327904c56e265be99d75540bbf9edf6615424e14"
    )


def test_unmatched_pattern_candidate_binds_both_current_sources(tmp_path: Path) -> None:
    root, project, board, config, hashes = _project(tmp_path, "fault-unmatched.kicad_pro")

    (candidate,) = _scan(root, config, hashes)

    assert isinstance(candidate, PcbUnmatchedNetClassPatternCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{PROJECT_RELATIVE}#net_settings/netclass_patterns/0"
    assert candidate.evidence == {
        "project_path": (PROJECT_RELATIVE,),
        "project_sha256": (digest(project),),
        "board_path": (BOARD_RELATIVE,),
        "board_sha256": (digest(board),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "pattern_index": ("0",),
        "pattern": ("GHOST",),
        "netclass": ("Narrow",),
    }
    assert "matches no named net" in candidate.message


@pytest.mark.parametrize(
    "fixture",
    ("control-literal.kicad_pro", "control-wildcard.kicad_pro", "control-regex.kicad_pro"),
)
def test_matching_literal_wildcard_and_regex_patterns_are_controls(
    tmp_path: Path,
    fixture: str,
) -> None:
    root, _, _, config, hashes = _project(tmp_path, fixture)

    assert _scan(root, config, hashes) == ()


def test_pattern_matching_is_case_sensitive_and_retains_source_index(tmp_path: Path) -> None:
    root, _, _, config, hashes = _project(tmp_path, "control-literal.kicad_pro")
    project = root / PROJECT_RELATIVE
    document = json.loads(project.read_text(encoding="utf-8"))
    document["net_settings"]["netclass_patterns"] = [
        {"pattern": "N1", "netclass": "Narrow"},
        {"pattern": "n1", "netclass": "Narrow"},
    ]
    project.write_text(json.dumps(document), encoding="utf-8")
    hashes[PROJECT_RELATIVE] = digest(project)

    (candidate,) = _scan(root, config, hashes)

    assert candidate.evidence["pattern_index"] == ("1",)
    assert candidate.evidence["pattern"] == ("n1",)


def test_default_and_undeclared_class_patterns_are_outside_this_rule() -> None:
    source = json.loads((FIXTURES / "fault-unmatched.kicad_pro").read_text(encoding="utf-8"))
    source["net_settings"]["netclass_patterns"] = [
        {"pattern": "GHOST", "netclass": "Default"},
        {"pattern": "GHOST", "netclass": "MissingClass"},
        {"pattern": 3, "netclass": "Narrow"},
    ]
    findings = unmatched_pcb_netclass_patterns(
        json.dumps(source),
        BOARD.read_text(encoding="utf-8"),
    )

    assert findings == ()


def test_ambiguous_settings_or_board_inventory_stays_quiet() -> None:
    serialized = (FIXTURES / "fault-unmatched.kicad_pro").read_text(encoding="utf-8").strip()
    source = json.loads(serialized)
    duplicate_pattern_field = serialized.replace(
        '"pattern":"GHOST"', '"pattern":"GHOST","pattern":"N1"'
    )
    duplicate_root = serialized[:-1] + ',"net_settings":' + json.dumps(source["net_settings"]) + "}"

    assert unmatched_pcb_netclass_patterns(duplicate_pattern_field, BOARD.read_text()) == ()
    assert unmatched_pcb_netclass_patterns(duplicate_root, BOARD.read_text()) == ()
    assert unmatched_pcb_netclass_patterns(json.dumps(source), "not a PCB expression") == ()


@pytest.mark.parametrize(
    ("version", "kind"),
    (("10.0.5", ProjectKind.PCB), ("10.0.8", ProjectKind.SCHEMATIC)),
)
def test_unmeasured_versions_and_non_pcb_projects_are_out_of_scope(
    tmp_path: Path,
    version: str,
    kind: ProjectKind,
) -> None:
    root, _, _, config, hashes = _project(
        tmp_path,
        "fault-unmatched.kicad_pro",
        kicad_version=version,
        kind=kind,
    )

    assert _scan(root, config, hashes) == ()


def test_missing_board_hash_does_not_create_finding(tmp_path: Path) -> None:
    root, _, _, config, hashes = _project(tmp_path, "fault-unmatched.kicad_pro")
    hashes.pop(BOARD_RELATIVE)

    assert _scan(root, config, hashes) == ()


def test_stale_board_hash_is_rejected(tmp_path: Path) -> None:
    root, _, board, config, hashes = _project(tmp_path, "fault-unmatched.kicad_pro")
    board.write_text(board.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="PCB source differs"):
        _scan(root, config, hashes)
