"""Guard electrical analysis report ownership and compatibility exports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import electrical_report_models, models
from kicad_tooling.hwrepo.source_state_models import SourceState

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]
_MODEL_NAMES = frozenset(
    {
        "ElectricalAnalysisReport",
        "ElectricalCheck",
        "ElectricalInputInventory",
        "ElectricalSetupReport",
        "ElectricalSuiteReport",
    }
)


def _imports(path: Path) -> set[str]:
    return {
        node.module
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }


def test_electrical_report_owner_has_only_evidence_and_primitive_dependencies() -> None:
    owner = _ROOT / "kicad_tooling/hwrepo/electrical_report_models.py"

    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert _imports(owner) == {
        "collections.abc",
        "typing",
        "pydantic",
        "command_evidence_models",
        "model_primitives",
        "source_state_models",
    }


def test_production_consumers_import_electrical_reports_from_the_owner() -> None:
    tooling = _ROOT / "kicad_tooling"
    registry = tooling / "hwrepo/models.py"
    violations: list[str] = []

    for path in tooling.rglob("*.py"):
        if path == registry:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or node.module not in {
                "models",
                "hwrepo.models",
                "kicad_tooling.hwrepo.models",
            }:
                continue
            misplaced = _MODEL_NAMES.intersection(alias.name for alias in node.names)
            if misplaced:
                violations.append(f"{path.relative_to(_ROOT)}:{node.lineno}: {sorted(misplaced)}")

    assert not violations, "Import electrical reports from their owner: " + "; ".join(violations)


def test_registry_exports_preserve_identity_and_source_bound_json() -> None:
    for name in _MODEL_NAMES:
        assert getattr(models, name) is getattr(electrical_report_models, name)

    source = SourceState(
        commit="a" * 40,
        clean=True,
        files_sha256={"projects/board/board.kicad_sch": "b" * 64},
    )
    check = electrical_report_models.ElectricalCheck(
        id="grounding",
        status="PASS",
        detail="All authored schematic reference pins are connected to the named ground net.",
        observed=0.0,
        unit="pins",
    )
    report = electrical_report_models.ElectricalAnalysisReport(
        project_id="board",
        source=source,
        status="PASS",
        checks=(check,),
    )
    suite = electrical_report_models.ElectricalSuiteReport(status="PASS", projects=(report,))
    setup = electrical_report_models.ElectricalSetupReport(
        project_id="board",
        contract="catalog/electrical/board.json",
        changed=("catalog/electrical/board.json",),
        next_actions=("Review the generated requirements before analysis.",),
    )
    inventory = electrical_report_models.ElectricalInputInventory(
        project_id="board",
        run_directory="build/electrical/input-review",
        source_sha256={"projects/board/board.kicad_sch": "b" * 64},
        model_sha256={},
        next_actions=("Review the captured input hashes.",),
    )

    for model in (report, suite, setup, inventory):
        assert type(model).model_validate_json(model.model_dump_json()) == model
