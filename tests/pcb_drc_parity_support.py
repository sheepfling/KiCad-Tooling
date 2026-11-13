"""Source-bound native DRC receipt helpers shared by CLI/MCP parity fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.native_project_validation_models import (
    CheckEvidence,
    ValidationSummary,
)


def install_source_bound_drc_receipt(root: Path, summary_path: Path) -> None:
    """Bind synthetic all-severity DRC output and command to a native summary."""
    summary = read_model(summary_path, ValidationSummary)
    board = root / "projects/controller/kicad/controller.kicad_pcb"
    drc_path = summary_path.parent / "drc.json"
    command_path = summary_path.parent / "drc.command.json"
    drc_path.write_text(
        json.dumps(
            {
                "$schema": "https://schemas.kicad.org/drc.v1.json",
                "kicad_version": "10.0.5",
                "source": str(board),
                "coordinate_units": "mm",
                "included_severities": ["error", "warning", "exclusion"],
                "ignored_checks": [],
                "violations": [],
            }
        ),
        encoding="utf-8",
    )
    write_model(
        command_path,
        CommandEvidence(
            argv=(
                "kicad-cli",
                "pcb",
                "drc",
                "--format",
                "json",
                "--severity-all",
                "--output",
                str(drc_path),
                str(board),
            ),
            started_utc="synthetic parity fixture",
            returncode=0,
        ),
    )
    write_model(
        summary_path,
        summary.model_copy(
            update={
                "checks": {
                    **summary.checks,
                    "drc": CheckEvidence(status="PASS", returncode=0),
                },
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "drc.json": digest(drc_path),
                    "drc.command.json": digest(command_path),
                },
            }
        ),
    )
