"""Generate manufacturer-facing files using explicit project export settings."""
from __future__ import annotations

import csv
import zipfile
from pathlib import Path

from ..validate import execute
from .contracts import (
    kicad_variant_names,
    read_model,
    repo_path,
    require_kicad_json_object,
    write_model,
)
from .discovery import load_config, load_registry
from .evidence import digest, evidence_path, source_state, verify_source
from .generation import csv_cell
from .models import (
    EvidenceFile,
    PartsCatalog,
    ProjectManifest,
    ReleaseExportReport,
    ReleaseExportSettings,
    SourceState,
)


def command_arguments(settings: ReleaseExportSettings, base: Path, output: Path,
                      assembly_variant: str | None = None) -> dict[str, tuple[str, ...]]:
    """One exporter table to extend; all destinations are controlled by this tool."""
    origin = ("--use-drill-file-origin",) if settings.coordinate_origin == "plot" else ()
    variant = ("--variant", assembly_variant) if assembly_variant else ()
    board = str(base.with_suffix(".kicad_pcb"))
    schematic = str(base.with_suffix(".kicad_sch"))
    commands = {
        "gerbers": ("pcb", "export", "gerbers", "--layers", ",".join(settings.gerber_layers),
                    "--no-protel-ext", "--check-zones", *origin, *variant,
                    "--output", str(output / "fabrication"), board),
        "drill": ("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
                  "--drill-origin", settings.coordinate_origin, "--excellon-units", "mm",
                  "--output", str(output / "fabrication"), board),
        "position": ("pcb", "export", "pos", "--format", "csv", "--units", settings.position_units,
                     "--exclude-dnp", *origin, *variant,
                     "--output", str(output / "assembly/positions.csv"), board),
        "bom": ("sch", "export", "bom", "--fields", "Reference,Value,Footprint,PART_ID,DNP",
                "--labels", "Reference,Value,Footprint,PartID,DNP", "--exclude-dnp", *variant,
                "--output", str(output / "assembly/bom.csv"), schematic),
        "schematic_pdf": ("sch", "export", "pdf", *variant,
                          "--output", str(output / "review/schematic.pdf"), schematic),
        "pcb_pdf": ("pcb", "export", "pdf", "--layers", ",".join(settings.gerber_layers),
                    "--mode-multipage", *variant,
                    "--output", str(output / "review/pcb.pdf"), board),
        "board_stats": ("pcb", "export", "stats", "--format", "json",
                        "--output", str(output / "review/board-stats.json"), board),
    }
    for format_name in settings.supplier_formats:
        if format_name == "odb":
            commands["odb"] = ("pcb", "export", "odb", "--check-zones", "--compression", "zip",
                               *variant, "--output", str(output / "fabrication/board.odb.zip"), board)
        elif format_name == "ipc2581":
            commands["ipc2581"] = ("pcb", "export", "ipc2581", "--compress",
                                   "--bom-col-int-id", "PART_ID", *variant,
                                   "--output", str(output / "fabrication/board.ipc2581.zip"), board)
        else:
            commands["ipcd356"] = ("pcb", "export", "ipcd356",
                                    "--output", str(output / "fabrication/board.d356"), board)
    return commands


def require_declared_variant(base: Path, name: str | None) -> None:
    """KiCad may silently export the default population for an unknown name."""
    if name is None:
        return
    names = kicad_variant_names(base)
    if name not in names:
        raise ValueError(f"KiCad assembly variant {name!r} is not declared in {base}; "
                         f"available: {names}. Do not export the default population by accident")


def export(root: Path, manifest_path: str, output: Path, cli: str,
           assembly_variant: str | None = None) -> ReleaseExportReport:
    root, output = root.resolve(), output.resolve()
    relative = output.relative_to(root).as_posix()
    repo_path(root, relative)
    if not relative.startswith("build/"):
        raise ValueError("Release exports belong under the ignored build/ directory")
    config = load_config(root, manifest_path)
    manifest = read_model(repo_path(root, manifest_path), ProjectManifest)
    settings = manifest.release_exports
    if settings is None or manifest.kind.value != "pcb":
        raise ValueError("PCB release exports require project.json release_exports settings")
    if assembly_variant is not None and not assembly_variant.strip():
        raise ValueError("KiCad assembly variant cannot be blank")
    selected_variant = assembly_variant or settings.assembly_variant
    require_declared_variant(repo_path(root, config.project), selected_variant)
    source = source_state(root)
    if not source.clean or source.commit is None:
        raise ValueError("Release exports require clean committed source")
    output.mkdir(parents=True, exist_ok=False)
    (output / "assembly").mkdir()
    (output / "fabrication").mkdir()
    (output / "review").mkdir()
    version = execute((cli, "version"), root, output, "version")
    if version.returncode != 0 or version.stdout.strip() != config.kicad_version:
        raise ValueError("Export executable must match the pinned project KiCad version")
    commands = {name: execute((cli, *arguments), root, output, name)
                for name, arguments in command_arguments(
                    settings, repo_path(root, config.project), output, selected_variant,
                ).items()}
    issues: list[str] = []
    if commands["bom"].returncode == 0:
        try:
            purchasing_bom(root, output / "assembly/bom.csv", output / "assembly/purchasing-bom.csv")
        except (OSError, ValueError) as exc:
            issues.append(f"Purchasing BOM: {exc}")
    expected = (tuple((output / "fabrication").glob("*.gbr")),
                tuple((output / "fabrication").glob("*.drl")),
                tuple(output / name for name in required_artifacts(settings)))
    files = {path.relative_to(output).as_posix(): digest(path)
             for path in sorted(output.rglob("*")) if path.is_file()}
    passed = (not issues and all(command.returncode == 0 and command.error is None for command in commands.values())
              and all(group and all(path.is_file() and path.stat().st_size for path in group) for group in expected)
              and review_artifacts_valid(output, settings)
              and source_state(root) == source)
    report = ReleaseExportReport(project_id=config.project_id, source=source, toolchain_id=config.toolchain_id,
                                 settings=settings, assembly_variant=selected_variant,
                                 commands={"version": version, **commands},
                                 artifacts_sha256=files, status="PASS" if passed else "FAIL",
                                 issues=tuple(issues))
    write_model(output / "exports.json", report)
    return report


