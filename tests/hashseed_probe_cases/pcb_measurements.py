"""Synthetic mapped PCB measurement reports for hash-seed verification."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
    PcbConnectivitySnapshot,
)
from tests.test_pcb_protection_path import (
    coverage_report as protection_coverage,
)
from tests.test_pcb_protection_path import (
    mapping as protection_mapping,
)
from tests.test_pcb_protection_path import (
    snapshot as protection_snapshot,
)
from tests.test_pcb_track_width import (
    coverage as track_width_coverage,
)
from tests.test_pcb_track_width import (
    mapping as track_width_mapping,
)
from tests.test_pcb_track_width import (
    requirement as track_width_requirement,
)
from tests.test_pcb_track_width import (
    snapshot as track_width_snapshot,
)
from tests.test_pcb_track_width import (
    track as track_width_track,
)


def _digest(model: BaseModel) -> str:
    return hashlib.sha256(model.model_dump_json().encode("utf-8")).hexdigest()


def _board_snapshot(
    snapshot: PcbConnectivitySnapshot, source_description: str
) -> PcbConnectivitySnapshot:
    board_sha256 = hashlib.sha256(source_description.encode("utf-8")).hexdigest()
    return snapshot.model_copy(update={"board_sha256": board_sha256})


def _report_case(
    requirement: BaseModel,
    snapshot: PcbConnectivitySnapshot,
    result: DesignLintReport,
    *,
    netlist_sha256: str,
) -> dict[str, object]:
    return {
        "requirement_sha256": _digest(requirement),
        "board_sha256": snapshot.board_sha256,
        "snapshot_sha256": _digest(snapshot),
        "netlist_sha256": netlist_sha256,
        "report": result.model_dump(mode="json"),
    }


def protection_path_report(*, fault: bool) -> dict[str, object]:
    """Serialize a one-nanometer protection-entry fault and boundary control."""
    requirement = protection_mapping()
    entry_distance_nm = 100_001 if fault else 100_000
    evidence = _board_snapshot(
        protection_snapshot(entry_distance_nm=entry_distance_nm),
        f"synthetic-protection-path-entry-distance:{entry_distance_nm}nm",
    )
    observed = NetlistContract(components={}, nets={})
    netlist_sha256 = _digest(observed)
    coverage = protection_coverage(requirement, evidence).model_copy(
        update={"netlist_sha256": netlist_sha256}
    )
    native = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-protection-path",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )
    result = evaluate(
        "synthetic-protection-path",
        native,
        DesignLintPolicy(pcb_protection_path_map=requirement),
        pcb_protection_path_coverage=coverage,
    )
    return _report_case(requirement, evidence, result, netlist_sha256=netlist_sha256)


def track_width_report(*, fault: bool) -> dict[str, object]:
    """Serialize a one-micrometer track-width fault and boundary control."""
    requirement = track_width_mapping(track_width_requirement(minimum_um=251))
    measured_width_nm = 250_000 if fault else 251_000
    evidence = _board_snapshot(
        track_width_snapshot(track_width_track("001", "VDD", measured_width_nm)),
        f"synthetic-track-width-vdd:{measured_width_nm}nm",
    )
    observed = NetlistContract(components={}, nets={})
    netlist_sha256 = _digest(observed)
    coverage = track_width_coverage(requirement, evidence).model_copy(
        update={"netlist_sha256": netlist_sha256}
    )
    native = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-track-width",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )
    result = evaluate(
        "synthetic-track-width",
        native,
        DesignLintPolicy(pcb_track_width_map=requirement),
        pcb_track_width_coverage=coverage,
    )
    return _report_case(requirement, evidence, result, netlist_sha256=netlist_sha256)


def report_cases() -> dict[str, object]:
    return {
        "pcb_protection_path_fault": protection_path_report(fault=True),
        "pcb_protection_path_control": protection_path_report(fault=False),
        "pcb_track_width_fault": track_width_report(fault=True),
        "pcb_track_width_control": track_width_report(fault=False),
    }
