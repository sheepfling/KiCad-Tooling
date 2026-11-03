"""Source-bound netlist admission for electrical analysis."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.electrical_netlist_evidence import (
    NetlistEvidenceNotRequested,
    NetlistEvidenceObserved,
    NetlistEvidenceUnavailable,
    admit_netlist_evidence,
)
from kicad_tooling.hwrepo.models import ContractCoachReport, NetlistContract

pytestmark = pytest.mark.architecture

PROJECT_ID = "controller"
SOURCE_HASHES = {"projects/controller/controller.kicad_sch": "a" * 64}


def _ready_report(
    *,
    project_id: str = PROJECT_ID,
    source_hashes: dict[str, str] | None = None,
    observed: NetlistContract | None = None,
    netlist_sha256: str | None = "b" * 64,
    include_observation: bool = True,
) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        source_hashes=SOURCE_HASHES if source_hashes is None else source_hashes,
        netlist_sha256=netlist_sha256,
        observed=(
            (NetlistContract(components={}, nets={}) if observed is None else observed)
            if include_observation
            else None
        ),
    )


def test_admitted_observation_keeps_its_producer_report_and_source_binding() -> None:
    report = _ready_report()

    evidence = admit_netlist_evidence(report, PROJECT_ID, SOURCE_HASHES)

    assert isinstance(evidence, NetlistEvidenceObserved)
    assert evidence.report is report
    assert evidence.observed is report.observed
    assert dict(evidence.expected_source_sha256) == SOURCE_HASHES


def test_native_summary_failure_does_not_promote_or_discard_netlist_observation() -> None:
    report = _ready_report().model_copy(update={"native_status": "FAIL"})

    evidence = admit_netlist_evidence(report, PROJECT_ID, SOURCE_HASHES)

    assert isinstance(evidence, NetlistEvidenceObserved)
    assert evidence.report.native_status == "FAIL"
    assert evidence.report.electrical_coverage is False
    assert evidence.report.build_authorized is False


def test_requested_but_blocked_netlist_is_distinct_from_not_requested() -> None:
    report = ContractCoachReport(
        status="BLOCKED",
        project_id=PROJECT_ID,
        issues=("Native export failed",),
    )

    evidence = admit_netlist_evidence(report, PROJECT_ID, SOURCE_HASHES)
    not_requested = NetlistEvidenceNotRequested(project_id=PROJECT_ID)

    assert isinstance(evidence, NetlistEvidenceUnavailable)
    assert evidence.state == "UNAVAILABLE"
    assert evidence.report is report
    assert not_requested.state == "NOT_REQUESTED"


@pytest.mark.parametrize(
    ("report", "expected_reason"),
    (
        (
            _ready_report(source_hashes={"projects/controller/controller.kicad_sch": "c" * 64}),
            "current declared",
        ),
        (_ready_report(netlist_sha256=None), "observation and digest"),
        (_ready_report(include_observation=False), "observation and digest"),
    ),
)
def test_incomplete_or_stale_ready_report_is_unavailable(
    report: ContractCoachReport, expected_reason: str
) -> None:
    evidence = admit_netlist_evidence(report, PROJECT_ID, SOURCE_HASHES)

    assert isinstance(evidence, NetlistEvidenceUnavailable)
    assert expected_reason in evidence.reason


def test_cross_project_report_is_rejected() -> None:
    report = _ready_report(project_id="another-project")

    with pytest.raises(ValueError, match="another project"):
        admit_netlist_evidence(report, PROJECT_ID, SOURCE_HASHES)


def test_unavailable_state_cannot_hide_current_source_bound_evidence() -> None:
    with pytest.raises(ValidationError, match="cannot be marked unavailable"):
        NetlistEvidenceUnavailable(
            project_id=PROJECT_ID,
            expected_source_sha256=SOURCE_HASHES,
            report=_ready_report(),
            reason="Incorrectly classified",
        )


def test_new_evidence_owner_is_small_and_runner_uses_it() -> None:
    repository_root = Path(__file__).parents[1]
    owner = repository_root / "kicad_tooling/hwrepo/electrical_netlist_evidence.py"
    runner = (repository_root / "kicad_tooling/hwrepo/electrical_runner.py").read_text(
        encoding="utf-8"
    )

    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert "admit_netlist_evidence" in runner
    assert "NetlistEvidenceNotRequested" in runner
    assert "netlist_report.observed" not in runner
