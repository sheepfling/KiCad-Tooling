"""Fixed-root MCP adapters for saved electrical charts and exact sourced CAD."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from pydantic import TypeAdapter

from . import cad_library, cad_source, cad_step, electrical_charts
from .contracts import repo_path, write_model
from .mcp_files import artifact_path, read_regular_bytes
from .mcp_workflow import artifact_file, fresh_output, selected_project
from .models import (
    CadImportReport,
    CadSourceReport,
    CadSourcingReview,
    CadStepReport,
    Digest,
    ElectricalChartsReport,
    ElectricalChartsSuiteReport,
)

_DIGEST: TypeAdapter[str] = TypeAdapter(Digest)


def _new_directory(root: Path, group: str, view_id: str) -> Path:
    output = fresh_output(root, group, view_id)
    output.mkdir(parents=True, exist_ok=False)
    return output


def _bundle_directory(root: Path, source: CadSourceReport) -> Path:
    if source.bundle_directory is None or source.bundle is None:
        raise ValueError("Select a READY source with a recorded bundle")
    raw = Path(source.bundle_directory)
    if not raw.is_absolute():
        raise ValueError("CAD bundle must use the checkout's absolute cache path")
    try:
        relative = raw.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("CAD bundle is outside this checkout") from exc
    expected = ("build", "cad-source-cache", f"easyeda-{source.bundle.converter_version}",
                source.supplier_id)
    if (len(relative.parts) != 6 or relative.parts[:4] != expected
            or relative.parts[-1] != "bundle" or len(relative.parts[4]) != 64
            or any(char not in "0123456789abcdef" for char in relative.parts[4])
            or source.bundle.supplier_id != source.supplier_id):
        raise ValueError("CAD bundle is outside the exact-part cache layout")
    return repo_path(root, relative.as_posix())


def _source_report(root: Path, source_report: str, supplier_id: str,
                   expected_mpn: str | None = None) -> CadSourceReport:
    path = artifact_file(root, source_report)
    if path.name != "cad-source.json":
        raise ValueError("Select a saved cad-source.json receipt")
    data, _ = read_regular_bytes(path, maximum=2 * 1024 * 1024)
    report = CadSourceReport.model_validate_json(data)
    if report.supplier_id != supplier_id or (expected_mpn is not None and (
            report.bundle is None or report.bundle.mpn != expected_mpn)):
        raise ValueError("Saved CAD source differs from the exact requested part")
    if report.status == "READY":
        _bundle_directory(root, report)
    return report


def export_electrical_charts(root: Path, view_id: str, receipt: str) -> ElectricalChartsReport:
    source = artifact_path(root, receipt)
    if not source.is_dir() and (not source.is_file() or source.name != "electrical.json"):
        raise ValueError("Select an electrical receipt directory or electrical.json")
    return electrical_charts.build_charts(root, source, fresh_output(root, "electrical-charts", view_id))


def export_electrical_chart_suite(root: Path, view_id: str,
                                  suite: str) -> ElectricalChartsSuiteReport:
    source = artifact_file(root, suite)
    if source.suffix != ".json":
        raise ValueError("Select a saved electrical suite JSON")
    return electrical_charts.build_suite(root, source, fresh_output(root, "electrical-charts", view_id))


def source_cad(root: Path, project_id: str, view_id: str, supplier_id: str,
               expected_mpn: str | None = None, refresh: bool = False,
               *, allow_downloads: bool = False) -> CadSourcingReview:
    selected_project(root, project_id)
    output = _new_directory(root, "cad-sourcing", view_id)
    source = cad_source.fetch(root, supplier_id, output / "source",
                              expected_mpn=expected_mpn, refresh=refresh,
                              allow_downloads=allow_downloads)
    planned = None
    if source.status == "READY" and source.bundle_directory is not None:
        plan_output = output / "import-plan"
        plan_output.mkdir()
        planned = cad_library.plan(root, project_id, _bundle_directory(root, source), plan_output)
    review = CadSourcingReview(source=source, import_plan=planned, review_id=str(output))
    write_model(output / "cad-review.json", review)
    return review


def preview_cad_import(root: Path, project_id: str, view_id: str,
                       source_report: str) -> CadImportReport:
    selected_project(root, project_id)
    path = artifact_file(root, source_report)
    if path.name != "cad-source.json":
        raise ValueError("Select a saved cad-source.json receipt")
    data, _ = read_regular_bytes(path, maximum=2 * 1024 * 1024)
    source = CadSourceReport.model_validate_json(data)
    if source.status != "READY" or source.bundle_directory is None:
        raise ValueError("Select a READY exact CAD source report")
    return cad_library.plan(root, project_id, _bundle_directory(root, source),
                            _new_directory(root, "cad-imports", view_id))


def apply_cad_import(root: Path, project_id: str, view_id: str, plan: str,
                     expected_sha256: str) -> CadImportReport:
    selected_project(root, project_id)
    expected = _DIGEST.validate_python(expected_sha256, strict=True)
    source = artifact_file(root, plan)
    if source.name != "cad-import-plan.json":
        raise ValueError("Select a saved cad-import-plan.json")
    data, _ = read_regular_bytes(source, maximum=2 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Reviewed CAD plan changed; inspect it and use its current SHA-256")
    output = _new_directory(root, "cad-imports", view_id)
    with tempfile.TemporaryDirectory(prefix=".reviewed-cad-import-", dir=output.parent) as temporary:
        snapshot = Path(temporary) / "cad-import-plan.json"
        snapshot.write_bytes(data)
        return cad_library.apply(root, project_id, snapshot, output)


def check_step_alignment(root: Path, project_id: str, view_id: str,
                         supplier_id: str, expected_mpn: str | None = None,
                         refresh: bool = False, source_report: str | None = None,
                         *, allow_downloads: bool = False) -> CadStepReport:
    selected_project(root, project_id)
    if source_report is not None and refresh:
        raise ValueError("refresh applies to a new provider lookup, not a saved source report")
    output = _new_directory(root, "cad-step", view_id)
    if source_report is None:
        source = cad_source.fetch(root, supplier_id, output / "source",
                                  expected_mpn=expected_mpn, refresh=refresh,
                                  allow_downloads=allow_downloads)
    else:
        source = _source_report(root, source_report, supplier_id, expected_mpn)
    review = output / "review"
    review.mkdir()
    return cad_step.review(root, project_id, source, review)
