"""Typed bus-requirement routing and absence-state regressions."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.analysis_state_models import AnalysisNotApplicable, AnalysisPending
from kicad_tooling.hwrepo.electrical_bus_evaluation import (
    ElectricalBusEvaluationRequest,
    evaluate_electrical_bus_requirements,
)
from kicad_tooling.hwrepo.electrical_netlist_evidence import (
    NetlistEvidenceNotRequested,
    NetlistEvidenceUnavailable,
    admit_netlist_evidence,
)
from kicad_tooling.hwrepo.i2c_pullup_models import (
    I2cPullupAnalysis,
    I2cPullupBusRequirement,
    I2cPullupLineRequirement,
)
from kicad_tooling.hwrepo.models import ContractCoachReport

pytestmark = pytest.mark.architecture

PROJECT_ID = "controller"
SOURCE_HASHES = {"projects/controller/controller.kicad_sch": "a" * 64}


def _i2c_requirement() -> I2cPullupAnalysis:
    return I2cPullupAnalysis(
        basis="Reviewed pull-up requirements",
        buses=(
            I2cPullupBusRequirement(
                id="i2c1",
                basis="Controller I2C bus",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="3V3", minimum_ohms=2_000, maximum_ohms=10_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="3V3", minimum_ohms=2_000, maximum_ohms=10_000
                ),
            ),
        ),
    )


def _unavailable_evidence() -> NetlistEvidenceUnavailable:
    report = ContractCoachReport(
        status="BLOCKED",
        project_id=PROJECT_ID,
        issues=("Native export is unavailable",),
    )
    evidence = admit_netlist_evidence(report, PROJECT_ID, SOURCE_HASHES)
    assert isinstance(evidence, NetlistEvidenceUnavailable)
    return evidence


def test_not_requested_evidence_preserves_pending_and_not_applicable_bus_states() -> None:
    request = ElectricalBusEvaluationRequest(
        project_id=PROJECT_ID,
        netlist_evidence=NetlistEvidenceNotRequested(project_id=PROJECT_ID),
        i2c_pullups=AnalysisPending(reason="Review the I2C bias network"),
        can_termination=AnalysisNotApplicable(
            mode="not_applicable", reason="No CAN bus is present"
        ),
    )

    checks = evaluate_electrical_bus_requirements(request)

    assert [(row.id, row.status) for row in checks] == [
        ("i2c-pullups", "NOT_CONFIGURED"),
        ("can-termination", "NOT_APPLICABLE"),
    ]


def test_concrete_bus_requirement_cannot_claim_no_netlist_was_requested() -> None:
    with pytest.raises(ValidationError, match="need a requested netlist capture"):
        ElectricalBusEvaluationRequest(
            project_id=PROJECT_ID,
            netlist_evidence=NetlistEvidenceNotRequested(project_id=PROJECT_ID),
            i2c_pullups=_i2c_requirement(),
        )


def test_unavailable_netlist_fails_only_configured_bus_checks_in_stable_order() -> None:
    request = ElectricalBusEvaluationRequest(
        project_id=PROJECT_ID,
        netlist_evidence=_unavailable_evidence(),
        i2c_pullups=_i2c_requirement(),
        can_termination=AnalysisNotApplicable(
            mode="not_applicable", reason="No CAN bus is present"
        ),
        spi=AnalysisPending(reason="Review the SPI roster"),
    )

    checks = evaluate_electrical_bus_requirements(request)

    assert [(row.id, row.status) for row in checks] == [
        ("i2c-pullups", "FAIL"),
        ("can-termination", "NOT_APPLICABLE"),
        ("spi", "NOT_CONFIGURED"),
    ]
    assert "No current source-bound netlist" in checks[0].detail


def test_bus_evaluation_request_rejects_cross_project_evidence_and_opaque_fields() -> None:
    with pytest.raises(ValueError, match="different projects"):
        ElectricalBusEvaluationRequest(
            project_id=PROJECT_ID,
            netlist_evidence=NetlistEvidenceNotRequested(project_id="other"),
        )
    with pytest.raises(ValidationError):
        ElectricalBusEvaluationRequest(
            project_id=PROJECT_ID,
            netlist_evidence=NetlistEvidenceNotRequested(project_id=PROJECT_ID),
            options={"bus": "i2c"},
        )


def test_bus_evaluation_owner_has_a_bounded_runner_boundary() -> None:
    repository_root = Path(__file__).parents[1]
    owner_path = repository_root / "kicad_tooling/hwrepo/electrical_bus_evaluation.py"
    runner = (repository_root / "kicad_tooling/hwrepo/electrical_runner.py").read_text(
        encoding="utf-8"
    )
    owner = owner_path.read_text(encoding="utf-8")

    assert len(owner.splitlines()) < 500
    assert "evaluate_electrical_bus_requirements" in runner
    for direct_predicate in (
        "i2c_pullup_checks",
        "can_termination_checks",
        "usb_c_checks",
        "spi_checks",
    ):
        assert direct_predicate not in runner
