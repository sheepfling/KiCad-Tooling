"""Run all configured electrical checks into a fresh, source-bound receipt."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

from .contract_coach import (
    AutoNetlistRunner,
    NetlistRunner,
    capture,
    inspect_summary,
    receipt_directory,
)
from .contracts import write_model
from .electrical import (
    bound_inputs,
    grounding_checks,
    load_analysis,
    power_budget_checks,
    selected_config,
    simulation_cases,
)
from .evidence import digest, source_state
from .models import (
    AnalysisNotApplicable,
    AnalysisPending,
    CommandEvidence,
    ElectricalAnalysisReport,
    ElectricalCheck,
    ElectricalSuiteReport,
    GroundingAnalysis,
)
from .selection import ProjectSelector, resolve_project_ids
from .spice import executable_path, run_case, simulator_version


def analyze(
    root: Path,
    project_id: str,
    output: Path | None = None,
    native_summary: Path | None = None,
    cli: str = "kicad-cli",
    ngspice: str = "ngspice",
    runner: NetlistRunner | None = None,
) -> ElectricalAnalysisReport:
    root = root.resolve()
    source = source_state(root)
    if native_summary is not None and not native_summary.is_absolute():
        native_summary = root / native_summary
    if output is None:
        output = Path("build/electrical") / f"{project_id}-{uuid4().hex[:12]}"
    output = receipt_directory(root, project_id, output)
    checks: list[ElectricalCheck] = []
    commands: dict[str, CommandEvidence] = {}
    inputs: dict[str, str] = {}
    status = "FAIL"
    try:
        config = selected_config(root, project_id)
        contract = load_analysis(root, config)
        if contract is None:
            status = "NOT_CONFIGURED"
            checks.append(
                ElectricalCheck(
                    id="configuration",
                    status="NOT_CONFIGURED",
                    detail=f"Run python -B -m kicad_tooling.electrical --project {project_id} --init, then review the starter.",
                )
            )
        else:
            inputs = bound_inputs(root, config, contract)
            write_model(output / "requirements.json", contract)
            if isinstance(contract.grounding, GroundingAnalysis):
                if native_summary is None:
                    netlist_output = output / "netlist"
                    netlist_output.mkdir()
                    observed = capture(
                        root, project_id, netlist_output, runner or AutoNetlistRunner(cli)
                    )
                else:
                    observed = inspect_summary(root, project_id, native_summary)
                write_model(output / "netlist-evidence.json", observed)
                if observed.observed is None:
                    checks.append(
                        ElectricalCheck(
                            id="grounding",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(grounding_checks(contract.grounding, observed.observed))
            else:
                checks.append(
                    ElectricalCheck(
                        id="grounding",
                        status="NOT_CONFIGURED"
                        if isinstance(contract.grounding, AnalysisPending)
                        else "NOT_APPLICABLE",
                        detail=contract.grounding.reason,
                    )
                )
            if isinstance(contract.high_frequency, (AnalysisNotApplicable, AnalysisPending)):
                checks.append(
                    ElectricalCheck(
                        id="high-frequency",
                        status="NOT_CONFIGURED"
                        if isinstance(contract.high_frequency, AnalysisPending)
                        else "NOT_APPLICABLE",
                        detail=contract.high_frequency.reason,
                    )
                )
            checks.extend(power_budget_checks(contract.power))
            cases = simulation_cases(contract)
            if cases:
                executable = executable_path(ngspice)
                try:
                    commands["version"] = simulator_version(
                        output, executable, contract.ngspice_version
                    )
                except ValueError as exc:
                    checks.extend(
                        ElectricalCheck(id=case.id, status="NOT_RUN", detail=str(exc))
                        for case in cases
                    )
                else:
                    for case in cases:
                        try:
                            command, measured = run_case(root, output, executable, case)
                            commands[case.id] = command
                            checks.extend(measured)
                        except (OSError, ValueError) as exc:
                            checks.append(
                                ElectricalCheck(id=case.id, status="FAIL", detail=str(exc))
                            )
            if bound_inputs(root, config, load_analysis(root, config) or contract) != inputs:
                raise ValueError("Electrical inputs changed during analysis")
            if source_state(root) != source:
                raise ValueError("Repository source changed during electrical analysis")
            status = (
                "PASS"
                if checks and all(c.status in {"PASS", "NOT_APPLICABLE"} for c in checks)
                else "FAIL"
            )
    except (OSError, ValueError) as exc:
        checks.append(ElectricalCheck(id="inputs", status="FAIL", detail=str(exc)))
    report = ElectricalAnalysisReport(
        project_id=project_id,
        source=source,
        status=status,
        run_directory=str(output),
        input_sha256=inputs,
        artifacts_sha256={
            path.relative_to(output).as_posix(): digest(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        },
        commands=commands,
        checks=tuple(checks),
    )
    write_model(output / "electrical.json", report)
    (output / "electrical.txt").write_text(format_report(report, "full") + "\n", encoding="utf-8")
    return report


def analyze_scope(
    root: Path,
    selector: ProjectSelector | None = None,
    cli: str = "kicad-cli",
    ngspice: str = "ngspice",
) -> ElectricalSuiteReport:
    """Run the same selected electrical scope for CLI and MCP, retaining every result."""
    identifiers = resolve_project_ids(root, selector or ProjectSelector())
    reports = tuple(
        analyze(root, project_id, cli=cli, ngspice=ngspice) for project_id in identifiers
    )
    return ElectricalSuiteReport(
        status="PASS" if reports and all(report.status == "PASS" for report in reports) else "FAIL",
        projects=reports,
    )


def format_report(
    report: ElectricalAnalysisReport, detail: Literal["brief", "full"] = "brief"
) -> str:
    lines = [f"Electrical analysis: {report.status}", f"Project: {report.project_id}"]
    failed = [row for row in report.checks if row.status not in {"PASS", "NOT_APPLICABLE"}]
    if detail == "brief":
        passed = sum(row.status == "PASS" for row in report.checks)
        excluded = sum(row.status == "NOT_APPLICABLE" for row in report.checks)
        lines.append(
            f"Checks: {passed} passed, {len(failed)} need attention, {excluded} not applicable"
        )
        shown = failed[:5]
    else:
        shown = report.checks
    lines.extend(f"  {row.id}: {row.status} — {row.detail}" for row in shown)
    if detail == "brief" and len(failed) > len(shown):
        lines.append("More findings: --detail full or --format json.")
    lines.append(f"Receipt: {report.run_directory}")
    if failed:
        lines.append(
            "Next: follow docs/workflow/ELECTRICAL_ANALYSIS.md or run "
            f"kicad_tooling.template doctor --electrical --project-id {report.project_id} --format text."
        )
    if detail == "full":
        lines.extend(f"Scope: {limit}" for limit in report.limits)
    else:
        lines.append(
            "Scope: declared pins, budgets and reviewed circuit models; layout and hardware acceptance remain separate."
        )
    return "\n".join(lines)
