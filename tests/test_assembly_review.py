"""Project-owned placement contracts and offline board/enclosure review parity."""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.assembly_review import build_assembly_review
from kicad_tooling.hwrepo.assembly_review_models import (
    AssemblyPlacement,
    AssemblyPlacementContract,
    AssemblyReviewReport,
)
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ModelInventoryReport, ThreeDReport
from kicad_tooling.validate import hashes
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity

pytestmark = pytest.mark.template_checkout

GLB = (Path(__file__).parent / "fixtures/three_d_board.glb").read_bytes()
ENCLOSURE = (Path(__file__).parent / "fixtures/three_d_enclosure.glb").read_bytes()


def inputs(
    root: Path, island: Path, *, placement: bool = True, enclosure: bool = True
) -> tuple[Path, Path]:
    config = load_config(root, "examples/projects/controller/project.json")
    source = hashes(root, config.source_roots)
    board = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    directory = root / "build/3d/assembly-fixture"
    directory.mkdir(parents=True)
    (directory / "board.glb").write_bytes(GLB)
    receipt = ThreeDReport(
        project_id="controller",
        mode="generate",
        status="PASS",
        run_directory=str(directory),
        toolchain_id=config.toolchain_id,
        kicad_version=config.kicad_version,
        board=board,
        source_sha256=source,
        models=ModelInventoryReport(
            project_id="controller",
            board=board,
            status="READY",
            footprints=(),
            findings=(),
            next_actions=(),
        ),
        artifacts_sha256={"board.glb": digest(directory / "board.glb")},
    )
    receipt_path = directory / "visualization.json"
    write_model(receipt_path, receipt)
    model = island / "cad/enclosure.glb"
    model.parent.mkdir(parents=True)
    if enclosure:
        model.write_bytes(ENCLOSURE)
    contract = AssemblyPlacementContract(
        project_id="controller",
        board_glb_sha256=digest(directory / "board.glb"),
        board_frame="board-export",
        board_unit="mm",
        enclosure_model=model.relative_to(root).as_posix(),
        enclosure_sha256=digest(Path(__file__).parent / "fixtures/three_d_enclosure.glb"),
        enclosure_frame="enclosure-local",
        enclosure_unit="m",
        placement=(
            AssemblyPlacement(
                source_frame="enclosure-local",
                target_frame="board-export",
                translation_mm=(12.0, -4.0, 2.0),
                rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
            )
            if placement
            else None
        ),
    )
    contract_path = island / "docs/assembly-placement.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    write_model(contract_path, contract)
    return receipt_path, contract_path


