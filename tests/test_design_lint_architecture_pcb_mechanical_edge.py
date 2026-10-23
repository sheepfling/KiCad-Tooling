"""Protect the mechanical-edge policy models' PCB theme ownership."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_mechanical_edge_models import (
    PcbMechanicalEdgeClearanceMap,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
]

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "kicad_tooling/hwrepo/pcb_mechanical_edge_models.py"


def test_mechanical_edge_models_remain_in_their_theme_owner() -> None:
    source = OWNER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(OWNER))
    model_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}

    assert len(source.splitlines()) < 500
    assert model_names == {
        "PcbMechanicalEdgeClearanceMap",
        "PcbMechanicalEdgeClearanceRequirement",
    }
    assert DesignLintPolicy.model_fields["pcb_mechanical_edge_clearance_map"].annotation in {
        PcbMechanicalEdgeClearanceMap | None,
    }


def test_policy_imports_mechanical_edge_models_from_the_pcb_owner() -> None:
    source = (ROOT / "kicad_tooling/hwrepo/design_lint_policy_models.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imports = {
        node.module: tuple(alias.name for alias in node.names)
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert imports["pcb_mechanical_edge_models"] == ("PcbMechanicalEdgeClearanceMap",)
    assert "PcbMechanicalEdgeClearanceMap" not in imports.get("models", ())
