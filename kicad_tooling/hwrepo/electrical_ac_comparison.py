"""Compare one matching AC measurement in two exact saved analysis receipts."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .contract_coach import receipt_directory
from .contracts import read_model, repo_path, write_model
from .electrical import simulation_cases
from .electrical_analysis_contract_models import ElectricalAnalysisContract
from .electrical_chart_interactive import interactive_trace, render_interactive_chart
from .electrical_chart_models import AcComparisonReport, AcComparisonRun
from .electrical_charts import checked_artifact, source_receipt, waveform_csv
from .electrical_plot import ChartPanel, plot_panels
from .electrical_report_models import ElectricalAnalysisReport
from .electrical_simulation_models import FrequencyAnalysis, SimulationMeasure
from .evidence import digest
from .waveform_data import WaveformData, read_waveform


@dataclass(frozen=True, slots=True)
class _SelectedAc:
    directory: Path
    report: ElectricalAnalysisReport
    report_sha256: str
    requirements_sha256: str
    waveform_sha256: str
    data: WaveformData
    measure: SimulationMeasure
    panel: ChartPanel
    case: FrequencyAnalysis


def _selected_ac(
    root: Path, project_id: str, receipt: Path, case_id: str, measure_id: str
) -> _SelectedAc:
    directory = source_receipt(root, receipt)
    report_path = repo_path(directory, "electrical.json")
    report = read_model(report_path, ElectricalAnalysisReport)
    if report.project_id != project_id or Path(report.run_directory).resolve() != directory:
        raise ValueError("AC receipt belongs to another project or directory")
    requirements = checked_artifact(directory, report, "requirements.json")
    contract = read_model(requirements, ElectricalAnalysisContract)
    if contract.project_id != project_id:
        raise ValueError("AC requirements belong to another project")
    matches = tuple(
        case
        for case in simulation_cases(contract)
        if case.id == case_id and isinstance(case, FrequencyAnalysis)
    )
    if len(matches) != 1:
        raise ValueError(f"Select one saved AC case: {case_id}")
    case = matches[0]
    measure_indices = tuple(
        index for index, item in enumerate(case.measures) if item.id == measure_id
    )
    if len(measure_indices) != 1:
        raise ValueError(f"Select one saved AC measurement: {measure_id}")
    raw = checked_artifact(directory, report, f"{case.id}/waveforms.raw")
    data = read_waveform(raw, "frequency")
    panel = plot_panels(data, case)[measure_indices[0]]
    return _SelectedAc(
        directory=directory,
        report=report,
        report_sha256=digest(report_path),
        requirements_sha256=digest(requirements),
        waveform_sha256=digest(raw),
        data=data,
        measure=case.measures[measure_indices[0]],
        panel=panel,
        case=case,
    )


def _identity(root: Path, selected: _SelectedAc) -> AcComparisonRun:
    return AcComparisonRun(
        receipt=(selected.directory / "electrical.json").relative_to(root).as_posix(),
        report_sha256=selected.report_sha256,
        requirements_sha256=selected.requirements_sha256,
        waveform_sha256=selected.waveform_sha256,
        analysis_status=selected.report.status,
        input_sha256=selected.report.input_sha256,
        samples=len(selected.data.axis),
        first_hz=selected.data.axis[0],
        last_hz=selected.data.axis[-1],
        window_start_hz=selected.measure.start,
        window_stop_hz=selected.measure.stop,
    )


def _still_current(selected: _SelectedAc) -> bool:
    source = selected.directory
    return (
        digest(source / "electrical.json") == selected.report_sha256
        and digest(checked_artifact(source, selected.report, "requirements.json"))
        == selected.requirements_sha256
        and digest(checked_artifact(source, selected.report, f"{selected.case.id}/waveforms.raw"))
        == selected.waveform_sha256
    )


def compare_ac_runs(
    root: Path,
    project_id: str,
    baseline: Path,
    candidate: Path,
    case_id: str,
    measure_id: str,
    output: Path | None = None,
) -> AcComparisonReport:
    """Overlay native grids without interpolation or inferred design acceptance."""
    root = root.resolve()
    first = _selected_ac(root, project_id, baseline, case_id, measure_id)
    second = _selected_ac(root, project_id, candidate, case_id, measure_id)
    if first.directory == second.directory:
        raise ValueError("Select two distinct AC receipts")
    if (
        first.measure.expression != second.measure.expression
        or first.measure.unit != second.measure.unit
        or first.measure.statistic != second.measure.statistic
        or first.panel.comparable_limits != second.panel.comparable_limits
    ):
        raise ValueError(
            "Saved AC measurements have incompatible expressions, units, or quantities"
        )
    overlap = (
        "OVERLAP"
        if max(first.data.axis[0], second.data.axis[0])
        < min(first.data.axis[-1], second.data.axis[-1])
        else "DISJOINT"
    )
    before_trace = interactive_trace(first.data.axis, first.panel, id="baseline", label="Baseline")
    after_trace = interactive_trace(
        second.data.axis, second.panel, id="candidate", label="Candidate"
    )
    # Recheck both selected receipts after parsing and before writing a comparison.
    if not _still_current(first) or not _still_current(second):
        raise ValueError("Selected AC evidence changed during comparison")
    directory = receipt_directory(
        root,
        project_id,
        output or Path("build/electrical-ac-comparison") / f"{project_id}-{uuid4().hex[:12]}",
    )
    waveform_csv(directory / "baseline.csv", first.data)
    waveform_csv(directory / "candidate.csv", second.data)
    shutil.copyfile(first.directory / "requirements.json", directory / "baseline-requirements.json")
    shutil.copyfile(
        second.directory / "requirements.json", directory / "candidate-requirements.json"
    )
    if (
        digest(directory / "baseline-requirements.json") != first.requirements_sha256
        or digest(directory / "candidate-requirements.json") != second.requirements_sha256
    ):
        raise ValueError("Saved AC requirements changed during copy")
    report = AcComparisonReport(
        project_id=project_id,
        case_id=case_id,
        measure_id=measure_id,
        expression=first.measure.expression,
        unit=first.measure.unit,
        quantity_kind="SCALAR" if first.panel.comparable_limits else "DERIVED_MAGNITUDE",
        baseline=_identity(root, first),
        candidate=_identity(root, second),
        overlap=overlap,
        display_points_baseline=len(before_trace.x),
        display_points_candidate=len(after_trace.x),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(
        render_interactive_chart(
            f"AC comparison · {project_id} · {case_id}/{measure_id}",
            "frequency",
            (before_trace, after_trace),
            (
                ("Selected expression", report.expression),
                ("Quantity", f"{report.quantity_kind} ({report.unit})"),
                ("Frequency overlap", overlap),
                ("Baseline analysis status", first.report.status),
                ("Baseline receipt", report.baseline.receipt),
                ("Baseline report SHA-256", first.report_sha256),
                ("Baseline waveform SHA-256", first.waveform_sha256),
                ("Candidate analysis status", second.report.status),
                ("Candidate receipt", report.candidate.receipt),
                ("Candidate report SHA-256", second.report_sha256),
                ("Candidate waveform SHA-256", second.waveform_sha256),
                ("Baseline display points", f"{len(before_trace.x)} of {len(first.data.axis)}"),
                ("Candidate display points", f"{len(after_trace.x)} of {len(second.data.axis)}"),
            ),
            (
                ("Baseline full CSV", "baseline.csv"),
                ("Candidate full CSV", "candidate.csv"),
                ("Baseline requirements", "baseline-requirements.json"),
                ("Candidate requirements", "candidate-requirements.json"),
                ("Structured comparison", "comparison.json"),
            ),
        ),
        encoding="utf-8",
    )
    if not _still_current(first) or not _still_current(second):
        raise ValueError("Selected AC evidence changed during comparison")
    report = report.model_copy(
        update={
            "artifacts_sha256": {
                path.name: digest(path) for path in sorted(directory.iterdir()) if path.is_file()
            }
        }
    )
    write_model(directory / "comparison.json", report)
    return report
