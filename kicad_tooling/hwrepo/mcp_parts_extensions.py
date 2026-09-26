"""Fixed-root adapters for reviewed part selection, CAD imports and supplier handoff."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from pydantic import TypeAdapter

from . import auto_cad, contract_coach, part_picker, part_picker_view, supplier_handoff
from .contracts import read_model, write_model
from .doctor import NativeRunner
from .mcp_files import read_regular_bytes
from .mcp_workflow import artifact_file, fresh_output, native_summary_path, selected_project
from .models import (
    AutoCadReport,
    Digest,
    PartPickerReport,
    PartSelectionAssignment,
    PartSelectionMap,
    PartSelectionReport,
    SupplierHandoffReport,
)

_DIGEST: TypeAdapter[str] = TypeAdapter(Digest)


def _output(root: Path, view_id: str) -> Path:
    output = fresh_output(root, "parts", view_id)
    output.mkdir(parents=True, exist_ok=False)
    return output


def _json_artifact(root: Path, value: str) -> Path:
    path = artifact_file(root, value)
    if path.suffix != ".json" or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Select a JSON review artifact no larger than 2 MiB")
    return path


def _reviewed_bytes(root: Path, value: str, expected_sha256: str) -> bytes:
    expected_sha256 = _DIGEST.validate_python(expected_sha256, strict=True)
    data, _ = read_regular_bytes(_json_artifact(root, value), maximum=2 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("Reviewed plan changed; inspect it and use its current SHA-256")
    return data


def prepare_part_picker(
    root: Path, project_id: str, view_id: str, native_summary: str | None = None,
    runner: NativeRunner = "auto", *, allow_checks: bool = False,
) -> PartPickerReport:
    selected_project(root, project_id)
    if native_summary is None and not allow_checks:
        raise ValueError("Fresh picker capture requires --allow-checks as well as --allow-exports; "
                         "otherwise supply a saved native_summary")
    if runner not in {"auto", "local", "container"}:
        raise ValueError(f"Unknown native runner: {runner}")
    if native_summary is not None and runner != "auto":
        raise ValueError("runner applies only to fresh capture, not saved native_summary")
    summary = None if native_summary is None else native_summary_path(root, native_summary)
    native_runner = (
        contract_coach.LocalNetlistRunner("kicad-cli") if runner == "local"
        else contract_coach.ContainerNetlistRunner() if runner == "container"
        else contract_coach.AutoNetlistRunner("kicad-cli")
    )
    output = _output(root, view_id)
    report = part_picker.create_picker(root, project_id, output, native_runner, summary)
    part_picker_view.save_picker(output, report)
    return report


def preview_part_selection(
    root: Path, project_id: str, view_id: str, picker_report: str,
    assignments: list[PartSelectionAssignment],
) -> PartSelectionReport:
    selected_project(root, project_id)
    picker = read_model(_json_artifact(root, picker_report), PartPickerReport)
    if picker.project_id != project_id or picker.selection_template is None:
        raise ValueError("Select this project's successful retained picker report")
    choices = {item.component.reference: item.choice_ids for item in picker.items}
    if not assignments or any(item.part_id not in choices.get(item.reference, ()) for item in assignments):
        raise ValueError("Choose at least one part offered for its reference in the retained picker")
    spec = PartSelectionMap(
        project_id=project_id, preconditions=picker.selection_template.preconditions,
        assignments=tuple(assignments),
    )
    output = _output(root, view_id)
    # The service requires a fresh empty output, so its typed input lives in a
    # separate, temporary build directory. No client-supplied path is opened.
    with tempfile.TemporaryDirectory(prefix=".part-selection-", dir=output.parent) as temporary:
        draft = Path(temporary) / "selection.json"
        write_model(draft, spec)
        report = part_picker.selection(root, project_id, draft, output)
    part_picker_view.save_selection(output, report)
    return report


def apply_part_selection(
    root: Path, project_id: str, view_id: str, selection_map: str, expected_sha256: str,
) -> PartSelectionReport:
    selected_project(root, project_id)
    data = _reviewed_bytes(root, selection_map, expected_sha256)
    output = _output(root, view_id)
    with tempfile.TemporaryDirectory(prefix=".reviewed-selection-", dir=output.parent) as temporary:
        path = Path(temporary) / "selection.json"
        path.write_bytes(data)
        report = part_picker.selection(root, project_id, path, output, apply=True)
    part_picker_view.save_selection(output, report)
    return report


def preview_model_sync(root: Path, project_id: str, view_id: str) -> PartSelectionReport:
    selected_project(root, project_id)
    output = _output(root, view_id)
    report = part_picker.resume_selection(root, project_id, output)
    part_picker_view.save_selection(output, report)
    return report


def preview_auto_cad(
    root: Path, project_id: str, view_id: str, *, allow_downloads: bool = False,
) -> AutoCadReport:
    selected_project(root, project_id)
    return auto_cad.plan(root, project_id, _output(root, view_id), allow_downloads=allow_downloads)


def apply_auto_cad(
    root: Path, project_id: str, view_id: str, plan: str, expected_sha256: str,
    *, allow_downloads: bool = False,
) -> AutoCadReport:
    selected_project(root, project_id)
    data = _reviewed_bytes(root, plan, expected_sha256)
    output = _output(root, view_id)
    with tempfile.TemporaryDirectory(prefix=".reviewed-cad-", dir=output.parent) as temporary:
        path = Path(temporary) / "cad-plan.json"
        path.write_bytes(data)
        return auto_cad.apply(root, project_id, path, output, allow_downloads=allow_downloads)


def prepare_supplier_handoff(
    root: Path, project_id: str, view_id: str, parts_report: str,
) -> SupplierHandoffReport:
    selected_project(root, project_id)
    output = fresh_output(root, "supplier-handoffs", view_id)
    return supplier_handoff.prepare_supplier_handoff(root, project_id, parts_report, output)


def submit_supplier_handoff(
    root: Path, handoff: str, expected_sha256: str,
) -> SupplierHandoffReport:
    return supplier_handoff.submit_supplier_handoff(root, handoff, expected_sha256)