def required_artifacts(settings: ReleaseExportSettings) -> tuple[str, ...]:
    base = ("assembly/positions.csv", "assembly/bom.csv", "assembly/purchasing-bom.csv",
            "review/schematic.pdf", "review/pcb.pdf", "review/board-stats.json")
    extras = {
        "odb": "fabrication/board.odb.zip",
        "ipc2581": "fabrication/board.ipc2581.zip",
        "ipcd356": "fabrication/board.d356",
    }
    return (*base, *(extras[name] for name in settings.supplier_formats))


def review_artifacts_valid(output: Path, settings: ReleaseExportSettings) -> bool:
    try:
        for name in ("review/schematic.pdf", "review/pcb.pdf"):
            if not (output / name).read_bytes().startswith(b"%PDF-"):
                return False
        require_kicad_json_object(output / "review/board-stats.json")
        archives = {"odb": "fabrication/board.odb.zip",
                    "ipc2581": "fabrication/board.ipc2581.zip"}
        for name, path in archives.items():
            if name in settings.supplier_formats and not zipfile.is_zipfile(output / path):
                return False
    except (OSError, UnicodeError, ValueError):
        return False
    return True


def purchasing_bom(root: Path, native_bom: Path, output: Path) -> None:
    """Join native fitted references to the controlled part catalog, without hand edits."""
    registry = load_registry(root)
    parts = {part.id: part for part in read_model(repo_path(root, registry.catalogs.parts), PartsCatalog).parts}
    with native_bom.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        if reader.fieldnames != ["Reference", "Value", "Footprint", "PartID", "DNP"] or not rows:
            raise ValueError("Native BOM has no components or unexpected fields")
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Reference", "Value", "Footprint", "PartID", "Revision", "Manufacturer", "MPN", "Status"))
        for row in rows:
            part = parts.get(row["PartID"])
            if part is None:
                raise ValueError(f"BOM reference {row['Reference']} has no controlled PART_ID")
            writer.writerow(tuple(csv_cell(value) for value in (
                row["Reference"], row["Value"], row["Footprint"], part.id,
                part.revision, part.manufacturer, part.mpn, part.status.value,
            )))


def verify_exports(root: Path, reference: EvidenceFile, source: SourceState,
                   project_id: str, manifest_path: str,
                   assembly_variant: str | None = None) -> ReleaseExportReport:
    path = evidence_path(root, reference)
    report = read_model(path, ReleaseExportReport)
    config = load_config(root, manifest_path)
    manifest = read_model(repo_path(root, manifest_path), ProjectManifest)
    verify_source(report.source, source)
    settings = manifest.release_exports
    if (report.status != "PASS" or report.issues or report.project_id != project_id
            or report.toolchain_id != config.toolchain_id or report.settings != settings
            or report.assembly_variant != (assembly_variant or (settings.assembly_variant if settings else None))):
        raise ValueError("Release exports differ from project or source settings")
    assert settings is not None
    require_declared_variant(repo_path(root, config.project), report.assembly_variant)
    if set(report.commands) != {"version", *command_arguments(
        settings, repo_path(root, config.project), path.parent, report.assembly_variant,
    )} or any(
        command.returncode != 0 or command.error is not None for command in report.commands.values()
    ):
        raise ValueError("Release export commands are incomplete or failed")
    for name in ("gerbers", "position", "bom", "schematic_pdf", "pcb_pdf", "odb", "ipc2581"):
        if name in report.commands:
            argv = report.commands[name].argv
            selected = argv[argv.index("--variant") + 1] if "--variant" in argv else None
            if selected != report.assembly_variant:
                raise ValueError(f"{name} does not use the selected KiCad assembly variant")
    if report.commands["version"].stdout.strip() != config.kicad_version:
        raise ValueError("Release exports used the wrong KiCad version")
    for name, expected in report.artifacts_sha256.items():
        if digest(repo_path(path.parent, name)) != expected:
            raise ValueError(f"Missing or changed release export: {name}")
    if not any(name.endswith(".gbr") for name in report.artifacts_sha256) or not any(
        name.endswith(".drl") for name in report.artifacts_sha256
    ) or not set(required_artifacts(settings)) <= report.artifacts_sha256.keys() or not review_artifacts_valid(
        path.parent, settings,
    ):
        raise ValueError("Release exports lack fabrication or assembly files")
    return report
