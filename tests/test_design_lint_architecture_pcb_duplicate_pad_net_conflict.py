"""Keep duplicate-pad source parsing and its PCB rule in focused owners."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.catalog_lint,
    pytest.mark.rule_gate_integrity,
]

ROOT = Path(__file__).resolve().parents[1]
RULE_ID = "pcb.duplicate_pad_net_conflict"
OWNER = (
    "kicad_tooling/hwrepo/pcb_duplicate_pad_net_conflicts.py#duplicate_pad_net_conflict_candidates"
)


def _top_level_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    return {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_rule_owner_and_shared_pad_parser_are_bounded() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    owner_path, owner_function = OWNER.split("#", maxsplit=1)
    owner = ROOT / owner_path
    parser = ROOT / "kicad_tooling/hwrepo/pcb_pad_source.py"

    assert rule.theme == "pcb"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert owner_function in _top_level_functions(owner)
    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert len(parser.read_text(encoding="utf-8").splitlines()) < 500


def test_project_inspection_dispatches_the_rule_from_its_owner() -> None:
    source = (ROOT / "kicad_tooling/hwrepo/design_lint_project_inspection.py").read_text(
        encoding="utf-8"
    )

    assert (
        "from .pcb_duplicate_pad_net_conflicts import duplicate_pad_net_conflict_candidates"
        in source
    )
    assert "*duplicate_pad_net_conflict_candidates(" in source


def test_both_source_pad_lints_use_the_shared_parser() -> None:
    unassigned = (ROOT / "kicad_tooling/hwrepo/pcb_unassigned_copper_pad.py").read_text(
        encoding="utf-8"
    )
    conflicts = (ROOT / "kicad_tooling/hwrepo/pcb_duplicate_pad_net_conflicts.py").read_text(
        encoding="utf-8"
    )

    assert "from .pcb_pad_source import source_bound_pcb_footprint_pads" in unassigned
    assert (
        "from .pcb_pad_source import PcbCopperPadSource, source_bound_pcb_footprint_pads"
        in conflicts
    )
    assert 'sexpr_nodes(document, footprint, "pad")' not in unassigned
    assert 'sexpr_nodes(document, footprint, "pad")' not in conflicts
