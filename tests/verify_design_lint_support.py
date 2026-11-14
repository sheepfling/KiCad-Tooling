"""Synthetic native evidence for verification design-lint gate tests."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.check_all import check_all
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CheckAllSummary,
    CheckEvidence,
    CommandEvidence,
    ValidationSummary,
)
from kicad_tooling.hwrepo.native_project_check_models import NativeProjectCheckRequest
from kicad_tooling.hwrepo.native_project_validation_models import NativeProjectValidationRequest
from kicad_tooling.validate import hashes
from kicad_tooling.verify import verify
from tests.verify_support import create_reference_project, native_summary, runner_environment


def synthetic_connector_native(
    root: Path, output: Path, cli: str, projects: Sequence[str]
) -> CheckAllSummary:
    """Write exact synthetic split-return evidence for the generic connectors."""
    _ = cli, projects
    project_output = output / "controller"
    project_output.mkdir(parents=True)
    netlist = project_output / "netlist.xml"
    netlist.write_text(
        '<export><components><comp ref="J1"><value>Synthetic port</value>'
        '<libsource lib="Synthetic" part="Port"/></comp><comp ref="J2">'
        '<value>Synthetic port</value><libsource lib="Synthetic" part="Port"/>'
        '</comp></components><libparts><libpart lib="Synthetic" part="Port"><pins>'
        '<pin num="1" name="PWR" type="passive"/>'
        '<pin num="7" name="GND" type="passive"/></pins></libpart></libparts><nets>'
        '<net name="GND1"><node ref="J1" pin="7"/></net>'
        '<net name="GND2"><node ref="J2" pin="7"/></net>'
        '<net name="+5V"><node ref="J1" pin="1"/></net>'
        "</nets></export>",
        encoding="utf-8",
    )
    evidence = CommandEvidence(
        argv=("synthetic-kicad-cli",),
        started_utc=datetime.now(UTC).isoformat(),
        returncode=0,
    )
    write_model(project_output / "netlist.command.json", evidence)
    config = load_config(root, "examples/projects/controller/project.json")
    project_file = root / config.project
    board_file = project_file.with_suffix(".kicad_pcb")
    drc_file = project_output / "drc.json"
    drc_file.write_text(
        json.dumps(
            {
                "$schema": "https://schemas.kicad.org/drc.v1.json",
                "coordinate_units": "mm",
                "kicad_version": config.kicad_version,
                "included_severities": ["error", "warning", "exclusion"],
                "ignored_checks": [],
                "source": board_file.name,
                "violations": [],
                "unconnected_items": [],
                "schematic_parity": [],
            }
        ),
        encoding="utf-8",
    )
    drc_command = CommandEvidence(
        argv=(
            "synthetic-kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--output",
            str(drc_file),
            str(board_file),
        ),
        started_utc=datetime.now(UTC).isoformat(),
        returncode=0,
    )
    write_model(project_output / "drc.command.json", drc_command)
    current = hashes(root, config.source_roots)
    write_model(
        project_output / "summary.json",
        ValidationSummary(
            timestamp_utc=datetime.now(UTC).isoformat(),
            checked_commit="LOCAL_UNBOUND",
            project_id="controller",
            project_kind=config.kind,
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes=current),
                "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
                "toolchain": CheckEvidence(
                    status="PASS",
                    observed_version=config.kicad_version,
                    image=config.image,
                ),
                "drc": CheckEvidence(status="PASS", returncode=0),
                "netlist": CheckEvidence(status="PASS", returncode=0),
            },
            status="PASS",
            artifacts_sha256={
                "netlist.xml": digest(netlist),
                "netlist.command.json": digest(project_output / "netlist.command.json"),
                "drc.json": digest(drc_file),
                "drc.command.json": digest(project_output / "drc.command.json"),
            },
        ),
    )
    write_model(output / "summary.json", native_summary())
    return native_summary()


def synthetic_connector_validation(
    root: Path, request: NativeProjectValidationRequest
) -> ValidationSummary:
    """Provide the synthetic native summary through the validation adapter."""
    synthetic_connector_native(root, request.output.parent, request.cli, ["controller"])
    return read_model(request.output / "summary.json", ValidationSummary)


def verify_with_synthetic_connector_evidence(root: Path):
    def run_native(_root: Path, request: NativeProjectCheckRequest) -> CheckAllSummary:
        return synthetic_connector_native(
            _root,
            request.output,
            request.cli,
            request.project_ids or (),
        )

    with (
        runner_environment("10.0.0"),
        patch(
            "kicad_tooling.hwrepo.project_verification.run_native_project_check",
            side_effect=run_native,
        ),
    ):
        return verify(root, "controller", depth="native", runner="local")


def verify_with_empty_contract_native_failure(root: Path):
    """Keep split-return lint visible when the independent net contract is empty."""

    def native_with_contract_blocker(
        project_root: Path, request: NativeProjectValidationRequest
    ) -> ValidationSummary:
        summary = synthetic_connector_validation(project_root, request)
        failed = summary.model_copy(
            update={
                "checks": {
                    **summary.checks,
                    "netlist": CheckEvidence(
                        status="FAIL",
                        returncode=0,
                        error="Independent connectivity contract is empty",
                    ),
                },
                "status": "FAIL",
            }
        )
        write_model(request.output / "summary.json", failed)
        return failed

    with (
        runner_environment("10.0.0"),
        patch(
            "kicad_tooling.hwrepo.native_project_check.validate_project",
            side_effect=native_with_contract_blocker,
        ),
    ):
        return verify(root, "controller", depth="native", runner="local")


def check_ci_with_synthetic_connector_evidence(root: Path, output_name: str):
    with patch(
        "kicad_tooling.hwrepo.native_project_check.validate_project",
        side_effect=synthetic_connector_validation,
    ):
        return check_all(
            root,
            root / "build" / output_name,
            "synthetic-kicad-cli",
            ["controller"],
        )


__all__ = [
    "check_ci_with_synthetic_connector_evidence",
    "create_reference_project",
    "synthetic_connector_native",
    "verify_with_synthetic_connector_evidence",
]
