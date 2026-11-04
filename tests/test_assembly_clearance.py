"""Authored box clearance from verified board mesh and assembly placement."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.assembly_clearance import build_assembly_clearance
from kicad_tooling.hwrepo.assembly_clearance_geometry import measure_free_space_box
from kicad_tooling.hwrepo.assembly_clearance_models import (
    AssemblyClearanceContract,
    AssemblyClearanceReport,
    AssemblyFreeSpaceBox,
)
from kicad_tooling.hwrepo.assembly_mesh_surfaces import compare_mesh_surfaces
from kicad_tooling.hwrepo.assembly_review_models import AssemblyPlacement, AssemblyPlacementContract
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.three_d_glb import mesh_triangles, mesh_vertices
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity
from tests.test_assembly_review import inputs

pytestmark = pytest.mark.template_checkout
BOARD = Path(__file__).parent / "fixtures/three_d_board.glb"
ENCLOSURE = Path(__file__).parent / "fixtures/three_d_enclosure.glb"


def _edited_board_glb(tmp_path: Path, change: str) -> Path:
    content = BOARD.read_bytes()
    json_length = struct.unpack_from("<I", content, 12)[0]
    document = json.loads(content[20 : 20 + json_length])
    binary = bytearray(content[28 + json_length :])
    if change == "translated":
        document["nodes"][0]["translation"] = [3, 4, 5]
    elif change == "unreferenced":
        struct.pack_into("<6H", binary, 48, 0, 1, 2, 0, 1, 2)
    elif change == "sparse":
        document["accessors"][0]["sparse"] = {"count": 1}
    elif change == "buffer_extension":
        document["bufferViews"][0]["extensions"] = {"EXT_meshopt_compression": {}}
    else:
        raise AssertionError(change)
    payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
    payload += b" " * (-len(payload) % 4)
    result = (
        struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(payload) + 8 + len(binary))
        + struct.pack("<I4s", len(payload), b"JSON")
        + payload
        + struct.pack("<I4s", len(binary), b"BIN\0")
        + binary
    )
    path = tmp_path / f"{change}.glb"
    path.write_bytes(result)
    return path


def _box(*, x_max: float = -0.010, z_max: float = -0.001) -> AssemblyFreeSpaceBox:
    return AssemblyFreeSpaceBox(
        lower=(-0.014, 0.003, -0.003),
        upper=(x_max, 0.005, z_max),
        basis="Reviewed rectangular free space for the synthetic enclosure fixture",
    )


def _contract(root: Path, island: Path, placement: Path, box: AssemblyFreeSpaceBox) -> Path:
    path = island / "docs/assembly-clearance.json"
    write_model(
        path,
        AssemblyClearanceContract(
            project_id="controller",
            placement_contract_sha256=digest(placement),
            free_space=box,
            required_margin_mm=0.4,
        ),
    )
    return path


def test_mesh_vertices_and_signed_box_margins() -> None:
    vertices = mesh_vertices(BOARD)
    assert len(vertices) == 4
    assert {point[0] for point in vertices} == {-1.0, 1.0}
    placement = AssemblyPlacement(
        source_frame="enclosure-local",
        target_frame="board-export",
        translation_mm=(12.0, -4.0, 2.0),
        rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    )
    clear = measure_free_space_box(
        vertices,
        board_unit="mm",
        enclosure_unit="m",
        placement=placement,
        free_space=_box(),
        required_margin_mm=0.4,
    )
    assert clear.status == "CLEAR_WITHIN_BOX"
    assert clear.minimum_margin_mm == pytest.approx(0.5)
    assert clear.face_margins_mm["z_max"] == pytest.approx(0.5)
    tight = measure_free_space_box(
        vertices,
        board_unit="mm",
        enclosure_unit="m",
        placement=placement,
        free_space=_box(z_max=-0.00145),
        required_margin_mm=0.4,
    )
    assert tight.status == "LOW_CLEARANCE"
    assert tight.minimum_margin_mm == pytest.approx(0.05)
    interference = measure_free_space_box(
        vertices,
        board_unit="mm",
        enclosure_unit="m",
        placement=placement,
        free_space=_box(x_max=-0.012),
        required_margin_mm=0.4,
    )
    assert interference.status == "BOX_INTERFERENCE"
    assert interference.face_margins_mm["x_max"] == pytest.approx(-1.0)


def test_mesh_vertices_follow_scene_transform_and_referenced_indices(tmp_path: Path) -> None:
    translated = mesh_vertices(_edited_board_glb(tmp_path, "translated"))
    assert {point[0] for point in translated} == {2.0, 4.0}
    assert {point[1] for point in translated} == {4.0}
    assert len(mesh_vertices(_edited_board_glb(tmp_path, "unreferenced"))) == 3
    with pytest.raises(ValueError, match="unsupported"):
        mesh_vertices(_edited_board_glb(tmp_path, "sparse"))
    with pytest.raises(ValueError, match="unassessed geometry encoding"):
        mesh_vertices(_edited_board_glb(tmp_path, "buffer_extension"))


def test_box_margin_applies_inverse_enclosure_to_board_rotation() -> None:
    placement = AssemblyPlacement(
        source_frame="enclosure-local",
        target_frame="board-export",
        translation_mm=(0, 0, 0),
        rotation_xyzw=(0, 0, 2**-0.5, 2**-0.5),
    )
    box = AssemblyFreeSpaceBox(
        lower=(-0.5, -1.5, -0.5),
        upper=(0.5, -0.5, 0.5),
        basis="One board point rotated into the enclosure frame",
    )
    result = measure_free_space_box(
        ((1, 0, 0),),
        board_unit="mm",
        enclosure_unit="mm",
        placement=placement,
        free_space=box,
        required_margin_mm=0.4,
    )
    assert result.status == "CLEAR_WITHIN_BOX"
    assert result.minimum_margin_mm == pytest.approx(0.5)


def test_mesh_surfaces_measure_separation_and_crossing() -> None:
    board = mesh_triangles(BOARD)
    enclosure = mesh_triangles(ENCLOSURE)
    separate = compare_mesh_surfaces(
        board,
        enclosure,
        board_unit="mm",
        enclosure_unit="m",
        placement=AssemblyPlacement(
            source_frame="enclosure-local",
            target_frame="board-export",
            translation_mm=(0, 4, 0),
            rotation_xyzw=(0, 0, 0, 1),
        ),
    )
    assert separate.status == "SEPARATED"
    assert separate.minimum_gap_mm == pytest.approx(4.0)
    crossing = compare_mesh_surfaces(
        board,
        enclosure,
        board_unit="mm",
        enclosure_unit="m",
        placement=AssemblyPlacement(
            source_frame="enclosure-local",
            target_frame="board-export",
            translation_mm=(0, 0, 0),
            rotation_xyzw=(0, 0, 2**-0.5, 2**-0.5),
        ),
    )
    assert crossing.status == "INTERSECTING"
    assert crossing.minimum_gap_mm == 0
    assert crossing.first_intersection is not None


def test_mesh_surfaces_keep_coplanar_disjoint_triangles_separate() -> None:
    placement = AssemblyPlacement(
        source_frame="enclosure-local",
        target_frame="board-export",
        translation_mm=(0, 0, 0),
        rotation_xyzw=(0, 0, 0, 1),
    )
    first = (((0, 0, 0), (1, 0, 0), (0, 1, 0)),)
    second = (((2, 0, 0), (3, 0, 0), (2, 1, 0)),)
    result = compare_mesh_surfaces(
        first,
        second,
        board_unit="mm",
        enclosure_unit="mm",
        placement=placement,
    )
    assert result.status == "SEPARATED"
    assert result.minimum_gap_mm == pytest.approx(1.0)


def test_mesh_surface_intersection_overrides_clear_box(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    board_receipt, placement = inputs(root, island)
    original = read_model(placement, AssemblyPlacementContract)
    crossing = AssemblyPlacement(
        source_frame="enclosure-local",
        target_frame="board-export",
        translation_mm=(0, 0, 0),
        rotation_xyzw=(0, 0, 2**-0.5, 2**-0.5),
    )
    write_model(placement, original.model_copy(update={"placement": crossing}))
    clearance = _contract(
        root,
        island,
        placement,
        AssemblyFreeSpaceBox(
            lower=(-0.002, -0.002, -0.001),
            upper=(0.002, 0.002, 0.001),
            basis="Synthetic crossing surfaces inside a broad box",
        ),
    )
    report = build_assembly_clearance(root, "controller", board_receipt, placement, clearance)
    assert report.status == "MESH_SURFACE_INTERSECTION"
    assert report.surface_status == "INTERSECTING"
    assert report.surface_gap_mm == 0
    assert report.minimum_margin_mm is not None and report.minimum_margin_mm > 0


def test_low_mesh_surface_gap_overrides_clear_box(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    board_receipt, placement = inputs(root, island)
    original = read_model(placement, AssemblyPlacementContract)
    near = AssemblyPlacement(
        source_frame="enclosure-local",
        target_frame="board-export",
        translation_mm=(0, 0.05, 0),
        rotation_xyzw=(0, 0, 0, 1),
    )
    write_model(placement, original.model_copy(update={"placement": near}))
    clearance = _contract(
        root,
        island,
        placement,
        AssemblyFreeSpaceBox(
            lower=(-0.002, -0.002, -0.001),
            upper=(0.002, 0.002, 0.001),
            basis="Synthetic separated surfaces inside a broad box",
        ),
    )
    report = build_assembly_clearance(root, "controller", board_receipt, placement, clearance)
    assert report.status == "LOW_SURFACE_GAP"
    assert report.surface_status == "SEPARATED"
    assert report.surface_gap_mm == pytest.approx(0.05)


@pytest.mark.parametrize(
    ("box", "expected"),
    ((_box(), "CLEAR_WITHIN_BOX"), (_box(x_max=-0.012), "BOX_INTERFERENCE")),
)
def test_review_binds_models_contract_and_face_margins(
    tmp_path: Path, box: AssemblyFreeSpaceBox, expected: str
) -> None:
    root, island, _ = parity_workspace(tmp_path)
    board_receipt, placement = inputs(root, island)
    clearance = _contract(root, island, placement, box)
    report = build_assembly_clearance(root, "controller", board_receipt, placement, clearance)
    assert report.status == expected
    assert report.referenced_vertices == 4
    assert not report.fit_certified and not report.enclosure_mesh_clearance_assessed
    assert report.surface_status == "SEPARATED" and report.surface_gap_mm is not None
    directory = Path(report.output_directory)
    assert read_model(directory / "assembly-clearance.json", AssemblyClearanceReport) == report
    assert (directory / "assembly/board.glb").read_bytes() == BOARD.read_bytes()
    html = (directory / "index.html").read_text(encoding="utf-8")
    assert 'src="assembly/index.html"' in html
    assert "Mesh surface gap and intersections" in html
    assert report.clearance_contract_sha256 == digest(clearance)


def test_missing_placement_keeps_box_unassessed(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    board_receipt, placement = inputs(root, island, placement=False)
    clearance = _contract(root, island, placement, _box())
    report = build_assembly_clearance(root, "controller", board_receipt, placement, clearance)
    assert report.status == "UNASSESSED"
    assert report.minimum_margin_mm is None and not report.face_margins_mm
    assert report.surface_status == "UNASSESSED"
    assert any("complete placed assembly" in item for item in report.issues)


def test_changed_enclosure_keeps_box_unassessed(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    board_receipt, placement = inputs(root, island)
    clearance = _contract(root, island, placement, _box())
    enclosure = island / "cad/enclosure.glb"
    enclosure.write_bytes(enclosure.read_bytes() + b"changed")
    report = build_assembly_clearance(root, "controller", board_receipt, placement, clearance)
    assert report.status == "UNASSESSED"
    assert report.minimum_margin_mm is None
    assert report.surface_status == "UNASSESSED"
    assert any("Enclosure GLB differs" in item for item in report.issues)


def test_changed_placement_contract_is_rejected(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    board_receipt, placement = inputs(root, island)
    clearance = _contract(root, island, placement, _box())
    placement.write_bytes(placement.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="does not bind"):
        build_assembly_clearance(root, "controller", board_receipt, placement, clearance)


class _ClearanceParity(McpParityHarness):
    async def _case_clearance(self) -> None:
        board, placement = inputs(self.root, self.island)
        clearance = _contract(self.root, self.island, placement, _box())
        cli = await self.cli(
            "kicad_tooling.assembly_clearance",
            AssemblyClearanceReport,
            "--project",
            "controller",
            "--board-receipt",
            str(board),
            "--placement-contract",
            str(placement),
            "--clearance-contract",
            str(clearance),
            "--output",
            "build/assembly-clearance/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "board_receipt": board.relative_to(self.root).as_posix(),
            "placement_contract": placement.relative_to(self.root).as_posix(),
            "clearance_contract": clearance.relative_to(self.root).as_posix(),
        }
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "export_assembly_clearance", AssemblyClearanceReport, arguments
            )
        self.assertNotEqual(cli.output_directory, mcp.output_directory)
        self.assertEqual(cli.status, mcp.status)
        self.assertEqual(cli.face_margins_mm, mcp.face_margins_mm)
        self.assertEqual(cli.minimum_margin_mm, mcp.minimum_margin_mm)
        cli_viewer = Path(cli.output_directory) / "assembly/index.html"
        mcp_viewer = Path(mcp.output_directory) / "assembly/index.html"
        self.assertEqual(cli_viewer.read_bytes(), mcp_viewer.read_bytes())
        for key in (
            "output_directory",
            "assembly_review",
            "assembly_review_sha256",
            "artifacts_sha256",
        ):
            cli = cli.model_copy(update={key: getattr(mcp, key)})
        self.assertEqual(cli, mcp)


def test_cli_mcp_assembly_clearance_parity() -> None:
    run_mcp_parity(_ClearanceParity, "_case_clearance")
