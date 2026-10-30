"""Join a retained board GLB with a project-authored adjacent assembly model."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from ..validate import hashes
from .artifact_access import artifact_file, read_regular_bytes
from .assembly_review_html import render_assembly_review
from .assembly_review_models import AssemblyPlacementContract, AssemblyReviewReport
from .contract_coach import receipt_directory
from .contracts import parse_model_text, repo_path, write_model
from .discovery import load_config
from .evidence import digest
from .models import ThreeDReport
from .review_overview_evidence import read_receipt, recorded_directory, selected_receipt
from .selection import resolve_project
from .three_d_glb import inspect_glb

_MAX_GLB = 64 * 1024 * 1024


def _selected_contract(root: Path, project_directory: Path, selected: Path) -> tuple[Path, bytes]:
    try:
        relative = selected.relative_to(root) if selected.is_absolute() else selected
    except ValueError as exc:
        raise ValueError("Select a project-owned placement contract") from exc
    path = repo_path(root, relative.as_posix())
    if (
        not path.is_relative_to(project_directory)
        or "build" in path.relative_to(project_directory).parts
        or path.suffix != ".json"
    ):
        raise ValueError("Placement contract must be JSON inside the selected project")
    content, _ = read_regular_bytes(path, maximum=1024 * 1024)
    return path, content


def _verified_board(
    root: Path, receipt_path: Path, receipt: ThreeDReport, current: dict[str, str]
) -> tuple[Path, bytes, str]:
    if (
        receipt.mode != "generate"
        or receipt.board is None
        or dict(receipt.source_sha256) != current
        or not recorded_directory(root, receipt.run_directory, receipt_path.parent)
    ):
        raise ValueError("Board 3D receipt is not bound to the selected current source")
    expected = receipt.artifacts_sha256.get("board.glb")
    if expected is None:
        raise ValueError("Board 3D receipt has no retained GLB")
    path = artifact_file(root, (receipt_path.parent / "board.glb").relative_to(root).as_posix())
    content, _ = read_regular_bytes(path, maximum=_MAX_GLB)
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError("Retained board GLB changed")
    info = inspect_glb(path)
    if info is None or not info.offline or not info.has_position_primitive:
        raise ValueError("Retained board GLB is invalid, empty or has external resources")
    return path, content, expected


def build_assembly_review(
    root: Path,
    project_id: str,
    board_receipt: Path,
    placement_contract: Path,
    output: Path | None = None,
) -> AssemblyReviewReport:
    """Create an offline visual overlay without claiming geometry or clearance checks."""
    root = root.resolve()
    project = resolve_project(root, project_id)
    config = load_config(root, project.config)
    current = hashes(root, config.source_roots)
    board_source = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    if board_source not in current:
        raise ValueError("Selected project has no current PCB source")
    receipt_path = selected_receipt(root, board_receipt, "visualization.json")
    receipt, receipt_sha = read_receipt(receipt_path, ThreeDReport)
    if (
        receipt.project_id != project_id
        or receipt.board != board_source
        or receipt.toolchain_id != config.toolchain_id
        or receipt.kicad_version != config.kicad_version
    ):
        raise ValueError("Board 3D receipt identifies another project, board or toolchain")
    board_path, board_bytes, board_sha = _verified_board(root, receipt_path, receipt, current)
    project_directory = repo_path(root, project.config).parent
    contract_path, contract_bytes = _selected_contract(root, project_directory, placement_contract)
    contract = parse_model_text(contract_bytes.decode("utf-8"), AssemblyPlacementContract)
    if contract.project_id != project_id or contract.board_glb_sha256 != board_sha:
        raise ValueError("Placement contract does not bind the selected board GLB")
    enclosure_path = repo_path(root, contract.enclosure_model)
    if "build" in enclosure_path.relative_to(root).parts:
        raise ValueError("Enclosure model must be project-owned source, not a generated receipt")
    enclosure_bytes: bytes | None = None
    actual_enclosure_sha: str | None = None
    issues: list[str] = []
    if not enclosure_path.is_file():
        issues.append("Declared enclosure GLB is missing.")
    else:
        enclosure_bytes, _ = read_regular_bytes(enclosure_path, maximum=_MAX_GLB)
        actual_enclosure_sha = hashlib.sha256(enclosure_bytes).hexdigest()
        if actual_enclosure_sha != contract.enclosure_sha256:
            issues.append("Enclosure GLB differs from the project-authored hash.")
            enclosure_bytes = None
        else:
            info = inspect_glb(enclosure_path)
            if info is None or not info.offline or not info.has_position_primitive:
                issues.append("Enclosure GLB is invalid, empty or has external resources.")
                enclosure_bytes = None
    if contract.placement is None:
        issues.append("No enclosure-to-board placement is declared.")
    if receipt.status != "PASS":
        issues.append("Selected board 3D export did not finish with PASS.")
    if receipt.models is None or receipt.models.status != "READY":
        issues.append("Board model coverage needs review in the selected 3D receipt.")
    ready = enclosure_bytes is not None and contract.placement is not None
    if not ready:
        issues.append("Combined placement is unavailable; only the board model is displayed.")

    def verify_inputs() -> None:
        if (
            hashes(root, config.source_roots) != current
            or load_config(root, project.config) != config
        ):
            raise ValueError("Project source or configuration changed during assembly export")
        if (
            digest(receipt_path) != receipt_sha
            or digest(contract_path) != hashlib.sha256(contract_bytes).hexdigest()
        ):
            raise ValueError("Selected 3D receipt or placement contract changed during export")
        if digest(board_path) != board_sha:
            raise ValueError("Retained board GLB changed during assembly export")
        if actual_enclosure_sha is not None and digest(enclosure_path) != actual_enclosure_sha:
            raise ValueError("Enclosure GLB changed during assembly export")
        if actual_enclosure_sha is None and enclosure_path.exists():
            raise ValueError("Declared enclosure GLB appeared during assembly export")

    verify_inputs()
    target = output or Path("build/assembly-review") / f"{project_id}-{uuid4().hex[:12]}"
    directory = receipt_directory(root, project_id, target)
    (directory / "board.glb").write_bytes(board_bytes)
    if enclosure_bytes is not None:
        (directory / "enclosure.glb").write_bytes(enclosure_bytes)
    asset = Path(__file__).parent / "assets"
    (directory / "viewer.js").write_bytes((asset / "three_d_viewer.js").read_bytes())
    (directory / "viewer-license.txt").write_bytes((asset / "threejs-LICENSE.txt").read_bytes())
    report = AssemblyReviewReport(
        project_id=project_id,
        status=(
            "INCOMPLETE"
            if not ready
            else "REVIEW"
            if receipt.status != "PASS"
            or receipt.models is None
            or receipt.models.status != "READY"
            else "READY"
        ),
        board_receipt=receipt_path.relative_to(root).as_posix(),
        board_receipt_sha256=receipt_sha,
        placement_contract=contract_path.relative_to(root).as_posix(),
        placement_contract_sha256=hashlib.sha256(contract_bytes).hexdigest(),
        board_glb_sha256=board_sha,
        enclosure_model=contract.enclosure_model,
        enclosure_expected_sha256=contract.enclosure_sha256,
        enclosure_sha256=actual_enclosure_sha,
        board_frame=contract.board_frame,
        board_unit=contract.board_unit,
        enclosure_frame=contract.enclosure_frame,
        enclosure_unit=contract.enclosure_unit,
        placement=contract.placement,
        source_hashes=current,
        model_status=receipt.models.status if receipt.models is not None else "NOT_RECORDED",
        assembly_variant=receipt.assembly_variant,
        issues=tuple(issues),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(
        render_assembly_review(report, board_bytes, enclosure_bytes),
        encoding="utf-8",
    )
    verify_inputs()
    report = report.model_copy(
        update={"artifacts_sha256": {path.name: digest(path) for path in directory.iterdir()}}
    )
    write_model(directory / "assembly-review.json", report)
    return report
