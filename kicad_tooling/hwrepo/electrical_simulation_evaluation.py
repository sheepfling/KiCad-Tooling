"""Run source-bound electrical simulation cases through one typed lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import model_validator

from .electrical_report_models import ElectricalCheck
from .electrical_simulation_evidence import (
    ElectricalSimulationEvaluation,
    SimulationCaseResult,
    SimulationVersionNotRequested,
    SimulationVersionObserved,
    SimulationVersionUnavailable,
)
from .electrical_simulation_models import SimulationCase
from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel
from .spice import (
    SimulatorVersionMismatch,
    executable_path,
    observed_versions,
    run_case,
    simulator_version,
)


class ElectricalSimulationEvaluationRequest(StrictModel):
    """Reviewed simulator inputs for the cases selected by one project contract."""

    project_id: Identifier
    root: Path
    output: Path
    ngspice: NonEmptyText
    expected_version: NonEmptyText
    source_sha256: Mapping[RepositoryPath, Digest]
    cases: tuple[SimulationCase, ...]

    @model_validator(mode="after")
    def cases_match_current_design_sources(self) -> ElectricalSimulationEvaluationRequest:
        case_ids = [case.id.casefold() for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("Simulation request contains duplicate case IDs")
        for case in self.cases:
            if dict(case.source_sha256) != dict(self.source_sha256):
                raise ValueError(f"{case.id}: stale or incomplete reviewed design source hashes")
        return self


def evaluate_electrical_simulations(
    request: ElectricalSimulationEvaluationRequest,
) -> ElectricalSimulationEvaluation:
    """Capture version once, then retain each case command and its bounded checks."""
    if not request.cases:
        return ElectricalSimulationEvaluation(
            project_id=request.project_id,
            version=SimulationVersionNotRequested(project_id=request.project_id),
            cases=(),
        )

    executable = executable_path(request.ngspice)
    try:
        version_command = simulator_version(request.output, executable, request.expected_version)
    except ValueError as exc:
        failed_version_command = exc.command if isinstance(exc, SimulatorVersionMismatch) else None
        unavailable = SimulationVersionUnavailable(
            project_id=request.project_id,
            expected_version=request.expected_version,
            reason=str(exc),
            command=failed_version_command,
            observed_versions=(
                observed_versions(failed_version_command)
                if failed_version_command is not None
                else ()
            ),
        )
        not_run = tuple(
            SimulationCaseResult(
                project_id=request.project_id,
                case=case,
                command=None,
                checks=(ElectricalCheck(id=case.id, status="NOT_RUN", detail=str(exc)),),
            )
            for case in request.cases
        )
        return ElectricalSimulationEvaluation(
            project_id=request.project_id,
            version=unavailable,
            cases=not_run,
        )

    version = SimulationVersionObserved(
        project_id=request.project_id,
        expected_version=request.expected_version,
        observed_versions=observed_versions(version_command),
        command=version_command,
    )
    cases: list[SimulationCaseResult] = []
    for case in request.cases:
        try:
            command, checks = run_case(request.root, request.output, executable, case)
        except (OSError, ValueError) as exc:
            cases.append(
                SimulationCaseResult(
                    project_id=request.project_id,
                    case=case,
                    command=None,
                    checks=(ElectricalCheck(id=case.id, status="FAIL", detail=str(exc)),),
                )
            )
        else:
            cases.append(
                SimulationCaseResult(
                    project_id=request.project_id,
                    case=case,
                    command=command,
                    checks=checks,
                )
            )
    return ElectricalSimulationEvaluation(
        project_id=request.project_id,
        version=version,
        cases=tuple(cases),
    )
