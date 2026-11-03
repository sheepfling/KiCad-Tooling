"""Render typed diagnostic reports as concise or full review text."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .diagnostics_models import DiagnosticFinding, DiagnosticReport


def format_text(result: DiagnosticReport, detail: Literal["brief", "full"] = "brief") -> str:
    """Show a short repair queue or every finding without losing its source location."""
    blocking = sum(row.severity == "BLOCKING" for row in result.findings)
    review = len(result.findings) - blocking
    lines = [
        f"{result.status}: {result.scope} diagnostics for {result.project_id}",
        f"{blocking} blocking finding(s); {review} review task(s).",
    ]
    if detail == "full":
        number = 0
        for severity in ("BLOCKING", "REVIEW"):
            for row in result.findings:
                if row.severity != severity:
                    continue
                number += 1
                lines.extend(
                    (
                        f"{number}. [{row.severity}] {row.code} at {row.location}",
                        f"   Observed: {row.observed}",
                        f"   Fix: {row.action}",
                        f"   Guide: {row.guide}",
                    )
                )
    else:
        groups: dict[tuple[str, str, str, str], list[DiagnosticFinding]] = {}
        for severity in ("BLOCKING", "REVIEW"):
            for row in result.findings:
                if row.severity == severity:
                    groups.setdefault((row.severity, row.code, row.action, row.guide), []).append(
                        row
                    )
        for number, ((severity, code, action, guide), rows) in enumerate(groups.items(), 1):
            lines.append(f"{number}. [{severity}] {code} ({len(rows)} finding(s))")
            for row in rows[:3]:
                lines.append(f"   At {row.location}: {row.observed}")
            if len(rows) > 3:
                lines.append(f"   ... and {len(rows) - 3} more in diagnosis.json")
            lines.extend((f"   Fix: {action}", f"   Guide: {guide}"))
    if not result.findings:
        lines.append(
            "No diagnosed problems in this scope. Continue with the selected verification command."
        )
    lines.append(f"Next command: {result.next_command}")
    if result.follow_up_command is not None:
        lines.append(
            "After the fresh run, replace FRESH_NATIVE_DIR with that receipt's native/ "
            "directory and recheck the BOM:"
        )
        lines.append(f"Follow-up command: {result.follow_up_command}")
    lines.append("Diagnostic success does not approve the electrical design or a release.")
    if any(
        row.code.startswith("NATIVE_")
        or row.code.startswith("BOM_")
        or row.code == "STALE_NATIVE_REPORT"
        for row in result.findings
    ):
        lines.append(
            "After changing KiCad source or check settings, use kicad_tooling.verify --depth native "
            "for a fresh report and replace any --native-report/--bom paths above."
        )
    if result.run_directory is not None:
        lines.append(f"Run log: {Path(result.run_directory) / 'events.log'}")
        lines.append(f"Full findings: {Path(result.run_directory) / 'diagnosis.json'}")
    return "\n".join(lines)
