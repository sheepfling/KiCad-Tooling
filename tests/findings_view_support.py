"""Synthetic retained native evidence for findings-view integration tests."""

from __future__ import annotations

import json
from pathlib import Path

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    CommandEvidence,
    ProjectManifest,
    ValidationSummary,
)
from kicad_tooling.hwrepo.schematic_geometry_models import (
    SchematicGeometryCoverage,
    SchematicGeometrySourceBinding,
)
from kicad_tooling.hwrepo.schematic_geometry_source import schematic_root, schematic_scalar

FIXTURES = Path(__file__).parent / "fixtures/findings_view"


def select_schematic_geometry_toolchain(island: Path) -> None:
    manifest_path = island / "project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.5"}))


def add_native_review(root: Path, native: Path) -> None:
    directory = native.parent
    config = load_config(root, "examples/projects/controller/project.json")
    original = read_model(native, ValidationSummary)
    checks = dict(original.checks)
    artifacts = dict(original.artifacts_sha256)
    (directory / "schematic").mkdir()
    for kind, source, args, paths, status in (
        (
            "schematic_svg",
            ".kicad_sch",
            ("sch", "export", "svg"),
            ("schematic/controller.svg",),
            "PASS",
        ),
        ("pcb_svg", ".kicad_pcb", ("pcb", "export", "svg"), ("pcb.svg",), "PASS"),
        ("erc", ".kicad_sch", ("sch", "erc"), ("erc.json",), "FAIL"),
        ("drc", ".kicad_pcb", ("pcb", "drc"), ("drc.json",), "FAIL"),
    ):
        for name in paths:
            target = directory / name
            if name.endswith(".svg"):
                target.write_bytes(
                    (
                        FIXTURES / Path(name).name.replace("controller.svg", "schematic.svg")
                    ).read_bytes()
                )
            else:
                payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
                payload["kicad_version"] = config.kicad_version
                expected = getattr(config.validation.expected_ignored_checks, kind)
                payload["ignored_checks"] = [{"key": key} for key in expected]
                target.write_text(json.dumps(payload), encoding="utf-8")
            artifacts[name] = digest(target)
        command_path = directory / f"{kind}.command.json"
        arguments = ("kicad-cli", *args)
        if kind in {"erc", "drc"}:
            arguments += ("--format", "json", "--severity-all", "--exit-code-violations")
            if kind == "drc":
                arguments += ("--schematic-parity", "--refill-zones")
        if kind == "pcb_svg":
            arguments += ("--layers", "F.Cu,F.SilkS,Edge.Cuts,Cmts.User")
        destination = directory / ("schematic" if kind == "schematic_svg" else paths[0])
        arguments += (
            "--output",
            str(destination),
            str(root / Path(config.project).with_suffix(source)),
        )
        write_model(
            command_path,
            CommandEvidence(
                argv=arguments,
                started_utc="2026-01-01T00:00:00Z",
                returncode=0 if status == "PASS" else 5,
            ),
        )
        artifacts[command_path.name] = digest(command_path)
        checks[kind] = CheckEvidence(
            status=status,
            returncode=0 if status == "PASS" else 5,
            findings=1 if kind == "erc" else 2 if kind == "drc" else None,
            files=paths if kind.endswith("svg") else (),
        )
    write_model(
        native, original.model_copy(update={"checks": checks, "artifacts_sha256": artifacts})
    )


def add_lint_snapshot(root: Path, native: Path, *, sheet_path: str | None = None) -> Path:
    config = load_config(root, "examples/projects/controller/project.json")
    manifest_path = root / "examples/projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    policy_path = manifest_path.parent / manifest.checks
    summary = read_model(native, ValidationSummary)
    sources = summary.checks["source_scope"].source_hashes
    schematic = str(Path(config.project).with_suffix(".kicad_sch"))
    if sheet_path is None:
        source_text, source_root = schematic_root((root / schematic).read_bytes())
        sheet_path = "/" + schematic_scalar(source_text, source_root, "uuid")
    netlist = summary.artifacts_sha256["netlist.xml"]
    binding = SchematicGeometrySourceBinding(
        source_path=schematic,
        source_sha256=sources[schematic],
        sheet_instance_path=sheet_path,
        sheet_path=("Child",) if sheet_path == "/reused-sheet" else (),
    )
    finding = DesignLintFinding(
        rule_id="schematic.unmarked_wire_crossing",
        fingerprint="1" * 64,
        subject="Crossing at 50,40 mm",
        message="Review the crossing.",
        mode="review",
        disposition="OPEN",
        evidence={
            "schematic": (schematic,),
            "schematic_sha256": (sources[schematic],),
            "sheet_instance_path": (sheet_path,),
            "crossing_mm": ("50.000000,40.000000",),
            "kicad_version": (config.kicad_version,),
        },
    )
    report = DesignLintReport(
        status="REVIEW",
        project_id="controller",
        native_summary=str(native),
        source_hashes=sources,
        netlist_sha256=netlist,
        project_manifest_sha256=digest(manifest_path),
        policy_path=policy_path.relative_to(root).as_posix(),
        policy_sha256=digest(policy_path),
        findings=(finding,),
        schematic_geometry=SchematicGeometryCoverage(
            status="COMPLETE",
            source_path=schematic,
            source_sha256=sources[schematic],
            source_tree_sha256=sources[schematic],
            source_bindings=(binding,),
            netlist_sha256=netlist,
            kicad_version=config.kicad_version,
            finding_count=1,
        ),
    )
    result = native.parent / "lint-review.json"
    write_model(result, report)
    return result
