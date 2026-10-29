"""Recheck retained electrical evidence without executing a simulator or project code."""

from __future__ import annotations

from pathlib import Path

from .command_evidence_models import CommandEvidence
from .contracts import read_model, repo_path
from .electrical import (
    bind_electrical_inputs,
    load_analysis,
    policy_issues,
    selected_config,
    simulation_cases,
)
from .electrical_analysis_contract_models import ElectricalAnalysisContract
from .electrical_evidence_contract_checks import retained_electrical_contract_checks
from .evidence import digest, evidence_path, verify_source
from .models import (
    ElectricalAnalysisReport,
    EvidenceFile,
    ReleaseClass,
    SourceState,
)
from .native_netlist_evidence import native_netlist_evidence_matches
from .project_models import (
    ProjectKind,
    ProjectRecord,
)
from .spice import measured_checks, observed_versions, simulation_deck, waveform_checks


def required_projects(
    root: Path, projects: tuple[ProjectRecord, ...], release_class: ReleaseClass
) -> tuple[str, ...]:
    """Declared contracts always gate releases; buildable boards must declare one."""
    required: list[str] = []
    for project in projects:
        config = selected_config(root, project.id)
        if config.electrical is not None:
            required.append(project.id)
        elif release_class is not ReleaseClass.ENGINEERING_REVIEW and config.kind in {
            ProjectKind.PCB,
            ProjectKind.SCHEMATIC,
        }:
            raise ValueError(
                f"{project.id}: build releases require reviewed electrical requirements; "
                f"run kicad-team electrical --project {project.id} --init and review applicability"
            )
    return tuple(required)


def verify_electrical(
    root: Path, reference: EvidenceFile, source: SourceState, project_id: str, native: EvidenceFile
) -> ElectricalAnalysisReport:
    """Check source, exact cases, logs, decks and waveform coverage, including after restore."""
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
    bind_electrical_inputs(
        root,
        config,
        contract,
        report.input_sha256,
        mismatch_message="Electrical evidence inputs differ from reviewed source/model bindings",
    )
    _verify_artifact_hashes(path.parent, report)

    def artifact(name: str) -> Path:
        if name not in report.artifacts_sha256:
            raise ValueError(f"Electrical evidence omits required artifact: {name}")
        return repo_path(path.parent, name)

    if read_model(artifact("requirements.json"), ElectricalAnalysisContract) != contract:
        raise ValueError("Retained electrical requirements differ from committed requirements")
    retained_checks, requires_pcb_connectivity, native_identity = (
        retained_electrical_contract_checks(root, config, contract, report, native, artifact)
    )
    checks = list(retained_checks)
    cases = simulation_cases(contract)
    expected_commands: set[str] = {case.id for case in cases}
    if cases:
        expected_commands.add("version")
    if requires_pcb_connectivity:
        expected_commands.add("pcb-connectivity")
    if set(report.commands) != expected_commands:
        raise ValueError("Electrical evidence command inventory differs from required cases")
    if cases:
        version = read_model(artifact("ngspice-version.command.json"), CommandEvidence)
        if (
            version != report.commands["version"]
            or version.returncode != 0
            or version.error
            or contract.ngspice_version not in observed_versions(version)
        ):
            raise ValueError("Electrical evidence has no successful exact simulator version probe")
    for case in cases:
        command = read_model(artifact(f"{case.id}/ngspice.command.json"), CommandEvidence)
        if command != report.commands[case.id]:
            raise ValueError(f"{case.id}: electrical command evidence differs")
        if artifact(f"{case.id}/simulation.cir").read_text() != simulation_deck(root, case):
            raise ValueError(f"{case.id}: retained simulation deck differs from reviewed inputs")
        checks.extend(measured_checks(case, command))
        checks.extend(waveform_checks(artifact(f"{case.id}/waveforms.raw"), case))
    if (
        tuple(checks) != report.checks
        or not checks
        or any(row.status not in {"PASS", "NOT_APPLICABLE"} for row in checks)
    ):
        raise ValueError("Retained electrical checks fail or omit reviewed requirements")
    evidence_path(root, reference)
    if native_identity is not None and not native_netlist_evidence_matches(
        evidence_path(root, native), native_identity
    ):
        raise ValueError("Native netlist evidence changed during electrical verification")
    bind_electrical_inputs(root, config, contract, report.input_sha256)
    _verify_artifact_hashes(path.parent, report)
    return report


def _verify_artifact_hashes(directory: Path, report: ElectricalAnalysisReport) -> None:
    for name, expected in report.artifacts_sha256.items():
        if digest(repo_path(directory, name)) != expected:
            raise ValueError(f"Missing or changed electrical artifact: {name}")
