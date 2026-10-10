"""Synthetic native evidence for verification design-lint gate tests."""

from __future__ import annotations

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
from kicad_tooling.validate import hashes
from kicad_tooling.verify import verify
from tests.verify_support import create_reference_project, native_summary, runner_environment


def synthetic_connector_native(
    root: Path, output: Path, cli: str, projects: list[str]
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
                "netlist": CheckEvidence(status="PASS", returncode=0),
            },
            status="PASS",
            artifacts_sha256={
                "netlist.xml": digest(netlist),
                "netlist.command.json": digest(project_output / "netlist.command.json"),
            },
        ),
    )
    write_model(output / "summary.json", native_summary())
    return native_summary()


def synthetic_connector_validation(
    root: Path, output: Path, cli: str, config_path: Path
) -> ValidationSummary:
    """Provide the synthetic native summary through the validation adapter."""
    _ = config_path
    synthetic_connector_native(root, output.parent, cli, ["controller"])
    return read_model(output / "summary.json", ValidationSummary)


def verify_with_synthetic_connector_evidence(root: Path):
    with (
        runner_environment("10.0.0"),
        patch("kicad_tooling.verify.check_all", side_effect=synthetic_connector_native),
    ):
        return verify(root, "controller", depth="native", runner="local")


def check_ci_with_synthetic_connector_evidence(root: Path, output_name: str):
    with patch("kicad_tooling.check_all.validate", side_effect=synthetic_connector_validation):
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
