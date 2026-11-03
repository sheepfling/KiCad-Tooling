"""Typed simulator-version and per-case evidence retained during analysis."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

from .command_evidence_models import CommandEvidence
from .electrical_simulation_models import SimulationCase
from .model_primitives import Identifier, NonEmptyText, StrictModel
from .models import ElectricalCheck


class SimulationVersionNotRequested(StrictModel):
    """No simulation cases required a simulator-version capture."""

    state: Literal["NOT_REQUESTED"] = "NOT_REQUESTED"
    project_id: Identifier


class SimulationVersionUnavailable(StrictModel):
    """Simulator version capture ran but did not establish the requested version."""

    state: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    project_id: Identifier
    expected_version: NonEmptyText
    reason: NonEmptyText
    command: CommandEvidence | None = None
    observed_versions: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def unavailable_version_was_not_observed(self) -> SimulationVersionUnavailable:
        if (
            self.command is not None
            and self.command.returncode == 0
            and self.command.error is None
            and self.expected_version in self.observed_versions
        ):
            raise ValueError("A successfully observed simulator version cannot be unavailable")
        return self


class SimulationVersionObserved(StrictModel):
    """Exact requested simulator version and its successful command receipt."""

    state: Literal["OBSERVED"] = "OBSERVED"
    project_id: Identifier
    expected_version: NonEmptyText
    observed_versions: tuple[NonEmptyText, ...]
    command: CommandEvidence

    @model_validator(mode="after")
    def command_proves_expected_version(self) -> SimulationVersionObserved:
        if self.command.returncode != 0 or self.command.error is not None:
            raise ValueError("Observed simulator version needs a successful command")
        if self.expected_version not in self.observed_versions:
            raise ValueError("Observed simulator version does not match the reviewed version")
        return self


SimulationVersionEvidence: TypeAlias = Annotated[
    SimulationVersionNotRequested | SimulationVersionUnavailable | SimulationVersionObserved,
    Field(discriminator="state"),
]


class SimulationCaseResult(StrictModel):
    """One source-bound authored case and its command/check outcome."""

    project_id: Identifier
    case: SimulationCase
    command: CommandEvidence | None
    checks: tuple[ElectricalCheck, ...]

    @model_validator(mode="after")
    def checks_belong_to_case(self) -> SimulationCaseResult:
        if not self.checks:
            raise ValueError("A simulation case result must retain at least one check")
        if any(
            check.id != self.case.id and not check.id.startswith(f"{self.case.id}/")
            for check in self.checks
        ):
            raise ValueError("Simulation checks must belong to their authored case")
        return self


class ElectricalSimulationEvaluation(StrictModel):
    """Typed simulator lifecycle result before public checks and commands are assembled."""

    project_id: Identifier
    version: SimulationVersionEvidence
    cases: tuple[SimulationCaseResult, ...]

    @model_validator(mode="after")
    def version_and_case_states_agree(self) -> ElectricalSimulationEvaluation:
        if self.version.project_id != self.project_id or any(
            result.project_id != self.project_id for result in self.cases
        ):
            raise ValueError("Simulation evidence and cases belong to another project")
        case_ids = [result.case.id.casefold() for result in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("Simulation evaluation contains duplicate case IDs")
        if isinstance(self.version, SimulationVersionNotRequested):
            if self.cases:
                raise ValueError("Unrequested simulator evidence cannot contain case results")
        elif not self.cases:
            raise ValueError("Requested simulator evidence must retain its case results")
        if isinstance(self.version, SimulationVersionUnavailable) and any(
            result.command is not None or any(check.status != "NOT_RUN" for check in result.checks)
            for result in self.cases
        ):
            raise ValueError("Unavailable simulator version must leave all cases not run")
        return self
