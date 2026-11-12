"""Source-bound reviews for malformed PCB netclass inventories."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_malformed_netclass_inventory import (
    PcbMalformedNetClassInventory,
    configured_pcb_malformed_netclass_inventory,
)
from kicad_tooling.hwrepo.pcb_drc_malformed_netclass_inventory_review import (
    PcbMalformedNetClassInventoryCandidate,
    source_bound_pcb_malformed_netclass_inventory_candidates,
)

RULE_ID = "pcb.drc_malformed_netclass_inventory"
PROJECT_RELATIVE = "projects/board.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings"
FAULT_FIXTURES = {
    "fault-netclass-classes-object.kicad_pro": (
        "c53ce061e4b5718bd5145851d59210036381dbb87e62b1e9993d6da9a3544136",
        "net_settings.classes",
        "classes_not_array",
        "object",
        None,
    ),
    "fault-netclass-class-entry-null.kicad_pro": (
        "edcd031ad5bb8db7d79d003a09fd572bb0a2088da3c2963d6c5af4b79d575edf",
        "net_settings.classes[1]",
        "entry_not_object",
        "null",
        1,
    ),
    "fault-netclass-class-entry-missing-name.kicad_pro": (
        "f7cdfb2ed83f4c9d756e8ce324501149a3bae098952517e8c3038afdaef7281d",
        "net_settings.classes[1]",
        "entry_missing_name",
        "object",
        1,
    ),
}
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
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=PROJECT_RELATIVE, kicad_version=kicad_version),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return source_bound_pcb_malformed_netclass_inventory_candidates(
        root,
        config,
        source_hashes,
    )


@pytest.mark.parametrize(
    ("fixture", "expected"),
    tuple(FAULT_FIXTURES.items()),
)
def test_malformed_inventory_fixtures_are_source_hashed_and_reviewed(
    tmp_path: Path,
    fixture: str,
    expected: tuple[str, str, str, str, int | None],
) -> None:
    source = FIXTURES / fixture
    source_hash, location, problem, observed_type, entry_index = expected
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash

    root, project, config, hashes = _project(tmp_path, fixture)
    (candidate,) = _scan(root, config, hashes)

    assert isinstance(candidate, PcbMalformedNetClassInventoryCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{PROJECT_RELATIVE}#{location}"
    assert candidate.source_evidence.source_sha256 == digest(project)
    expected_evidence = {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "location": (location,),
        "problem": (problem,),
        "observed_json_type": (observed_type,),
    }
    if entry_index is not None:
        expected_evidence["entry_index"] = (str(entry_index),)
    assert candidate.evidence == expected_evidence


@pytest.mark.parametrize(
    ("classes", "problem", "observed_type", "index"),
    (
        (None, "classes_not_array", "null", None),
        (True, "classes_not_array", "boolean", None),
        (17, "classes_not_array", "number", None),
        ("classes", "classes_not_array", "string", None),
        ({}, "classes_not_array", "object", None),
        ([None, False, 17, "entry", []], "entry_not_object", "null", 0),
        ([None, False, 17, "entry", []], "entry_not_object", "boolean", 1),
        ([None, False, 17, "entry", []], "entry_not_object", "number", 2),
        ([None, False, 17, "entry", []], "entry_not_object", "string", 3),
        ([None, False, 17, "entry", []], "entry_not_object", "array", 4),
        ([{}], "entry_missing_name", "object", 0),
    ),
)
def test_json_shapes_retain_problem_type_and_index(
    classes: object,
    problem: str,
    observed_type: str,
    index: int | None,
) -> None:
    source = json.loads(
        (FIXTURES / "control-netclass-assignment-array-narrow.kicad_pro").read_text(
            encoding="utf-8"
        )
    )
    source["net_settings"]["classes"] = classes

    items = configured_pcb_malformed_netclass_inventory(json.dumps(source))
    item = next(item for item in items if item.entry_index == index)

    assert item.problem == problem
    assert item.observed_json_type == observed_type
    assert item.entry_index == index


@pytest.mark.parametrize(
    "fixture",
    (
        "control-netclass-assignment-array-narrow.kicad_pro",
        "control-netclass-assignment-default.kicad_pro",
        "control-netclass-assignment-array-empty.kicad_pro",
    ),
)
def test_valid_class_array_controls_stay_quiet(tmp_path: Path, fixture: str) -> None:
    root, _, config, hashes = _project(tmp_path, fixture)

    assert _scan(root, config, hashes) == ()


def test_incomplete_or_ambiguous_class_inventory_stays_quiet() -> None:
    document = (FIXTURES / "control-netclass-assignment-array-narrow.kicad_pro").read_text(
        encoding="utf-8"
    )
    base = json.loads(document)
    base["net_settings"]["classes"].append({"clearance": 0.05})
    assert len(configured_pcb_malformed_netclass_inventory(json.dumps(base))) == 1

    duplicate_classes = document.replace(
        '"netclass_assignments":', '"classes":[],"netclass_assignments":', 1
    )
    assert configured_pcb_malformed_netclass_inventory(duplicate_classes) == ()


def test_unmeasured_versions_and_non_pcb_projects_are_out_of_scope(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-classes-object.kicad_pro",
        kicad_version="10.0.7",
    )
    assert _scan(root, config, hashes) == ()

    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-classes-object.kicad_pro",
        kind=ProjectKind.SCHEMATIC,
    )
    assert _scan(root, config, hashes) == ()


def test_pcb_only_projects_are_supported(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-classes-object.kicad_pro",
        kind=ProjectKind.PCB_ONLY,
    )

    (candidate,) = _scan(root, config, hashes)

    assert candidate.evidence["project_kind"] == (ProjectKind.PCB_ONLY.value,)


def test_stale_source_hash_does_not_produce_candidate(tmp_path: Path) -> None:
    root, _, config, _hashes = _project(
        tmp_path,
        "fault-netclass-classes-object.kicad_pro",
    )

    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, {PROJECT_RELATIVE: "0" * 64})


def test_inventory_record_rejects_inconsistent_problem_fields() -> None:
    with pytest.raises(ValueError, match="non-array"):
        PcbMalformedNetClassInventory(
            location="net_settings.classes",
            problem="classes_not_array",
            observed_json_type="array",
        )
