"""Shared source evidence and report construction for PCB geometry checks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

from .models import CommandEvidence, Digest
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot

PcbRuleMode = Literal["review", "block", "off"]
MapModel = TypeVar("MapModel", bound=BaseModel)
ReportModel = TypeVar("ReportModel", bound=BaseModel)


class CoverageEntry(Protocol):
    @property
    def status(self) -> str: ...


@dataclass(frozen=True)
class PcbGeometrySourceEvidence:
    """Native and source-bound inputs shared by deterministic PCB coverage checks."""

    board_path: str
    board_sha256: str
    snapshot_relative_path: str
    snapshot_path: Path
    snapshot_sha256: str
    probe_sha256: str
    snapshot: PcbConnectivitySnapshot
    command: CommandEvidence
    command_path: Path
    command_sha256: str


def map_sha256(requirements: BaseModel) -> str:
    """Hash the normalized project-authored requirements for report binding."""
    return hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()


def geometry_coverage_report(
    report_type: type[ReportModel],
    requirements: BaseModel,
    mode: PcbRuleMode,
    entries: tuple[CoverageEntry, ...],
    evidence: PcbGeometrySourceEvidence,
    netlist_sha256: Digest,
) -> ReportModel:
    """Construct a source-bound report after the native evidence gate passes."""
    return report_type.model_validate(
        {
            "status": "COMPLETE"
            if all(item.status == "COMPLETE" for item in entries)
            else "INCOMPLETE",
            "mode": mode,
            "map_sha256": map_sha256(requirements),
            "board_path": evidence.board_path,
            "board_sha256": evidence.board_sha256,
            "snapshot_path": evidence.snapshot_relative_path,
            "snapshot_sha256": evidence.snapshot_sha256,
            "probe_sha256": evidence.probe_sha256,
            "kicad_version": evidence.snapshot.kicad_version,
            "image": evidence.snapshot.image,
            "netlist_sha256": netlist_sha256,
            "entries": entries,
        }
    )
