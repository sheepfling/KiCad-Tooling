"""Identity of the saved native summary and its netlist export evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ..validate import read_netlist
from .command_evidence_models import CommandEvidence
from .contracts import read_model
from .evidence import digest, evidence_path
from .models import (
    EvidenceFile,
    NetlistContract,
    ValidationSummary,
)
from .native_summary_binding import validate_native_summary_binding
from .project_models import ProjectConfig


@dataclass(frozen=True, slots=True)
class NativeNetlistEvidenceIdentity:
    """Exact bytes used to accept one native netlist export."""

    summary_sha256: str
    netlist_sha256: str
    command_sha256: str


def capture_native_netlist_evidence(native_summary: Path) -> NativeNetlistEvidenceIdentity:
    """Hash the summary and the two native export artifacts it references."""
    summary = native_summary / "summary.json" if native_summary.is_dir() else native_summary
    return NativeNetlistEvidenceIdentity(
        summary_sha256=digest(summary),
        netlist_sha256=digest(summary.parent / "netlist.xml"),
        command_sha256=digest(summary.parent / "netlist.command.json"),
    )


def native_netlist_evidence_matches(
    native_summary: Path, expected: NativeNetlistEvidenceIdentity | None
) -> bool:
    """Treat missing or changed native files as nonmatching evidence."""
    if expected is None:
        return False
    try:
        return capture_native_netlist_evidence(native_summary) == expected
    except OSError:
        return False


def validate_native_netlist_export(
    summary_path: Path, summary: ValidationSummary, identity: NativeNetlistEvidenceIdentity
) -> None:
    """Validate the native export check and the exact retained command bytes."""
    check = summary.checks.get("netlist")
    if check is None or check.status == "NOT_RUN" or check.returncode != 0:
        raise ValueError("Native netlist export was not executed successfully")
    if summary.artifacts_sha256.get("netlist.xml") != identity.netlist_sha256:
        raise ValueError("Native netlist bytes differ from the summary artifact hash")
    if summary.artifacts_sha256.get("netlist.command.json") != identity.command_sha256:
        raise ValueError("Native netlist command evidence differs from the summary artifact hash")
    command = read_model(summary_path.parent / "netlist.command.json", CommandEvidence)
    if command.returncode != 0 or command.error is not None:
        raise ValueError("Native netlist command evidence records a failed export")


def read_bound_native_netlist(
    root: Path,
    reference: EvidenceFile,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[NetlistContract, NativeNetlistEvidenceIdentity]:
    """Read a netlist only when its summary, command and source identity agree."""
    summary_path = evidence_path(root, reference)
    identity = capture_native_netlist_evidence(summary_path)
    if identity.summary_sha256 != reference.sha256:
        raise ValueError("Native summary changed while binding netlist evidence")
    summary = read_model(summary_path, ValidationSummary)
    validate_native_summary_binding(summary, config, source_hashes)
    validate_native_netlist_export(summary_path, summary, identity)
    observed = read_netlist(summary_path.parent / "netlist.xml")
    if not observed.components:
        raise ValueError("Native netlist contains no component records")
    if not native_netlist_evidence_matches(summary_path, identity):
        raise ValueError("Native netlist evidence changed while reading the validation summary")
    return observed, identity
