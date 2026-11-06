"""Source-bound input and population reconciliation for cross-probe exports."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import cast

import pytest

from kicad_tooling.hwrepo.cross_probe_board import BoardFootprintAnchor
from kicad_tooling.hwrepo.cross_probe_reconciliation import (
    CrossProbeLocationEvidence,
    CrossProbePopulationInput,
    reconcile_cross_probe_population,
)
from kicad_tooling.hwrepo.cross_probe_schematic_models import SchematicSymbolAnchor
from kicad_tooling.hwrepo.cross_probe_variant import VariantObservation
from kicad_tooling.hwrepo.findings_view_models import ReviewDrawing
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract
from kicad_tooling.hwrepo.purchasing_models import PurchasingComponent
from tests.cross_probe_board_support import source_bound_board_marker_resolution
from tests.cross_probe_schematic_support import (
    source_bound_anchor_resolution,
    source_bound_drawing_resolution,
)


def test_location_evidence_copies_and_freezes_its_source_indexes() -> None:
    board_path = "projects/demo/kicad/demo.kicad_pcb"
    schematic_path = "projects/demo/kicad/demo.kicad_sch"
    board_anchor = BoardFootprintAnchor("R1", "Resistor_SMD:R_0805", 1.0, 2.0, "F.Cu")
    schematic_anchor = SchematicSymbolAnchor(
        "R1", schematic_path, "/root", (), "symbol-uuid", 3.0, 4.0
    )
    source_hashes = {board_path: "a" * 64, schematic_path: "b" * 64}
    board_anchors = {"r1": (board_anchor,)}
    schematic_anchors = {"r1": (schematic_anchor,)}
    drawing = ReviewDrawing(
        kind="schematic",
        file="sheet.svg",
        source_artifact="schematic/demo.svg",
        sha256="c" * 64,
        width_mm=100.0,
        height_mm=80.0,
        mapping_supported=True,
        sheet_instance_path="/root",
        schematic_source=schematic_path,
        schematic_source_sha256="b" * 64,
    )
    drawings = {"/root": drawing}

    locations = CrossProbeLocationEvidence(
        source_hashes=source_hashes,
        board_marker_resolution=source_bound_board_marker_resolution(
            board_path=board_path,
            board_source_sha256="a" * 64,
            anchors=board_anchors,
        ),
        schematic_anchor_resolution=source_bound_anchor_resolution(
            root_path=schematic_path,
            project_directory="projects/demo/kicad",
            project_name="demo",
            source_hashes={schematic_path: "b" * 64},
            anchors=schematic_anchors,
        ),
        schematic_drawing_resolution=source_bound_drawing_resolution(
            root_source=schematic_path,
            source_hashes={schematic_path: "b" * 64},
            source_drawings=(drawing,),
            drawings_by_instance=drawings,
        ),
    )

    source_hashes["projects/demo/kicad/late.kicad_sch"] = "c" * 64
    board_anchors["r2"] = (board_anchor,)
    schematic_anchors["r2"] = (schematic_anchor,)
    drawings["/later"] = drawing

    assert set(locations.source_hashes) == {board_path, schematic_path}
    assert set(locations.board_anchors) == {"r1"}
    assert set(locations.schematic_anchors) == {"r1"}
    assert set(locations.schematic_drawings) == {"/root"}
    with pytest.raises(TypeError):
        cast(MutableMapping[str, tuple[BoardFootprintAnchor, ...]], locations.board_anchors)[
            "r2"
        ] = ()
    with pytest.raises(TypeError):
        cast(MutableMapping[str, str], locations.source_hashes)["r2"] = "c" * 64


def test_location_evidence_rejects_schematic_resolution_for_stale_source() -> None:
    board_path = "projects/demo/kicad/demo.kicad_pcb"
    schematic_path = "projects/demo/kicad/demo.kicad_sch"
    resolution = source_bound_anchor_resolution(
        root_path=schematic_path,
        project_directory="projects/demo/kicad",
        project_name="demo",
        source_hashes={schematic_path: "b" * 64},
    )

    with pytest.raises(ValueError, match="matching current source hashes"):
        CrossProbeLocationEvidence(
            source_hashes={schematic_path: "c" * 64},
            board_marker_resolution=source_bound_board_marker_resolution(
                board_path=board_path,
                board_source_sha256=None,
            ),
            schematic_anchor_resolution=resolution,
            schematic_drawing_resolution=source_bound_drawing_resolution(
                root_source=schematic_path,
                source_hashes={},
                source_drawings=(),
                drawings_by_instance={},
            ),
        )


def test_location_evidence_rejects_board_markers_for_stale_source() -> None:
    board_path = "projects/demo/kicad/demo.kicad_pcb"
    schematic_path = "projects/demo/kicad/demo.kicad_sch"
    with pytest.raises(ValueError, match="matching current board source hash"):
        CrossProbeLocationEvidence(
            source_hashes={board_path: "c" * 64, schematic_path: "b" * 64},
            board_marker_resolution=source_bound_board_marker_resolution(
                board_path=board_path,
                board_source_sha256="a" * 64,
            ),
            schematic_anchor_resolution=source_bound_anchor_resolution(
                root_path=schematic_path,
                project_directory="projects/demo/kicad",
                project_name="demo",
                source_hashes={schematic_path: "b" * 64},
            ),
            schematic_drawing_resolution=source_bound_drawing_resolution(
                root_source=schematic_path,
                source_hashes={},
                source_drawings=(),
                drawings_by_instance={},
            ),
        )


def test_location_evidence_rejects_schematic_drawing_resolution_for_stale_source() -> None:
    schematic_path = "projects/demo/kicad/demo.kicad_sch"
    drawing = ReviewDrawing(
        kind="schematic",
        file="sheet.svg",
        source_artifact="schematic/demo.svg",
        sha256="c" * 64,
        width_mm=100.0,
        height_mm=80.0,
        mapping_supported=True,
        sheet_instance_path="/root",
        schematic_source=schematic_path,
        schematic_source_sha256="b" * 64,
    )

    with pytest.raises(ValueError, match="matching current source hashes"):
        CrossProbeLocationEvidence(
            source_hashes={
                "projects/demo/kicad/demo.kicad_pcb": "c" * 64,
                schematic_path: "d" * 64,
            },
            board_marker_resolution=source_bound_board_marker_resolution(
                board_path="projects/demo/kicad/demo.kicad_pcb",
                board_source_sha256="c" * 64,
            ),
            schematic_anchor_resolution=source_bound_anchor_resolution(
                root_path=schematic_path,
                project_directory="projects/demo/kicad",
                project_name="demo",
                source_hashes={schematic_path: "d" * 64},
            ),
            schematic_drawing_resolution=source_bound_drawing_resolution(
                root_source=schematic_path,
                source_hashes={schematic_path: "b" * 64},
                source_drawings=(drawing,),
                drawings_by_instance={"/root": drawing},
            ),
        )


def test_population_reconciliation_keeps_variant_origin_and_unmatched_board_refs() -> None:
    board_path = "projects/demo/kicad/demo.kicad_pcb"
    schematic_path = "projects/demo/kicad/demo.kicad_sch"
    locations = CrossProbeLocationEvidence(
        source_hashes={board_path: "a" * 64, schematic_path: "b" * 64},
        board_marker_resolution=source_bound_board_marker_resolution(
            board_path=board_path,
            board_source_sha256="a" * 64,
        ),
        schematic_anchor_resolution=source_bound_anchor_resolution(
            root_path=schematic_path,
            project_directory="projects/demo/kicad",
            project_name="demo",
            source_hashes={schematic_path: "b" * 64},
        ),
        schematic_drawing_resolution=source_bound_drawing_resolution(
            root_source=schematic_path,
            source_hashes={},
            source_drawings=(),
            drawings_by_instance={},
        ),
    )
    parts_component = PurchasingComponent(
        reference="R1", value="1k", footprint="Resistor_SMD:R_0805", dnp=True
    )
    variant_component = PurchasingComponent(
        reference="R2", value="2k", footprint="Resistor_SMD:R_0805"
    )
    variant = VariantObservation(
        name="default",
        netlist_path=Path("build/design-lint/variant.net.xml"),
        lint_path=Path("build/design-lint/variant-review.json"),
        lint_sha256="d" * 64,
        evidence_sha256={"build/design-lint/variant.net.xml": "c" * 64},
        schematic={
            "r1": ComponentContract(value="1k", footprint="Resistor_SMD:R_0805"),
            "r2": ComponentContract(value="2k", footprint="Resistor_SMD:R_0805"),
        },
        schematic_references={"r1": "R1", "r2": "R2"},
        schematic_dnp=frozenset(),
        board_all={"r1": "R1", "r2": "R2", "j8": "J8"},
        board_fitted=frozenset({"r1", "r2", "j8"}),
    )

    result = reconcile_cross_probe_population(
        CrossProbePopulationInput(
            parts_components=(parts_component,),
            variant_components=(parts_component, variant_component),
            locations=locations,
            variant=variant,
        )
    )

    parts_entry, variant_entry = result.entries
    assert parts_entry.origin == "PARTS_PLAN"
    assert parts_entry.population == "DNP"
    assert parts_entry.variant_board == "FITTED"
    assert "Selected PCB variant fits a parts-plan excluded reference." in parts_entry.issues
    assert variant_entry.reference == "R2"
    assert variant_entry.origin == "VARIANT_NATIVE"
    assert variant_entry.variant_schematic == "FITTED"
    assert variant_entry.variant_board == "FITTED"
    assert result.board_only == ("J8",)


def test_variant_only_components_require_variant_observation() -> None:
    component = PurchasingComponent(reference="R2", value="2k", footprint="Resistor_SMD:R_0805")
    locations = CrossProbeLocationEvidence(
        source_hashes={},
        board_marker_resolution=source_bound_board_marker_resolution(
            board_path="projects/demo/kicad/demo.kicad_pcb",
            board_source_sha256=None,
        ),
        schematic_anchor_resolution=source_bound_anchor_resolution(
            root_path="projects/demo/kicad/demo.kicad_sch",
            project_directory="projects/demo/kicad",
            project_name="demo",
            source_hashes={},
        ),
        schematic_drawing_resolution=source_bound_drawing_resolution(
            root_source="projects/demo/kicad/demo.kicad_sch",
            source_hashes={},
            source_drawings=(),
            drawings_by_instance={},
        ),
    )

    with pytest.raises(ValueError, match="Variant components require"):
        CrossProbePopulationInput(
            parts_components=(),
            variant_components=(component,),
            locations=locations,
            variant=None,
        )
