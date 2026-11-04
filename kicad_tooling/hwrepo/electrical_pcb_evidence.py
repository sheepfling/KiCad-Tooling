"""Admission states for native PCB connectivity used by electrical analysis."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

from .command_evidence_models import CommandEvidence
from .contracts import model_json_bytes
from .model_primitives import Digest, Identifier, NonEmptyText, StrictModel
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_return_path_capture import NativePcbConnectivityCapture
from .pcb_test_access_models import PcbAccessProbeRequestSet


class PcbEvidenceNotRequested(StrictModel):
    """No configured electrical requirement requested native PCB evidence."""

    state: Literal["NOT_REQUESTED"] = "NOT_REQUESTED"
    project_id: Identifier


class PcbEvidenceUnavailable(StrictModel):
    """A PCB evidence request did not produce an admissible native snapshot."""

    state: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    project_id: Identifier
    reason: NonEmptyText
    command: CommandEvidence | None = None
    access_probe_requests_sha256: Digest | None = None


class PcbEvidenceObserved(StrictModel):
    """A native snapshot and the command that produced it, scoped to one project."""

    state: Literal["OBSERVED"] = "OBSERVED"
    project_id: Identifier
    command: CommandEvidence
    snapshot: PcbConnectivitySnapshot
    access_probe_requests_sha256: Digest | None

    @model_validator(mode="after")
    def command_and_probe_request_match(self) -> PcbEvidenceObserved:
        if self.command.returncode != 0 or self.command.error is not None:
            raise ValueError("Observed PCB evidence needs a successful native command")
        if self.snapshot.access_probe_requests_sha256 != self.access_probe_requests_sha256:
            raise ValueError("PCB evidence does not match the requested access-probe input")
        return self


ElectricalPcbEvidence: TypeAlias = Annotated[
    PcbEvidenceNotRequested | PcbEvidenceUnavailable | PcbEvidenceObserved,
    Field(discriminator="state"),
]


def admit_pcb_connectivity_capture(
    project_id: str,
    capture: NativePcbConnectivityCapture | None,
    *,
    reason: str | None = None,
    access_probe_requests: PcbAccessProbeRequestSet | None = None,
) -> PcbEvidenceUnavailable | PcbEvidenceObserved:
    """Retain failed capture context or admit the returned native observation."""
    command = None if capture is None else capture.command
    snapshot = None if capture is None else capture.snapshot
    request_digest = (
        hashlib.sha256(model_json_bytes(access_probe_requests)).hexdigest()
        if access_probe_requests is not None
        else None
    )
    if (
        command is not None
        and snapshot is not None
        and command.returncode == 0
        and command.error is None
    ):
        return PcbEvidenceObserved(
            project_id=project_id,
            command=command,
            snapshot=snapshot,
            access_probe_requests_sha256=request_digest,
        )
    return PcbEvidenceUnavailable(
        project_id=project_id,
        command=command,
        reason=reason or "KiCad native PCB probing did not produce evidence.",
        access_probe_requests_sha256=request_digest,
    )


def admit_pcb_evidence(
    project_id: str,
    command: CommandEvidence | None,
    snapshot: PcbConnectivitySnapshot | None,
    *,
    reason: str | None = None,
    access_probe_requests: PcbAccessProbeRequestSet | None = None,
) -> PcbEvidenceUnavailable | PcbEvidenceObserved:
    """Compatibility adapter for callers that still pass command and snapshot separately."""
    capture = (
        None
        if command is None
        else NativePcbConnectivityCapture(command=command, snapshot=snapshot)
    )
    return admit_pcb_connectivity_capture(
        project_id,
        capture,
        reason=reason,
        access_probe_requests=access_probe_requests,
    )
