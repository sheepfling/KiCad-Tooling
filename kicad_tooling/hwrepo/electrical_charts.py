"""Build source-bound chart and CSV review artifacts from saved electrical runs."""
from __future__ import annotations

import csv
import importlib.util
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

from .contract_coach import receipt_directory
from .contracts import read_model, repo_path, write_model
from .electrical import simulation_cases
from .electrical_plot import render_case
from .evidence import digest
from .models import (
    ContractCoachReport,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    ElectricalChartCase,
    ElectricalChartsReport,
    ElectricalChartsSuiteReport,
    ElectricalSuiteReport,
    GroundingAnalysis,
    PowerAnalysis,
)
from .waveform_data import WaveformData, read_waveform


def source_receipt(root: Path, path: Path) -> Path:
    """Require an existing ignored analysis receipt, with no linked path components."""
    root = root.resolve()
    requested = path if path.is_absolute() else root / path
    directory = requested.parent if requested.name == "electrical.json" else requested
    try:
        relative = directory.relative_to(root)
    except ValueError as exc:
        raise ValueError("Electrical charts require a receipt under this repository's build/") from exc
    if not relative.parts or relative.parts[0] != "build":
        raise ValueError("Electrical charts require a receipt under this repository's build/")
    directory = repo_path(root, relative.as_posix())
    if not directory.is_dir() or not (directory / "electrical.json").is_file():
        raise ValueError(f"No electrical analysis receipt at {directory}")
    return directory


def checked_artifact(directory: Path, report: ElectricalAnalysisReport, name: str) -> Path:
    expected = report.artifacts_sha256.get(name)
    if expected is None:
        raise ValueError(f"Analysis did not record {name}; refusing unbound chart input")
    path = repo_path(directory, name)
    if not path.is_file() or digest(path) != expected:
        raise ValueError(f"Retained analysis artifact changed or is missing: {name}")
    return path


def waveform_csv(path: Path, data: WaveformData) -> None:
    """Keep the full precision native samples, including AC real/imaginary pairs."""
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        axis_unit = "s" if data.axis_name == "time" else "Hz"
        header = [f"{data.axis_name}_{axis_unit}"]
        for series in data.series:
            header.extend((f"{series.name}.real [{series.unit}]",
                           f"{series.name}.imag [{series.unit}]"))
        writer.writerow(header)
        for index, value in enumerate(data.axis):
            row = [format(value, ".17g")]
            for series in data.series:
                row.extend((format(series.values[index].real, ".17g"),
                            format(series.values[index].imag, ".17g")))
            writer.writerow(row)


def grounding_csv(path: Path, contract: GroundingAnalysis,
                  observed: ContractCoachReport | None) -> None:
    nets: Mapping[str, tuple[str, ...]] = (
        observed.observed.nets if observed is not None and observed.observed is not None else {}
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("declared_net", "pin", "observed_net", "status", "note"))
        for domain in contract.domains:
            for pin in domain.pins:
                actual = next((name for name, pins in nets.items() if pin in pins), "")
                status = "MATCH" if actual == domain.net else (
                    "MISSING_OR_DIFFERENT" if observed is not None else "UNVERIFIED"
                )
                writer.writerow((domain.net, pin, actual, status, "Declared schematic coverage"))
            for pin in sorted(set(nets.get(domain.net, ())) - set(domain.pins)):
                writer.writerow((domain.net, pin, domain.net, "UNDECLARED", "Review extra pin"))
        for component, reason in sorted(contract.exempt_components.items()):
            writer.writerow(("", component, "", "EXEMPT", reason))


def power_csv(path: Path, contract: PowerAnalysis) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("rail", "voltage_v", "steady_load_a", "startup_load_a",
                         "continuous_limit_a", "peak_limit_a", "peak_duration_limit_s",
                         "longest_startup_s", "basis"))
        for rail in contract.rails:
            writer.writerow((rail.id, rail.voltage_v,
                             sum(load.steady_a for load in rail.loads),
                             sum(max(load.steady_a, load.startup_a) for load in rail.loads),
                             rail.continuous_limit_a, rail.peak_limit_a,
                             rail.peak_duration_limit_s,
                             max(load.startup_s for load in rail.loads), rail.basis))


