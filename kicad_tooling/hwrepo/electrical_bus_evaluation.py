"""Coordinate authored bus requirements against admitted netlist evidence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, TypeVar

from pydantic import Field, model_validator

from .analysis_state_models import AnalysisNotApplicable, AnalysisPending
from .can_termination_contract import can_termination_checks
from .can_termination_models import CanTerminationAnalysis
from .electrical_netlist_evidence import (
    ElectricalNetlistEvidence,
    NetlistEvidenceNotRequested,
    NetlistEvidenceObserved,
)
from .electrical_report_models import ElectricalCheck
from .i2c_pullup_contract import i2c_pullup_checks
from .i2c_pullup_models import I2cPullupAnalysis
from .model_primitives import Identifier, StrictModel
from .models import NetlistContract
from .spi_contract import spi_checks
from .spi_models import SpiAnalysis
from .usb_c_contract import usb_c_checks
from .usb_c_models import UsbCAnalysis

I2cPullupRequirement = Annotated[
    I2cPullupAnalysis | AnalysisPending | AnalysisNotApplicable,
    Field(discriminator="mode"),
]
CanTerminationRequirement = Annotated[
    CanTerminationAnalysis | AnalysisPending | AnalysisNotApplicable,
    Field(discriminator="mode"),
]
UsbCRequirement = Annotated[
    UsbCAnalysis | AnalysisPending | AnalysisNotApplicable,
    Field(discriminator="mode"),
]
SpiRequirement = Annotated[
    SpiAnalysis | AnalysisPending | AnalysisNotApplicable,
    Field(discriminator="mode"),
]


class ElectricalBusEvaluationRequest(StrictModel):
    """Narrow bus-family inputs with evidence and absence states kept explicit."""

    project_id: Identifier
    netlist_evidence: ElectricalNetlistEvidence
    i2c_pullups: I2cPullupRequirement | None = None
    can_termination: CanTerminationRequirement | None = None
    usb_c: UsbCRequirement | None = None
    spi: SpiRequirement | None = None

    @model_validator(mode="after")
    def evidence_matches_requirements(self) -> ElectricalBusEvaluationRequest:
        if self.netlist_evidence.project_id != self.project_id:
            raise ValueError("Bus requirements and netlist evidence belong to different projects")
        configured = any(
            isinstance(requirement, requirement_type)
            for requirement, requirement_type in (
                (self.i2c_pullups, I2cPullupAnalysis),
                (self.can_termination, CanTerminationAnalysis),
                (self.usb_c, UsbCAnalysis),
                (self.spi, SpiAnalysis),
            )
        )
        if configured and isinstance(self.netlist_evidence, NetlistEvidenceNotRequested):
            raise ValueError("Configured bus requirements need a requested netlist capture")
        return self


Requirement = TypeVar("Requirement")


def _evaluate_requirement(
    check_id: str,
    requirement: Requirement | AnalysisPending | AnalysisNotApplicable | None,
    netlist: NetlistContract | None,
    evaluator: Callable[[Requirement, NetlistContract], tuple[ElectricalCheck, ...]],
) -> tuple[ElectricalCheck, ...]:
    if requirement is None:
        return ()
    if isinstance(requirement, AnalysisPending | AnalysisNotApplicable):
        return (
            ElectricalCheck(
                id=check_id,
                status=(
                    "NOT_CONFIGURED"
                    if isinstance(requirement, AnalysisPending)
                    else "NOT_APPLICABLE"
                ),
                detail=requirement.reason,
            ),
        )
    if netlist is None:
        return (
            ElectricalCheck(
                id=check_id,
                status="FAIL",
                detail="No current source-bound netlist; inspect netlist-evidence.json.",
            ),
        )
    return evaluator(requirement, netlist)


def evaluate_electrical_bus_requirements(
    request: ElectricalBusEvaluationRequest,
) -> tuple[ElectricalCheck, ...]:
    """Evaluate I2C, CAN, USB-C, and SPI checks in the established report order."""
    netlist = (
        request.netlist_evidence.observed
        if isinstance(request.netlist_evidence, NetlistEvidenceObserved)
        else None
    )
    return (
        *_evaluate_requirement("i2c-pullups", request.i2c_pullups, netlist, i2c_pullup_checks),
        *_evaluate_requirement(
            "can-termination", request.can_termination, netlist, can_termination_checks
        ),
        *_evaluate_requirement("usb-c", request.usb_c, netlist, usb_c_checks),
        *_evaluate_requirement("spi", request.spi, netlist, spi_checks),
    )
