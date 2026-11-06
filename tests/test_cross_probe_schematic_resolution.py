"""Source-bound completeness and context for cross-probe schematic anchors."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.cross_probe_schematic import (
    schematic_drawing_bindings,
    schematic_symbol_anchors,
)
from kicad_tooling.hwrepo.findings_view_models import ReviewDrawing
from kicad_tooling.hwrepo.schematic_geometry_models import (
    SchematicSourceFile,
    VerifiedSchematicSourceTree,
)
from kicad_tooling.hwrepo.schematic_geometry_source import source_tree_sha256
from tests.cross_probe_schematic_support import (
    CHILD_PATH,
    PROJECT_DIRECTORY,
    ROOT_PATH,
    cross_probe_fixture_tree,
)

pytestmark = [pytest.mark.architecture, pytest.mark.evidence_lint]


def test_anchor_resolution_binds_visited_sources_and_freezes_the_index() -> None:
    fixture_tree = cross_probe_fixture_tree()
    unused_contents = b"(kicad_sch)"
    source_tree = VerifiedSchematicSourceTree(
        root_path=fixture_tree.root_path,
        project_directory=fixture_tree.project_directory,
        source_files=(
            *fixture_tree.source_files,
            SchematicSourceFile(
                source_path="projects/demo/kicad/unused.kicad_sch",
                source_sha256=hashlib.sha256(unused_contents).hexdigest(),
                contents=unused_contents,
            ),
        ),
    )

    resolution = schematic_symbol_anchors(
        source_tree,
        root_path=ROOT_PATH,
        project_directory=PROJECT_DIRECTORY,
        project_name="demo",
    )

    assert resolution.status == "COMPLETE"
    assert set(resolution.source_hashes) == {ROOT_PATH, CHILD_PATH}
    assert resolution.source_tree_sha256 == source_tree_sha256(resolution.source_hashes)
    assert resolution.anchors_by_casefolded_reference["r1"]
    with pytest.raises(TypeError):
        resolution.anchors_by_casefolded_reference["r3"] = ()  # type: ignore[index]
    with pytest.raises(TypeError):
        resolution.source_hashes["projects/demo/kicad/other.kicad_sch"] = "f" * 64  # type: ignore[index]


def test_anchor_resolution_keeps_hierarchy_issues_as_partial_evidence() -> None:
    resolution = schematic_symbol_anchors(
        cross_probe_fixture_tree(),
        root_path=ROOT_PATH,
        project_directory=PROJECT_DIRECTORY,
        project_name="different-project",
    )

    assert resolution.status == "PARTIAL"
    assert resolution.issues
    assert set(resolution.source_hashes) == {ROOT_PATH, CHILD_PATH}


def test_missing_root_is_explicitly_blocked() -> None:
    resolution = schematic_symbol_anchors(
        None,
        root_path=ROOT_PATH,
        project_directory=PROJECT_DIRECTORY,
        project_name="demo",
    )

    assert resolution.status == "BLOCKED"
    assert not resolution.source_hashes
    assert not resolution.anchors_by_casefolded_reference
    assert resolution.issues == ("Root schematic source is unavailable.",)


@pytest.mark.parametrize(
    ("root_path", "project_directory"),
    (
        ("projects/demo/kicad/other.kicad_sch", PROJECT_DIRECTORY),
        (ROOT_PATH, "projects/elsewhere"),
    ),
)
def test_anchor_resolution_rejects_a_mismatched_source_tree_context(
    root_path: str,
    project_directory: str,
) -> None:
    with pytest.raises(ValueError, match="does not match"):
        schematic_symbol_anchors(
            cross_probe_fixture_tree(),
            root_path=root_path,
            project_directory=project_directory,
            project_name="demo",
        )


def test_drawing_binding_retains_child_source_identity_and_freezes_index() -> None:
    source_sha256 = "a" * 64
    drawing = ReviewDrawing(
        kind="schematic",
        file="power-a.svg",
        source_artifact="schematic/power-a.svg",
        sha256="b" * 64,
        width_mm=100.0,
        height_mm=80.0,
        mapping_supported=True,
        sheet_instance_path="/root/child-instance",
        sheet_path=("Power A",),
        schematic_source=CHILD_PATH,
        schematic_source_sha256=source_sha256,
    )

    resolution = schematic_drawing_bindings(
        (drawing,),
        {CHILD_PATH: source_sha256},
        root_source=ROOT_PATH,
        legacy_root_instance=None,
    )

    assert resolution.status == "COMPLETE"
    assert resolution.drawings_by_instance == {"/root/child-instance": drawing}
    assert resolution.source_drawings == (drawing,)
    assert resolution.source_hashes == {CHILD_PATH: source_sha256}
    assert resolution.source_inventory_sha256 == source_tree_sha256(resolution.source_hashes)
    with pytest.raises(TypeError):
        resolution.drawings_by_instance["/other"] = drawing  # type: ignore[index]


def test_stale_child_drawing_binding_is_partial_and_keeps_current_source_hash() -> None:
    drawing = ReviewDrawing(
        kind="schematic",
        file="power-a.svg",
        source_artifact="schematic/power-a.svg",
        sha256="b" * 64,
        width_mm=100.0,
        height_mm=80.0,
        mapping_supported=True,
        sheet_instance_path="/root/child-instance",
        schematic_source=CHILD_PATH,
        schematic_source_sha256="c" * 64,
    )
    current_sha256 = "d" * 64

    resolution = schematic_drawing_bindings(
        (drawing,),
        {CHILD_PATH: current_sha256},
        root_source=ROOT_PATH,
        legacy_root_instance=None,
    )

    assert resolution.status == "PARTIAL"
    assert not resolution.drawings_by_instance
    assert resolution.source_hashes == {CHILD_PATH: current_sha256}
    assert resolution.issues == (f"Schematic drawing {drawing.file} has stale source binding.",)


def test_duplicate_instance_drawings_are_partial_and_unbound() -> None:
    source_sha256 = "a" * 64
    drawing = ReviewDrawing(
        kind="schematic",
        file="power-a.svg",
        source_artifact="schematic/power-a.svg",
        sha256="b" * 64,
        width_mm=100.0,
        height_mm=80.0,
        mapping_supported=True,
        sheet_instance_path="/root/child-instance",
        schematic_source=CHILD_PATH,
        schematic_source_sha256=source_sha256,
    )

    resolution = schematic_drawing_bindings(
        (drawing, drawing),
        {CHILD_PATH: source_sha256},
        root_source=ROOT_PATH,
        legacy_root_instance=None,
    )

    assert resolution.status == "PARTIAL"
    assert not resolution.drawings_by_instance
    assert resolution.issues == (
        "Multiple schematic drawings claim sheet instance /root/child-instance.",
    )


def test_legacy_root_svg_binding_uses_current_root_hash() -> None:
    source_sha256 = "a" * 64
    drawing = ReviewDrawing(
        kind="schematic",
        file="root.svg",
        source_artifact="legacy/rendered/root.svg",
        sha256="b" * 64,
        width_mm=100.0,
        height_mm=80.0,
        mapping_supported=True,
    )

    resolution = schematic_drawing_bindings(
        (drawing,),
        {ROOT_PATH: source_sha256},
        root_source=ROOT_PATH,
        legacy_root_instance="/root-instance",
    )

    assert resolution.status == "COMPLETE"
    assert resolution.drawings_by_instance == {"/root-instance": drawing}
    assert resolution.source_hashes == {ROOT_PATH: source_sha256}


def test_no_schematic_drawings_is_not_requested() -> None:
    pcb_drawing = ReviewDrawing(
        kind="pcb",
        file="board.svg",
        source_artifact="pcb/board.svg",
        sha256="b" * 64,
        width_mm=100.0,
        height_mm=80.0,
        mapping_supported=True,
    )

    resolution = schematic_drawing_bindings(
        (pcb_drawing,),
        {},
        root_source=ROOT_PATH,
        legacy_root_instance=None,
    )

    assert resolution.status == "NOT_REQUESTED"
    assert not resolution.source_hashes
    assert not resolution.drawings_by_instance
    assert not resolution.issues