def build_charts(root: Path, receipt: Path, output: Path | None = None) -> ElectricalChartsReport:
    """Render existing checked waveform artifacts; never run KiCad or ngspice."""
    root = root.resolve()
    source = source_receipt(root, receipt)
    report_path = source / "electrical.json"
    report = read_model(report_path, ElectricalAnalysisReport)
    report_hash = digest(report_path)
    if Path(report.run_directory).resolve() != source:
        raise ValueError("Analysis report points to a different receipt directory")
    requirements = checked_artifact(source, report, "requirements.json")
    contract = read_model(requirements, ElectricalAnalysisContract)
    if contract.project_id != report.project_id:
        raise ValueError("Analysis and requirements project IDs differ")
    cases = simulation_cases(contract)
    # Dependency is optional for verification; fail with a precise install command
    # when charting is requested and waveform cases actually exist.
    if cases and importlib.util.find_spec("matplotlib") is None:
        raise ValueError("Install chart support with python -m pip install -e '.[charts]'")
    directory = receipt_directory(root, report.project_id, output or (
        Path("build/electrical-charts") / f"{report.project_id}-{uuid4().hex[:12]}"
    ))
    results: list[ElectricalChartCase] = []
    ground: str | None = None
    power: str | None = None
    if isinstance(contract.grounding, GroundingAnalysis):
        observed: ContractCoachReport | None = None
        if "netlist-evidence.json" in report.artifacts_sha256:
            observed = read_model(checked_artifact(source, report, "netlist-evidence.json"),
                                  ContractCoachReport)
            if observed.project_id != report.project_id:
                raise ValueError("Grounding capture belongs to another project")
        ground = "grounding.csv"
        grounding_csv(directory / ground, contract.grounding, observed)
    if isinstance(contract.power, PowerAnalysis):
        power = "power.csv"
        power_csv(directory / power, contract.power)
    for case in cases:
        raw_name = f"{case.id}/waveforms.raw"
        if raw_name not in report.artifacts_sha256 and not (source / raw_name).exists():
            results.append(ElectricalChartCase(
                id=case.id, status="FAIL" if report.status == "PASS" else "SKIPPED",
                detail="No retained waveform; inspect the analysis receipt."
            ))
            continue
        try:
            raw = checked_artifact(source, report, raw_name)
            data = read_waveform(raw, "time" if case.analysis == "tran" else "frequency")
            csv_name, png_name, svg_name = (f"{case.id}.{extension}"
                                            for extension in ("csv", "png", "svg"))
            waveform_csv(directory / csv_name, data)
            render_case(data, case, directory / png_name, directory / svg_name)
            results.append(ElectricalChartCase(
                id=case.id, status="PASS", samples=len(data.axis),
                waveform_sha256=digest(raw), csv=csv_name, png=png_name, svg=svg_name,
                detail="Chart and full precision series exported from the retained waveform."
            ))
        except (OSError, RuntimeError, ValueError) as exc:
            results.append(ElectricalChartCase(id=case.id, status="FAIL", detail=str(exc)))
    status = ("FAIL" if any(item.status == "FAIL" for item in results) else
              "PARTIAL" if any(item.status == "SKIPPED" for item in results) else
              "PASS")
    # Preserve the evidence boundary if files change while large charts render.
    if digest(report_path) != report_hash:
        raise ValueError("Analysis report changed during chart export")
    checked_artifact(source, report, "requirements.json")
    if ground is not None and "netlist-evidence.json" in report.artifacts_sha256:
        checked_artifact(source, report, "netlist-evidence.json")
    for item in results:
        if item.status == "PASS":
            checked_artifact(source, report, f"{item.id}/waveforms.raw")
    output_report = ElectricalChartsReport(
        project_id=report.project_id, status=status, source_analysis_status=report.status,
        source_receipt=str(source), source_report_sha256=report_hash,
        run_directory=str(directory), cases=tuple(results), grounding_csv=ground,
        power_csv=power,
        artifacts_sha256={item.relative_to(directory).as_posix(): digest(item)
                          for item in sorted(directory.rglob("*")) if item.is_file()},
        next_actions=("Review charts with the declared acceptance limits and the original analysis receipt.",
                      "A chart is a view of saved simulation data, not physical validation."),
    )
    write_model(directory / "charts.json", output_report)
    return output_report


def build_suite(root: Path, suite: Path, output: Path | None = None) -> ElectricalChartsSuiteReport:
    root = root.resolve()
    requested = suite if suite.is_absolute() else root / suite
    try:
        relative = requested.relative_to(root)
    except ValueError as exc:
        raise ValueError("Electrical suite must be saved under this repository's build/") from exc
    if not relative.parts or relative.parts[0] != "build":
        raise ValueError("Electrical suite must be saved under this repository's build/")
    path = repo_path(root, relative.as_posix())
    summary = read_model(path, ElectricalSuiteReport)
    if not summary.projects:
        raise ValueError("Electrical suite contains no project receipts")
    directory = receipt_directory(root, "suite", output or (
        Path("build/electrical-charts") / f"suite-{uuid4().hex[:12]}"
    ))
    reports_list: list[ElectricalChartsReport] = []
    for project in summary.projects:
        source = source_receipt(root, Path(project.run_directory))
        if read_model(source / "electrical.json", ElectricalAnalysisReport) != project:
            raise ValueError(f"Suite and retained analysis disagree for {project.project_id}")
        reports_list.append(build_charts(root, source, directory / project.project_id))
    reports = tuple(reports_list)
    status = ("FAIL" if any(item.status == "FAIL" for item in reports) else
              "PARTIAL" if any(item.status == "PARTIAL" for item in reports) else "PASS")
    result = ElectricalChartsSuiteReport(status=status, run_directory=str(directory), reports=reports)
    write_model(directory / "suite.json", result)
    return result
