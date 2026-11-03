"""Guard the source-bound simulator lifecycle and its no-run states."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.electrical_simulation_evaluation import (
    ElectricalSimulationEvaluationRequest,
    evaluate_electrical_simulations,
)
from kicad_tooling.hwrepo.electrical_simulation_evidence import (
    SimulationVersionObserved,
    SimulationVersionUnavailable,
)
from kicad_tooling.hwrepo.electrical_simulation_models import (
    SimulationMeasure,
    TransientAnalysis,
)
from kicad_tooling.hwrepo.models import ElectricalCheck
from kicad_tooling.hwrepo.spice import SimulatorVersionMismatch

pytestmark = pytest.mark.architecture

PROJECT_ID = "controller"
SOURCE_HASHES = {"projects/controller/controller.kicad_sch": "a" * 64}


def _case() -> TransientAnalysis:
    return TransientAnalysis(
        id="startup",
        basis="Reviewed startup response",
        deck="projects/controller/startup.cir",
        model_sha256={"projects/controller/startup.cir": "b" * 64},
        source_sha256=SOURCE_HASHES,
        measures=(
            SimulationMeasure(
                id="vout",
                expression="V(out)",
                statistic="max",
                unit="V",
                start=0,
                stop=1,
                minimum=4.5,
            ),
        ),
        step_s=0.1,
        stop_s=1,
    )


def _request(*cases: TransientAnalysis) -> ElectricalSimulationEvaluationRequest:
    return ElectricalSimulationEvaluationRequest(
        project_id=PROJECT_ID,
        root=Path("/workspace/project"),
        output=Path("/workspace/project/build/electrical/run"),
        ngspice="ngspice",
        expected_version="47",
        source_sha256=SOURCE_HASHES,
        cases=cases,
    )


def _command(*, stdout: str = "", returncode: int = 0) -> CommandEvidence:
    return CommandEvidence(
        argv=("ngspice",),
        started_utc="2026-10-31T00:00:00Z",
        returncode=returncode,
        stdout=stdout,
    )


def test_no_cases_are_explicitly_not_requested_and_run_no_commands() -> None:
    with (
        patch("kicad_tooling.hwrepo.electrical_simulation_evaluation.simulator_version") as version,
        patch("kicad_tooling.hwrepo.electrical_simulation_evaluation.run_case") as run_case,
    ):
        result = evaluate_electrical_simulations(_request())

    assert result.version.state == "NOT_REQUESTED"
    assert result.cases == ()
    version.assert_not_called()
    run_case.assert_not_called()


def test_case_request_must_match_the_current_design_source_hashes() -> None:
    case = _case().model_copy(
        update={"source_sha256": {"projects/controller/old.kicad_sch": "c" * 64}}
    )

    with pytest.raises(ValidationError, match="stale or incomplete reviewed design source hashes"):
        _request(case)


def test_wrong_simulator_version_retains_command_and_marks_each_case_not_run() -> None:
    version_command = _command(stdout="ngspice-46")
    error = SimulatorVersionMismatch("Exact ngspice 47 required; observed ('46',)", version_command)
    with (
        patch(
            "kicad_tooling.hwrepo.electrical_simulation_evaluation.simulator_version",
            side_effect=error,
        ),
        patch("kicad_tooling.hwrepo.electrical_simulation_evaluation.run_case") as run_case,
    ):
        result = evaluate_electrical_simulations(_request(_case()))

    assert isinstance(result.version, SimulationVersionUnavailable)
    assert result.version.command == version_command
    assert result.version.observed_versions == ("46",)
    assert [(row.checks[0].id, row.checks[0].status) for row in result.cases] == [
        ("startup", "NOT_RUN")
    ]
    run_case.assert_not_called()


def test_matching_version_runs_each_case_and_retains_its_command_and_checks() -> None:
    version_command = _command(stdout="ngspice-47")
    case_command = _command(stdout="check0 = 4.95")
    checks = (ElectricalCheck(id="startup/vout", status="PASS", detail="Within limit."),)
    with (
        patch(
            "kicad_tooling.hwrepo.electrical_simulation_evaluation.simulator_version",
            return_value=version_command,
        ),
        patch(
            "kicad_tooling.hwrepo.electrical_simulation_evaluation.run_case",
            return_value=(case_command, checks),
        ) as run_case,
    ):
        result = evaluate_electrical_simulations(_request(_case()))

    assert isinstance(result.version, SimulationVersionObserved)
    assert result.version.command == version_command
    assert result.version.observed_versions == ("47",)
    assert result.cases[0].case.id == "startup"
    assert result.cases[0].command == case_command
    assert result.cases[0].checks == checks
    run_case.assert_called_once()


def test_case_preparation_error_is_scoped_to_that_case() -> None:
    with (
        patch(
            "kicad_tooling.hwrepo.electrical_simulation_evaluation.simulator_version",
            return_value=_command(stdout="ngspice-47"),
        ),
        patch(
            "kicad_tooling.hwrepo.electrical_simulation_evaluation.run_case",
            side_effect=ValueError("Stale reviewed model hash"),
        ),
    ):
        result = evaluate_electrical_simulations(_request(_case()))

    assert result.cases[0].command is None
    assert [(row.id, row.status, row.detail) for row in result.cases[0].checks] == [
        ("startup", "FAIL", "Stale reviewed model hash")
    ]


def test_simulation_owner_is_bounded_and_runner_has_no_case_predicates() -> None:
    repository_root = Path(__file__).parents[1]
    owner_path = repository_root / "kicad_tooling/hwrepo/electrical_simulation_evaluation.py"
    evidence_path = repository_root / "kicad_tooling/hwrepo/electrical_simulation_evidence.py"
    runner = (repository_root / "kicad_tooling/hwrepo/electrical_runner.py").read_text(
        encoding="utf-8"
    )
    owner = owner_path.read_text(encoding="utf-8")

    assert len(owner.splitlines()) < 500
    assert len(evidence_path.read_text(encoding="utf-8").splitlines()) < 500
    assert "ElectricalSimulationEvaluationRequest" in runner
    assert "evaluate_electrical_simulations" in runner
    assert "simulator_version(" not in runner
    assert "run_case(" not in runner
    assert "electrical_runner" not in owner
