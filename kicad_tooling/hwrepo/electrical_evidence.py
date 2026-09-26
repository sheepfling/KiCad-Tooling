"""Recheck retained electrical evidence without executing a simulator or project code."""
from __future__ import annotations

from pathlib import Path

from .contracts import read_model, repo_path
from .electrical import (
    bound_inputs,
    grounding_checks,
    load_analysis,
    policy_issues,
    power_budget_checks,
    selected_config,
    simulation_cases,
)
from .evidence import digest, evidence_path, verify_source
from .models import (
    AnalysisNotApplicable,
    CommandEvidence,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    ElectricalCheck,
    EvidenceFile,
    GroundingAnalysis,
    ProjectKind,
    ProjectRecord,
    ReleaseClass,
    SourceState,
)
from .spice import measured_checks, observed_versions, simulation_deck, waveform_checks


def required_projects(root: Path, projects: tuple[ProjectRecord, ...],
                      release_class: ReleaseClass) -> tuple[str, ...]:
    """Declared contracts always gate releases; buildable boards must declare one."""
    required: list[str] = []
    for project in projects:
        config = selected_config(root, project.id)
        if config.electrical is not None:
            required.append(project.id)
        elif (release_class is not ReleaseClass.ENGINEERING_REVIEW
              and config.kind in {ProjectKind.PCB, ProjectKind.SCHEMATIC}):
            raise ValueError(f"{project.id}: build releases require reviewed electrical requirements; "
                             f"run kicad-team electrical --project {project.id} --init and review applicability")
    return tuple(required)


def verify_electrical(root: Path, reference: EvidenceFile, source: SourceState,
                      project_id: str, native: EvidenceFile) -> ElectricalAnalysisReport:
    """Check source, exact cases, logs, decks and waveform coverage, including after restore."""
    from ..validate import read_netlist

    path = evidence_path(root, reference)
    report = read_model(path, ElectricalAnalysisReport)
    verify_source(report.source, source)
    if report.project_id != project_id or report.status != "PASS":
        raise ValueError("Electrical report identifies a different project or did not pass")
    config = selected_config(root, project_id)
    contract = load_analysis(root, config)
    if contract is None:
        raise ValueError("Electrical requirements are missing")
    issues = policy_issues(root, config)
    if issues:
        raise ValueError("Electrical requirements are invalid: " + "; ".join(issues))
    if dict(report.input_sha256) != bound_inputs(root, config, contract):
        raise ValueError("Electrical evidence inputs differ from reviewed source/model bindings")
    for name, expected in report.artifacts_sha256.items():
        if digest(repo_path(path.parent, name)) != expected:
            raise ValueError(f"Missing or changed electrical artifact: {name}")

    def artifact(name: str) -> Path:
        if name not in report.artifacts_sha256:
            raise ValueError(f"Electrical evidence omits required artifact: {name}")
        return repo_path(path.parent, name)

    if read_model(artifact("requirements.json"), ElectricalAnalysisContract) != contract:
        raise ValueError("Retained electrical requirements differ from committed requirements")
    checks: list[ElectricalCheck] = []
    if isinstance(contract.grounding, GroundingAnalysis):
        checks.extend(grounding_checks(contract.grounding, read_netlist(
            evidence_path(root, native).parent / "netlist.xml")))
    else:
        if not isinstance(contract.grounding, AnalysisNotApplicable):
            raise ValueError("Grounding requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(ElectricalCheck(id="grounding", status="NOT_APPLICABLE",
                                      detail=contract.grounding.reason))
    if isinstance(contract.high_frequency, AnalysisNotApplicable):
        checks.append(ElectricalCheck(id="high-frequency", status="NOT_APPLICABLE",
                                      detail=contract.high_frequency.reason))
    checks.extend(power_budget_checks(contract.power))
    cases = simulation_cases(contract)
    expected_commands: set[str] = {case.id for case in cases}
    if cases:
        expected_commands.add("version")
    if set(report.commands) != expected_commands:
        raise ValueError("Electrical evidence command inventory differs from required cases")
    if cases:
        version = read_model(artifact("ngspice-version.command.json"), CommandEvidence)
        if (version != report.commands["version"] or version.returncode != 0 or version.error
                or contract.ngspice_version not in observed_versions(version)):
            raise ValueError("Electrical evidence has no successful exact simulator version probe")
    for case in cases:
        command = read_model(artifact(f"{case.id}/ngspice.command.json"), CommandEvidence)
        if command != report.commands[case.id]:
            raise ValueError(f"{case.id}: electrical command evidence differs")
        if artifact(f"{case.id}/simulation.cir").read_text() != simulation_deck(root, case):
            raise ValueError(f"{case.id}: retained simulation deck differs from reviewed inputs")
        checks.extend(measured_checks(case, command))
        checks.extend(waveform_checks(artifact(f"{case.id}/waveforms.raw"), case))
    if (tuple(checks) != report.checks or not checks
            or any(row.status not in {"PASS", "NOT_APPLICABLE"} for row in checks)):
        raise ValueError("Retained electrical checks fail or omit reviewed requirements")
    return report
