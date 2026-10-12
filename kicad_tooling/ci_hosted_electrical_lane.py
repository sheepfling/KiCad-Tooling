"""Hosted electrical-analysis setup, execution, and chart diagnostics."""

from __future__ import annotations

import sys
from pathlib import Path

from .ci_hosted_support import HostedLog
from .hwrepo.contracts import read_model
from .hwrepo.models import ElectricalAnalysisReport


def project_simulator(root: Path, project: str, log: HostedLog) -> str:
    from .hwrepo.electrical import load_analysis, policy_issues, selected_config, simulation_cases
    from .hwrepo.simulator_setup import ensure

    config = selected_config(root, project)
    contract = load_analysis(root, config)
    if contract is None:
        return "ngspice"
    issues = policy_issues(root, config)
    if issues:
        raise ValueError(f"{project}: unresolved electrical requirements: {issues}")
    return (
        ensure(root, contract.ngspice_version, contract.ngspice_source_sha256, log)
        if simulation_cases(contract)
        else "ngspice"
    )


def electrical_lane(
    root: Path,
    project: str,
    log: HostedLog,
    native_summary: str | None = None,
    required: bool = False,
) -> None:
    from .hwrepo.electrical import selected_config

    if selected_config(root, project).electrical is None:
        if required:
            raise ValueError(
                f"{project}: no electrical contract; run kicad-team electrical --project {project} --init"
            )
        log.event("electrical", "NOT_CONFIGURED", project=project)
        return
    simulator = project_simulator(root, project, log)
    report = root / "build" / f"electrical-{project}.json"
    summary_args = (
        ("--native-summary", native_summary) if native_summary else ("--runner", "container")
    )

    def charts() -> None:
        analysis = read_model(report, ElectricalAnalysisReport)
        log.run(
            "electrical-charts",
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.electrical_charts",
                "--root",
                str(root),
                "--receipt",
                analysis.run_directory,
                "--format",
                "json",
            ),
            cwd=root,
        )

    try:
        log.run(
            "electrical-check",
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.electrical",
                "--root",
                str(root),
                "--project",
                project,
                *summary_args,
                "--ngspice",
                simulator,
                "--format",
                "json",
            ),
            cwd=root,
            stdout_path=report,
        )
    except RuntimeError:
        # Preserve charts from measured failures without replacing the gate error.
        try:
            charts()
        except (OSError, ValueError, RuntimeError) as exc:
            log.event("electrical-charts", "UNAVAILABLE", error=str(exc))
        raise
    charts()
