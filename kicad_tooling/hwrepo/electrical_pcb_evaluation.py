"""Evaluate electrical PCB and test-access requirements from typed evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, model_validator

from .analysis_state_models import AnalysisNotApplicable, AnalysisPending
from .contracts import repo_path
from .electrical_netlist_evidence import (
    ElectricalNetlistEvidence,
    NetlistEvidenceNotRequested,
    NetlistEvidenceObserved,
)
from .electrical_pcb_evidence import (
    ElectricalPcbEvidence,
    PcbEvidenceNotRequested,
    PcbEvidenceObserved,
    PcbEvidenceUnavailable,
)
from .electrical_report_models import ElectricalCheck
from .evidence import digest
from .model_primitives import Digest, Identifier, StrictModel
from .pcb_return_path_checks import pcb_return_path_checks
from .pcb_return_path_models import PcbReturnPathsAnalysis
from .pcb_test_access_models import TestAccessAnalysis
from .project_models import ProjectConfig, ProjectKind
from .test_access import (
    evaluate_test_access_checks,
    pcb_access_probe_request_set,
    pcb_accessibility_checks,
    pcb_probe_envelope_checks,
)

PcbReturnPathsRequirement = Annotated[
    PcbReturnPathsAnalysis | AnalysisPending | AnalysisNotApplicable,
    Field(discriminator="mode"),
]
TestAccessRequirement = Annotated[
    TestAccessAnalysis | AnalysisPending | AnalysisNotApplicable,
    Field(discriminator="mode"),
]


class ElectricalPcbReturnEvaluationRequest(StrictModel):
    """Only the project, return requirement, and its native PCB evidence."""

    project_id: Identifier
    root: Path
    config: ProjectConfig
    requirement: PcbReturnPathsRequirement
    evidence: ElectricalPcbEvidence
    expected_probe_sha256: Digest | None = None

    @model_validator(mode="after")
    def project_and_capture_match(self) -> ElectricalPcbReturnEvaluationRequest:
        if self.config.project_id != self.project_id or self.evidence.project_id != self.project_id:
            raise ValueError("PCB return requirements and evidence belong to another project")
        if isinstance(self.requirement, PcbReturnPathsAnalysis) and isinstance(
            self.evidence, PcbEvidenceNotRequested
        ):
            raise ValueError(  # noqa: TRY004 - valid evidence state conflicts with requested work
                "Configured PCB return requirements need a requested capture"
            )
        if (
            isinstance(self.requirement, PcbReturnPathsAnalysis)
            and isinstance(self.evidence, PcbEvidenceObserved)
            and self.expected_probe_sha256 is None
        ):
            raise ValueError("PCB return evidence needs the expected native probe digest")
        return self


class ElectricalTestAccessEvaluationRequest(StrictModel):
    """Schematic access, board access, and probe evidence for one project."""

    project_id: Identifier
    root: Path
    config: ProjectConfig
    requirement: TestAccessRequirement | None
    netlist_evidence: ElectricalNetlistEvidence
    pcb_evidence: ElectricalPcbEvidence

    @model_validator(mode="after")
    def project_and_capture_match(self) -> ElectricalTestAccessEvaluationRequest:
        if self.config.project_id != self.project_id:
            raise ValueError("Test-access configuration belongs to another project")
        if self.netlist_evidence.project_id != self.project_id:
            raise ValueError("Test-access netlist evidence belongs to another project")
        if self.pcb_evidence.project_id != self.project_id:
            raise ValueError("Test-access PCB evidence belongs to another project")
        if isinstance(self.requirement, TestAccessAnalysis):
            if isinstance(self.netlist_evidence, NetlistEvidenceNotRequested):
                raise ValueError(  # noqa: TRY004 - valid evidence state conflicts with requested work
                    "Configured test-access requirements need a netlist capture"
                )
            if pcb_access_probe_request_set(self.requirement) is not None and isinstance(
                self.pcb_evidence, PcbEvidenceNotRequested
            ):
                raise ValueError("Configured probe envelopes need a requested PCB capture")
        return self


def evaluate_pcb_return_paths(
    request: ElectricalPcbReturnEvaluationRequest,
) -> tuple[ElectricalCheck, ...]:
    """Evaluate return paths while retaining unavailable and wrong-source states."""
    requirement = request.requirement
    if isinstance(requirement, AnalysisPending | AnalysisNotApplicable):
        return (
            ElectricalCheck(
                id="pcb-return-paths",
                status=(
                    "NOT_CONFIGURED"
                    if isinstance(requirement, AnalysisPending)
                    else "NOT_APPLICABLE"
                ),
                detail=requirement.reason,
            ),
        )
    if request.config.kind is not ProjectKind.PCB:
        return (
            ElectricalCheck(
                id="pcb-return-paths/source",
                status="FAIL",
                detail="PCB return-path requirements need an authoritative PCB project.",
            ),
        )
    if isinstance(request.evidence, PcbEvidenceUnavailable):
        return (
            ElectricalCheck(
                id="pcb-return-paths/native-probe",
                status="NOT_RUN",
                detail=request.evidence.reason,
            ),
        )
    assert isinstance(request.evidence, PcbEvidenceObserved)
    assert request.expected_probe_sha256 is not None
    board_path = repo_path(request.root, request.config.project).with_suffix(".kicad_pcb")
    return pcb_return_path_checks(
        requirement,
        request.evidence.snapshot,
        board_sha256=digest(board_path),
        kicad_version=request.config.kicad_version,
        image=request.config.image,
        probe_sha256=request.expected_probe_sha256,
    )


def evaluate_electrical_test_access(
    request: ElectricalTestAccessEvaluationRequest,
) -> tuple[ElectricalCheck, ...]:
    """Evaluate schematic, pad-access, and probe-envelope stages in report order."""
    requirement = request.requirement
    if isinstance(requirement, AnalysisPending | AnalysisNotApplicable):
        status = "NOT_CONFIGURED" if isinstance(requirement, AnalysisPending) else "NOT_APPLICABLE"
        return (
            ElectricalCheck(id="test-access/schematic", status=status, detail=requirement.reason),
            ElectricalCheck(
                id="test-access/pcb-accessibility", status=status, detail=requirement.reason
            ),
        )
    if requirement is None:
        detail_schematic = (
            "No test_access requirement or explicit not-applicable decision is "
            "recorded in tests/electrical.json."
        )
        detail_pcb = (
            "No PCB test-access requirements or explicit not-applicable decision "
            "is recorded in tests/electrical.json."
        )
        return (
            ElectricalCheck(
                id="test-access/schematic", status="NOT_CONFIGURED", detail=detail_schematic
            ),
            ElectricalCheck(
                id="test-access/pcb-accessibility", status="NOT_CONFIGURED", detail=detail_pcb
            ),
        )

    checks: list[ElectricalCheck] = []
    if isinstance(request.netlist_evidence, NetlistEvidenceObserved):
        checks.extend(evaluate_test_access_checks(requirement, request.netlist_evidence.observed))
    else:
        checks.append(
            ElectricalCheck(
                id="test-access/schematic",
                status="FAIL",
                detail="No current source-bound netlist; inspect netlist-evidence.json.",
            )
        )

    pcb_accessibility = requirement.pcb_accessibility
    if isinstance(pcb_accessibility, AnalysisPending | AnalysisNotApplicable):
        checks.append(
            ElectricalCheck(
                id="test-access/pcb-accessibility",
                status=(
                    "NOT_CONFIGURED"
                    if isinstance(pcb_accessibility, AnalysisPending)
                    else "NOT_APPLICABLE"
                ),
                detail=pcb_accessibility.reason,
            )
        )
    elif request.config.kind is not ProjectKind.PCB:
        checks.append(
            ElectricalCheck(
                id="test-access/pcb-accessibility/source",
                status="FAIL",
                detail="PCB access evidence is required, but this project has no PCB project kind.",
            )
        )
    else:
        board_path = repo_path(request.root, request.config.project).with_suffix(".kicad_pcb")
        checks.extend(pcb_accessibility_checks(requirement, pcb_accessibility, board_path))

    if pcb_access_probe_request_set(requirement) is not None:
        if request.config.kind is not ProjectKind.PCB:
            checks.append(
                ElectricalCheck(
                    id="test-access/pcb-probe-envelope/source",
                    status="FAIL",
                    detail="Probe-envelope evidence requires an authoritative PCB project.",
                )
            )
        elif isinstance(request.pcb_evidence, PcbEvidenceObserved):
            checks.extend(pcb_probe_envelope_checks(requirement, request.pcb_evidence.snapshot))
        else:
            detail = (
                request.pcb_evidence.reason
                if isinstance(request.pcb_evidence, PcbEvidenceUnavailable)
                else "KiCad native PCB probing did not produce evidence."
            )
            checks.append(
                ElectricalCheck(
                    id="test-access/pcb-probe-envelope/native-probe",
                    status="NOT_RUN",
                    detail=detail,
                )
            )
    return tuple(checks)