def test_explicit_overlay_retains_exact_models_frames_and_transform(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    receipt, contract = inputs(root, island)
    report = build_assembly_review(
        root, "controller", receipt, contract, Path("build/assembly-review/ready")
    )
    assert report.status == "READY"
    assert not report.fit_certified and not report.interference_assessed
    assert not report.clearance_assessed
    assert report.board_unit == "mm" and report.enclosure_unit == "m"
    assert report.placement is not None
    assert report.placement.translation_mm == (12.0, -4.0, 2.0)
    directory = Path(report.output_directory)
    html = (directory / "index.html").read_text(encoding="utf-8")
    assert 'id="assembly-config"' in html
    assert '"enclosure_unit":"m"' in html
    assert '"translation_mm":[12.0,-4.0,2.0]' in html
    assert 'data-model="enclosure"' in html
    embedded = html.split('<script id="assembly-glb-data" type="application/octet-stream">', 1)[
        1
    ].split("</script>", 1)[0]
    assert base64.b64decode(embedded) == ENCLOSURE
    assert "No interference, clearance, or fit calculation" in html
    assert "https://" not in html and "http://" not in html
    assert read_model(directory / "assembly-review.json", AssemblyReviewReport) == report
    assert all(digest(directory / name) == sha for name, sha in report.artifacts_sha256.items())


@pytest.mark.parametrize("missing", ["placement", "enclosure"])
def test_incomplete_assembly_keeps_board_only(tmp_path: Path, missing: str) -> None:
    root, island, _ = parity_workspace(tmp_path)
    receipt, contract = inputs(
        root, island, placement=missing != "placement", enclosure=missing != "enclosure"
    )
    report = build_assembly_review(root, "controller", receipt, contract)
    assert report.status == "INCOMPLETE" and report.issues
    directory = Path(report.output_directory)
    html = (directory / "index.html").read_text(encoding="utf-8")
    assert 'id="assembly-glb-data"' not in html
    assert 'data-model="enclosure"' not in html
    assert (directory / "board.glb").read_bytes() == GLB
    assert (directory / "enclosure.glb").exists() == (missing == "placement")


def test_stale_and_incompatible_contracts_are_rejected(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    receipt, path = inputs(root, island)
    contract = read_model(path, AssemblyPlacementContract)
    write_model(path, contract.model_copy(update={"board_glb_sha256": "a" * 64}))
    with pytest.raises(ValueError, match="selected board GLB"):
        build_assembly_review(root, "controller", receipt, path)
    write_model(path, contract)
    (island / "kicad/controller.kicad_pcb").write_bytes(
        (island / "kicad/controller.kicad_pcb").read_bytes() + b"\n"
    )
    with pytest.raises(ValueError, match="current source"):
        build_assembly_review(root, "controller", receipt, path)


def test_stale_or_invalid_enclosure_is_reported_without_overlay(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    receipt, path = inputs(root, island)
    model = island / "cad/enclosure.glb"
    model.write_bytes(ENCLOSURE + b"changed")
    stale = build_assembly_review(root, "controller", receipt, path)
    assert stale.status == "INCOMPLETE"
    assert any("differs" in issue for issue in stale.issues)
    model.write_bytes(b"broken glb")
    contract = read_model(path, AssemblyPlacementContract)
    write_model(path, contract.model_copy(update={"enclosure_sha256": digest(model)}))
    invalid = build_assembly_review(root, "controller", receipt, path)
    assert invalid.status == "INCOMPLETE"
    assert any("invalid" in issue for issue in invalid.issues)
    document = json.dumps({"asset": {"version": "2.0"}}).encode("utf-8")
    document += b" " * (-len(document) % 4)
    model.write_bytes(
        struct.pack("<4sII", b"glTF", 2, 20 + len(document))
        + struct.pack("<I4s", len(document), b"JSON")
        + document
    )
    write_model(path, contract.model_copy(update={"enclosure_sha256": digest(model)}))
    empty = build_assembly_review(root, "controller", receipt, path)
    assert empty.status == "INCOMPLETE"
    assert any("empty" in issue for issue in empty.issues)


def test_review_status_retains_overlay_when_board_coverage_is_partial(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    receipt, contract = inputs(root, island)
    saved = read_model(receipt, ThreeDReport)
    assert saved.models is not None
    write_model(
        receipt,
        saved.model_copy(update={"models": saved.models.model_copy(update={"status": "REVIEW"})}),
    )
    report = build_assembly_review(root, "controller", receipt, contract)
    assert report.status == "REVIEW"
    assert (Path(report.output_directory) / "enclosure.glb").is_file()
    assert any("coverage" in issue for issue in report.issues)


def test_generated_model_path_is_not_accepted_as_project_source(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    receipt, path = inputs(root, island)
    contract = read_model(path, AssemblyPlacementContract)
    write_model(
        path,
        contract.model_copy(
            update={"enclosure_model": "examples/projects/controller/build/enclosure.glb"}
        ),
    )
    with pytest.raises(ValueError, match="project-owned source"):
        build_assembly_review(root, "controller", receipt, path)


def test_frame_and_quaternion_mismatch_are_rejected() -> None:
    with pytest.raises(ValueError, match="frames differ"):
        AssemblyPlacementContract(
            project_id="demo",
            board_glb_sha256="a" * 64,
            board_frame="board",
            board_unit="mm",
            enclosure_model="cad/enclosure.glb",
            enclosure_sha256="b" * 64,
            enclosure_frame="enclosure",
            enclosure_unit="mm",
            placement=AssemblyPlacement(
                source_frame="wrong",
                target_frame="board",
                translation_mm=(0, 0, 0),
                rotation_xyzw=(0, 0, 0, 1),
            ),
        )
    with pytest.raises(ValueError, match="quaternion"):
        AssemblyPlacement(
            source_frame="enclosure",
            target_frame="board",
            translation_mm=(0, 0, 0),
            rotation_xyzw=(0, 0, 0, 2),
        )
    with pytest.raises(ValueError, match="board_unit"):
        AssemblyPlacementContract(
            project_id="demo",
            board_glb_sha256="a" * 64,
            board_frame="board",
            board_unit="inch",
            enclosure_model="cad/enclosure.glb",
            enclosure_sha256="b" * 64,
            enclosure_frame="enclosure",
            enclosure_unit="mm",
        )


class _AssemblyParity(McpParityHarness):
    async def _case_test_cli_mcp_assembly_review_parity(self) -> None:
        receipt, contract = inputs(self.root, self.island)
        cli = await self.cli(
            "kicad_tooling.assembly_review",
            AssemblyReviewReport,
            "--project",
            "controller",
            "--board-receipt",
            str(receipt),
            "--placement-contract",
            str(contract),
            "--output",
            "build/assembly-review/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "board_receipt": receipt.relative_to(self.root).as_posix(),
            "placement_contract": contract.relative_to(self.root).as_posix(),
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue((await client.call_tool("export_assembly_review", arguments)).is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "export_assembly_review", AssemblyReviewReport, arguments)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_text(),
            (Path(mcp.output_directory) / "index.html").read_text(),
        )


def test_cli_mcp_assembly_review_parity() -> None:
    run_mcp_parity(_AssemblyParity, "_case_test_cli_mcp_assembly_review_parity")
