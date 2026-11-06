"""Guard electrical analysis report ownership and compatibility exports."""

from __future__ import annotations

import ast
from operator import setitem
from pathlib import Path
from typing import Any, cast

import pytest

from kicad_tooling.hwrepo import electrical_report_models, models
from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
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
_INTERNAL_INPUT_BINDING_MODEL_NAMES = frozenset({"BoundElectricalInputs", "ElectricalInputDigest"})


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
        "types",
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
            misplaced = (_MODEL_NAMES | _INTERNAL_INPUT_BINDING_MODEL_NAMES).intersection(
                alias.name for alias in node.names
            )
            if misplaced:
                violations.append(f"{path.relative_to(_ROOT)}:{node.lineno}: {sorted(misplaced)}")

    assert not violations, "Import electrical reports from their owner: " + "; ".join(violations)


def test_electrical_input_binding_models_are_internal_and_read_only() -> None:
    source_path = "projects/board/board.kicad_sch"
    model_path = "projects/board/models/startup.cir"
    bindings = electrical_report_models.BoundElectricalInputs(
        entries=(
            electrical_report_models.ElectricalInputDigest(
                source_path=source_path,
                source_sha256="b" * 64,
                roles=("design-source",),
            ),
            electrical_report_models.ElectricalInputDigest(
                source_path=model_path,
                source_sha256="c" * 64,
                roles=("simulation-model",),
            ),
        )
    )

    assert dict(bindings.all_sha256) == {source_path: "b" * 64, model_path: "c" * 64}
    assert dict(bindings.source_sha256) == {source_path: "b" * 64}
    assert dict(bindings.model_sha256) == {model_path: "c" * 64}
    with pytest.raises(TypeError):
        setitem(cast(Any, bindings.all_sha256), source_path, "d" * 64)
    for name in _INTERNAL_INPUT_BINDING_MODEL_NAMES:
        assert getattr(electrical_report_models, name).__module__ == (
            electrical_report_models.__name__
        )
        assert not hasattr(models, name)


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
    input_sha256 = {"projects/board/board.kicad_sch": "d" * 64}
    artifacts_sha256 = {"build/electrical/requirements.json": "e" * 64}
    command_evidence = CommandEvidence(
        argv=("ngspice", "--version"),
        started_utc="2026-11-05T12:00:00Z",
        returncode=0,
        stdout="ngspice-47",
    )
    commands = {"version": command_evidence}
    report = electrical_report_models.ElectricalAnalysisReport(
        project_id="board",
        source=source,
        status="PASS",
        input_sha256=input_sha256,
        artifacts_sha256=artifacts_sha256,
        commands=commands,
        checks=(check,),
    )
    input_sha256.clear()
    artifacts_sha256.clear()
    commands.clear()
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
        model_sha256={"projects/board/models/startup.cir": "c" * 64},
        next_actions=("Review the captured input hashes.",),
    )

    report_json = report.model_dump(mode="json")
    assert report_json["input_sha256"] == {"projects/board/board.kicad_sch": "d" * 64}
    assert report_json["artifacts_sha256"] == {"build/electrical/requirements.json": "e" * 64}
    assert report_json["commands"]["version"]["stdout"] == "ngspice-47"
    for inventory_map, key in (
        (report.input_sha256, "projects/board/board.kicad_sch"),
        (report.artifacts_sha256, "build/electrical/requirements.json"),
        (report.commands, "version"),
    ):
        with pytest.raises(TypeError):
            setitem(cast(Any, inventory_map), key, "f" * 64)

    inventory_json = inventory.model_dump(mode="json")
    assert inventory_json["source_sha256"] == {"projects/board/board.kicad_sch": "b" * 64}
    assert inventory_json["model_sha256"] == {"projects/board/models/startup.cir": "c" * 64}
    with pytest.raises(TypeError):
        setitem(cast(Any, inventory.source_sha256), "projects/board/board.kicad_sch", "d" * 64)
    with pytest.raises(TypeError):
        setitem(cast(Any, inventory.model_sha256), "projects/board/models/startup.cir", "d" * 64)

    for model in (report, suite, setup, inventory):
        assert type(model).model_validate_json(model.model_dump_json()) == model
