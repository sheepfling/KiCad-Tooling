"""Keep native PCB connectivity evidence models in bounded theme owners."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo import pcb_connectivity_observations, pcb_connectivity_snapshot
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = pytest.mark.design_lint

OBSERVATION_MODEL_NAMES = (
    "PcbAccessProbeObservation",
    "PcbFootprintPlacementObservation",
    "PcbNetTieObservation",
    "PcbPadConnectivityObservation",
    "PcbRuleAreaObservation",
    "PcbRuleAreaPolygonObservation",
    "PcbTrackObservation",
    "PcbTrackUuid",
    "PcbViaObservation",
    "PcbZoneFilledIslandObservation",
    "PcbZoneIdentity",
    "PcbZoneIslandIdentity",
    "PcbZoneObservation",
)


def _top_level_definitions(path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_connectivity_models_have_bounded_theme_owners_and_compatibility_exports() -> None:
    observation_owner = HWREPO / "pcb_connectivity_observations.py"
    snapshot_owner = HWREPO / "pcb_connectivity_snapshot.py"

    assert line_count(observation_owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(snapshot_owner) < IMPLEMENTATION_MAX_LINES
    assert set(OBSERVATION_MODEL_NAMES) <= _top_level_definitions(observation_owner)
    assert {"PcbConnectivitySnapshot"} <= _top_level_definitions(snapshot_owner)
    for name in OBSERVATION_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(pcb_connectivity_observations, name)
    assert (
        shared_models.PcbConnectivitySnapshot is pcb_connectivity_snapshot.PcbConnectivitySnapshot
    )


def test_internal_pcb_services_import_connectivity_models_from_theme_owners() -> None:
    moved_names = {*OBSERVATION_MODEL_NAMES, "PcbConnectivitySnapshot"}
    legacy_imports: list[str] = []
    for path in sorted((REPO_ROOT / "kicad_tooling").rglob("*.py")):
        if path == HWREPO / "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.endswith("models")
                and any(alias.name in moved_names for alias in node.names)
            ):
                legacy_imports.append(path.relative_to(REPO_ROOT).as_posix())

    assert not legacy_imports, (
        "Internal PCB services should import native connectivity types from their theme owners; "
        f"legacy imports: {sorted(set(legacy_imports))}"
    )
