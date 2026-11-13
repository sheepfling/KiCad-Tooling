"""Guard the typed source inventory across the PCB DRC evidence route."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import get_args, get_origin

import pytest

from kicad_tooling.hwrepo.model_primitives import Digest, RepositoryPath
from kicad_tooling.hwrepo.pcb_board_source_binding import pcb_board_source_matches
from kicad_tooling.hwrepo.source_state_models import SourceHashInventory

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.architecture,
]

_ROOT = Path(__file__).parents[1]
_MODULES = (
    "design_lint_pcb_coverage_policy.py",
    "design_lint_pcb_geometry_coverage_policy.py",
    "pcb_board_source_binding.py",
    "pcb_drc_exclusion_review.py",
    "pcb_drc_global_severity_review.py",
    "pcb_drc_source_evidence.py",
    "pcb_drc_source_scan.py",
    "pcb_dru_rule_review.py",
    "pcb_mechanical_edge_clearance.py",
    "pcb_track_angle.py",
)


def test_source_hash_inventory_names_repository_paths_and_digests() -> None:
    assert get_origin(SourceHashInventory) is Mapping
    assert get_args(SourceHashInventory) == (RepositoryPath, Digest)


def test_pcb_drc_route_uses_the_shared_inventory_type() -> None:
    package = _ROOT / "kicad_tooling/hwrepo"
    for name in _MODULES:
        path = package / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "source_state_models"
            and any(alias.name == "SourceHashInventory" for alias in node.names)
            for node in tree.body
        ), f"{name} must use the shared source inventory owner"
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                if argument.arg == "source_hashes":
                    assert isinstance(argument.annotation, ast.Name)
                    assert argument.annotation.id == "SourceHashInventory"


def test_board_binding_keeps_exact_path_and_digest_match_semantics() -> None:
    board_path: RepositoryPath = "projects/controller/controller.kicad_pcb"
    current_digest: Digest = "a" * 64
    stale_digest: Digest = "b" * 64

    assert pcb_board_source_matches(board_path, current_digest, {board_path: current_digest})
    assert not pcb_board_source_matches(board_path, stale_digest, {board_path: current_digest})
    assert not pcb_board_source_matches(board_path, current_digest, {})
