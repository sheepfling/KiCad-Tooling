"""Guard typed PCB evidence ownership and electrical evaluation routing."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.electrical_pcb_evidence import (
    PcbEvidenceNotRequested,
    PcbEvidenceObserved,
    PcbEvidenceUnavailable,
    admit_pcb_evidence,
)
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_test_access_models import (
    PcbAccessProbeRequest,
    PcbAccessProbeRequestSet,
)

pytestmark = pytest.mark.architecture

REPOSITORY_ROOT = Path(__file__).parents[1]
PACKAGE = REPOSITORY_ROOT / "kicad_tooling/hwrepo"


def _command(*, returncode: int = 0) -> CommandEvidence:
    return CommandEvidence(
        argv=("kicad-native-probe",),
        started_utc="2026-10-31T00:00:00Z",
        returncode=returncode,
    )


def _snapshot(*, access_request_sha256: str | None = None) -> PcbConnectivitySnapshot:
    return PcbConnectivitySnapshot(
        schema_version="2",
        board_sha256="a" * 64,
        kicad_version="10.0.0",
        image="kicad@sha256:" + "b" * 64,
        probe_sha256="c" * 64,
        zones_refilled=True,
        pads=(),
        net_ties=(),
        zones=(),
        access_probe_requests_sha256=access_request_sha256,
    )


def test_pcb_capture_admission_preserves_requested_and_observed_states() -> None:
    not_requested = PcbEvidenceNotRequested(project_id="controller")
    observed = admit_pcb_evidence("controller", _command(), _snapshot())

    assert not_requested.state == "NOT_REQUESTED"
    assert isinstance(observed, PcbEvidenceObserved)
    assert observed.project_id == "controller"
    assert observed.command.returncode == 0
    assert observed.access_probe_requests_sha256 is None


def test_failed_pcb_capture_retains_command_and_reason() -> None:
    command = _command(returncode=1)

    unavailable = admit_pcb_evidence(
        "controller",
        command,
        None,
        reason="Native probe exited with status 1",
        access_probe_requests=PcbAccessProbeRequestSet(
            requests=(PcbAccessProbeRequest(endpoint="TP1.1", net="3V3", side="front"),)
        ),
    )

    assert isinstance(unavailable, PcbEvidenceUnavailable)
    assert unavailable.command == command
    assert unavailable.reason == "Native probe exited with status 1"
    assert unavailable.access_probe_requests_sha256 is not None


def test_observed_probe_evidence_must_match_the_requested_access_surfaces() -> None:
    requests = PcbAccessProbeRequestSet(
        requests=(PcbAccessProbeRequest(endpoint="TP1.1", net="3V3", side="front"),)
    )

    with pytest.raises(ValidationError, match="does not match the requested access-probe input"):
        admit_pcb_evidence("controller", _command(), _snapshot(), access_probe_requests=requests)


def test_runner_delegates_pcb_predicates_to_typed_evaluation_owners() -> None:
    runner = (PACKAGE / "electrical_runner.py").read_text(encoding="utf-8")
    evaluation = (PACKAGE / "electrical_pcb_evaluation.py").read_text(encoding="utf-8")
    evidence = (PACKAGE / "electrical_pcb_evidence.py").read_text(encoding="utf-8")

    assert len(evaluation.splitlines()) < 500
    assert len(evidence.splitlines()) < 500
    assert "ElectricalPcbReturnEvaluationRequest" in runner
    assert "ElectricalTestAccessEvaluationRequest" in runner
    for predicate in (
        "pcb_return_path_checks",
        "pcb_accessibility_checks",
        "pcb_probe_envelope_checks",
        "evaluate_test_access_checks",
    ):
        assert predicate not in runner
    assert "ElectricalPcbEvidence" in evaluation
    assert "ElectricalNetlistEvidence" in evaluation
    assert "electrical_runner" not in evaluation
    assert "PcbEvidenceNotRequested | PcbEvidenceUnavailable | PcbEvidenceObserved" in evidence
