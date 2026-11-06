"""Part-selection and CAD plans share one source-precondition owner."""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from pathlib import Path
from typing import cast

import pytest

from kicad_tooling.hwrepo import (
    auto_cad,
    cad_library,
    model_population,
    model_population_sources,
    part_selection_sources,
)
from kicad_tooling.hwrepo.cad_source_models import CadImportPlan
from kicad_tooling.hwrepo.model_primitives import Digest, RepositoryPath
from kicad_tooling.hwrepo.models import AutoCadPlan, PartSelectionMap
from kicad_tooling.hwrepo.part_selection_sources import (
    PartCadSourceSnapshot,
    capture_part_cad_source_snapshot,
    require_part_cad_source_snapshot_current,
)
from tests.support import reference_root

pytestmark = [pytest.mark.architecture, pytest.mark.template_checkout]


def test_cad_operations_import_the_shared_source_owner() -> None:
    assert model_population.ModelSourceResolution is model_population_sources.ModelSourceResolution
    assert model_population.resolve_model_source_path is (
        model_population_sources.resolve_model_source_path
    )
    assert part_selection_sources.__file__ is not None
    owner_path = Path(part_selection_sources.__file__)
    assert len(owner_path.read_text(encoding="utf-8").splitlines()) < 500
    assert part_selection_sources.PartCadSourceSnapshot is PartCadSourceSnapshot
    source_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    source_imports = {
        node.module for node in ast.walk(source_tree) if isinstance(node, ast.ImportFrom)
    }
    assert "model_population_sources" in source_imports

    for module in (auto_cad, cad_library):
        assert module.__file__ is not None
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imports = {node.module for node in tree.body if isinstance(node, ast.ImportFrom)}
        assert "part_selection_sources" in imports
        assert "part_picker" not in imports

    source_owner = Path(model_population_sources.__file__)
    assert len(source_owner.read_text(encoding="utf-8").splitlines()) < 500


def test_source_snapshot_keeps_project_identity_and_absence_state() -> None:
    root = reference_root()
    snapshot = capture_part_cad_source_snapshot(root, "controller")
    preferences = "examples/projects/controller/docs/purchasing.json"

    assert snapshot.project_id == "controller"
    assert snapshot.preconditions[preferences] is None
    with pytest.raises(TypeError):
        cast(MutableMapping[RepositoryPath, Digest | None], snapshot.preconditions)[preferences] = (
            "a" * 64
        )
    with pytest.raises(ValueError, match="belongs to another project"):
        require_part_cad_source_snapshot_current(
            root,
            "another-project",
            PartCadSourceSnapshot(project_id="controller", preconditions=snapshot.preconditions),
        )

    preference_path = root / preferences
    preference_text = '{"schema_version":"1"}\n'
    assert not preference_path.exists()
    try:
        preference_path.write_text(preference_text, encoding="utf-8")
        with pytest.raises(ValueError, match="purchasing.json"):
            require_part_cad_source_snapshot_current(root, "controller", snapshot)
    finally:
        if (
            preference_path.is_file()
            and preference_path.read_text(encoding="utf-8") == preference_text
        ):
            preference_path.unlink()


def test_plan_maps_stay_read_only_and_keep_the_same_json_object_shape() -> None:
    preconditions: dict[RepositoryPath, Digest | None] = {"docs/optional.json": None}
    after_hashes: dict[RepositoryPath, Digest] = {"docs/output.json": "a" * 64}
    plans = (
        PartSelectionMap(project_id="controller", preconditions=preconditions),
        AutoCadPlan(
            project_id="controller", preconditions=preconditions, after_hashes=after_hashes
        ),
        CadImportPlan(
            project_id="controller",
            bundle_dir="build/cad-bundle",
            bundle_sha256="b" * 64,
            preconditions=preconditions,
            after_hashes=after_hashes,
        ),
    )

    for plan in plans:
        serialized = plan.model_dump(mode="json")
        assert serialized["preconditions"] == preconditions
        assert serialized["preconditions"]["docs/optional.json"] is None
        with pytest.raises(TypeError):
            cast(MutableMapping[str, object], plan.preconditions)["later"] = None

    preconditions["docs/optional.json"] = "c" * 64
    assert plans[0].preconditions["docs/optional.json"] is None
