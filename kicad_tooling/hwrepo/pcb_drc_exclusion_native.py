"""Compare saved PCB DRC exclusions with exact native DRC evidence."""

from __future__ import annotations

import hashlib
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .contracts import read_kicad_drc_findings, read_model
from .native_drc_findings import NativeDrcFinding, NativeDrcReport
from .native_project_validation_models import ValidationSummary
from .pcb_drc_project_settings import PcbDrcExclusion

PcbDrcExclusionMatchStatus = Literal["MATCHED", "UNMATCHED", "AMBIGUOUS", "UNAVAILABLE"]


@dataclass(frozen=True, slots=True)
class PcbDrcExclusionNativeMatch:
    """One saved marker's comparison with a source-bound native DRC report."""

    marker: str
    status: PcbDrcExclusionMatchStatus
    report_sha256: str | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _marker_identity(marker: str) -> tuple[str, tuple[str, ...]] | None:
    """Read the KiCad 10 marker's rule key and participating item UUIDs."""
    fields = marker.split("|")
    if len(fields) < 5 or not fields[0]:
        return None
    try:
        int(fields[1])
        int(fields[2])
        item_ids = tuple(str(uuid.UUID(value)) for value in fields[3:])
    except (ValueError, AttributeError):
        return None
    if len(item_ids) < 2:
        return None
    return fields[0], tuple(sorted(item_ids))


def _excluded_violation_identity(
    finding: NativeDrcFinding,
) -> tuple[str, str, tuple[str, ...]] | None:
    if not finding.excluded:
        return None
    item_ids: list[str] = []
    for item in finding.items:
        if item.uuid is None:
            return None
        try:
            item_ids.append(str(uuid.UUID(item.uuid)))
        except ValueError:
            return None
    if len(item_ids) < 2:
        return None
    return finding.rule, finding.comment, tuple(sorted(item_ids))


def match_pcb_drc_exclusions(
    exclusions: tuple[PcbDrcExclusion, ...],
    report: NativeDrcReport,
    *,
    expected_kicad_version: str,
    report_sha256: str,
) -> tuple[PcbDrcExclusionNativeMatch, ...]:
    """Match settings markers against excluded violations in a native report.

    Matching uses the DRC rule key, exact saved comment, and participating item
    UUIDs. When distinct markers share this identity, report an ambiguous group
    rather than assigning a match to an arbitrary marker.
    """
    if report.version != expected_kicad_version:
        raise ValueError("Native PCB DRC report version differs from the configured KiCad version")
    if report.schema != "https://schemas.kicad.org/drc.v1.json":
        raise ValueError("Native PCB DRC report schema is not supported")
    if "exclusion" not in report.included_severities:
        raise ValueError("Native PCB DRC report does not include exclusion findings")

    native_counts: Counter[tuple[str, str, tuple[str, ...]]] = Counter()
    has_uncomparable_exclusion = False
    for finding in report.findings:
        if not finding.excluded:
            continue
        identity = _excluded_violation_identity(finding)
        if identity is None:
            has_uncomparable_exclusion = True
        else:
            native_counts[identity] += 1

    grouped: dict[tuple[str, str, tuple[str, ...]], list[PcbDrcExclusion]] = defaultdict(list)
    unsupported: set[str] = set()
    for exclusion in exclusions:
        identity = _marker_identity(exclusion.marker)
        if identity is None:
            unsupported.add(exclusion.marker)
        else:
            grouped[(identity[0], exclusion.comment, identity[1])].append(exclusion)

    statuses: dict[str, PcbDrcExclusionNativeMatch] = {}
    for marker in unsupported:
        statuses[marker] = PcbDrcExclusionNativeMatch(
            marker=marker, status="UNAVAILABLE", report_sha256=report_sha256
        )
    for (rule_key, comment, item_ids), members in grouped.items():
        current = native_counts[(rule_key, comment, item_ids)]
        if len(members) > 1 and 0 < current < len(members):
            status: PcbDrcExclusionMatchStatus = "AMBIGUOUS"
        elif current == 0 and has_uncomparable_exclusion:
            status = "UNAVAILABLE"
        else:
            status = "MATCHED" if current >= len(members) else "UNMATCHED"
        for exclusion in members:
            statuses[exclusion.marker] = PcbDrcExclusionNativeMatch(
                marker=exclusion.marker,
                status=status,
                report_sha256=report_sha256,
            )
    return tuple(statuses[item.marker] for item in exclusions)


def source_bound_pcb_drc_exclusion_matches(
    native_summary: Path,
    exclusions: tuple[PcbDrcExclusion, ...],
    *,
    expected_kicad_version: str,
) -> tuple[PcbDrcExclusionNativeMatch, ...]:
    """Read only the DRC report whose exact digest is recorded by its summary."""
    summary_path = native_summary / "summary.json" if native_summary.is_dir() else native_summary
    summary = read_model(summary_path, ValidationSummary)
    drc_check = summary.checks.get("drc")
    report_path = summary_path.parent / "drc.json"
    expected_hash = summary.artifacts_sha256.get("drc.json")
    if (
        drc_check is None
        or drc_check.returncode not in {0, 5}
        or expected_hash is None
        or not report_path.is_file()
    ):
        return tuple(
            PcbDrcExclusionNativeMatch(marker=item.marker, status="UNAVAILABLE")
            for item in exclusions
        )
    report_bytes = report_path.read_bytes()
    if _sha256(report_bytes) != expected_hash:
        raise ValueError("Native PCB DRC report differs from its validation-summary artifact hash")
    report = read_kicad_drc_findings(report_path)
    return match_pcb_drc_exclusions(
        exclusions,
        report,
        expected_kicad_version=expected_kicad_version,
        report_sha256=expected_hash,
    )


def native_pcb_drc_report_matches(native_summary: Path, expected_sha256: str) -> bool:
    """Confirm the retained DRC report did not change after candidate creation."""
    summary_path = native_summary / "summary.json" if native_summary.is_dir() else native_summary
    report_path = summary_path.parent / "drc.json"
    try:
        return _sha256(report_path.read_bytes()) == expected_sha256
    except OSError:
        return False
