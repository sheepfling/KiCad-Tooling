"""Capture exact-version schematic and PCB exports for named variants."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import JsonValue

from .command_evidence_models import CommandEvidence
from .contract_coach import pinned_image, run_command
from .contracts import kicad_variant_names, repo_path, write_model
from .evidence import digest
from .model_primitives import Digest, RepositoryPath
from .native_report_parsing import read_netlist
from .pcb_component_inventory_models import (
    PcbVariantPopulationCoverage,
    PcbVariantPopulationEvidence,
)
from .pcb_component_population import PcbVariantPopulationSource, PcbVariantPositionReceipt
from .pcb_variant_position_export import read_pcb_variant_position_export
from .project_models import ProjectConfig
from .project_source_hashes import hash_project_sources as hashes
from .source_state_models import SourceHashInventory


@dataclass(frozen=True, slots=True)
class PcbVariantPopulationCapture:
    """Variant comparison inputs and the retained source/output evidence state."""

    sources: tuple[PcbVariantPopulationSource, ...]
    coverage: PcbVariantPopulationCoverage

    def __post_init__(self) -> None:
        source_names = tuple(source.variant.casefold() for source in self.sources)
        evidence_names = tuple(item.variant.casefold() for item in self.coverage.evidence)
        if self.coverage.status == "COMPLETE":
            if len(set(source_names)) != len(source_names) or set(source_names) != set(
                evidence_names
            ):
                raise ValueError(
                    "Complete variant sources must match the source-bound evidence inventory"
                )
            evidence_by_variant = {item.variant.casefold(): item for item in self.coverage.evidence}
            for source in self.sources:
                receipt = source.position_receipt
                evidence = evidence_by_variant[source.variant.casefold()]
                if (
                    receipt is None
                    or receipt.path != evidence.board_all_positions_path
                    or receipt.sha256 != evidence.board_all_positions_sha256
                ):
                    raise ValueError(
                        "Complete variant source must match its all-position export receipt"
                    )
        elif self.sources:
            raise ValueError("Incomplete variant capture cannot expose parsed source records")


def supports_named_variant_pcb_values(kicad_version: str) -> bool:
    """Whether the pinned native PCB position exporter preserves variant values."""
    return kicad_version == "10.0.5"


def capture_variant_population(
    root: Path,
    config: ProjectConfig,
    output: Path,
    *,
    expected_source_hashes: SourceHashInventory,
    kicad_version: str,
) -> PcbVariantPopulationCapture:
    """Export each project-declared variant from the same pinned KiCad image."""
    root = root.resolve()
    output = output.resolve()
    try:
        relative_output = output.relative_to(root)
    except ValueError as exc:
        raise ValueError("Variant population receipts must remain inside the checkout") from exc
    if not relative_output.parts or relative_output.parts[0] != "build":
        raise ValueError("Variant population receipts must remain under ignored build/")

    base = repo_path(root, config.project)
    project = base.with_suffix(".kicad_pro")
    schematic = base.with_suffix(".kicad_sch")
    board = base.with_suffix(".kicad_pcb")
    project_relative = project.relative_to(root).as_posix()
    schematic_relative = schematic.relative_to(root).as_posix()
    board_relative = board.relative_to(root).as_posix()
    source_identity: dict[RepositoryPath, Digest] = {}
    evidence: list[PcbVariantPopulationEvidence] = []
    probe_paths: dict[str, str] = {}

    try:
        before = hashes(root, config.source_roots)
        if before != expected_source_hashes:
            raise ValueError("Project sources changed before variant population capture")
        for relative in (project_relative, schematic_relative, board_relative):
            if relative not in before:
                raise ValueError(f"Variant population source is not declared: {relative}")
            source_identity[relative] = before[relative]
        variants = kicad_variant_names(project)
        if not variants:
            if hashes(root, config.source_roots) != before:
                raise ValueError("Project sources changed during variant population inspection")
            return PcbVariantPopulationCapture(
                sources=(),
                coverage=PcbVariantPopulationCoverage(status="NOT_APPLICABLE"),
            )

        image = pinned_image(config.image)
        output.mkdir(parents=True, exist_ok=False)
        probe_path = output / "native_pcb_variant_probe.py"
        probe_path.write_bytes(Path(__file__).with_name("pcb_variant_probe.py.in").read_bytes())
        request_path = output / "board-variant-request.json"
        request_path.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "board_sha256": source_identity[board_relative],
                    "project_sha256": source_identity[project_relative],
                    "variants": variants,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        presence_path = output / "board-variants.json"
        probe_command_path = output / "board-variant-probe.command.json"
        probe_command = run_variant_native_command(
            root,
            output,
            image,
            "/usr/bin/python3",
            (
                "-I",
                "-B",
                f"/output/{probe_path.name}",
                f"/work/{board_relative}",
                f"/output/{request_path.name}",
                f"/output/{presence_path.name}",
            ),
        )
        write_model(probe_command_path, probe_command)
        _require_export(probe_command, presence_path, ", ".join(variants), "PCB variant probe")
        for name, path in (
            ("probe_path", probe_path),
            ("probe_sha256", probe_path),
            ("request_path", request_path),
            ("request_sha256", request_path),
            ("command_path", probe_command_path),
            ("command_sha256", probe_command_path),
        ):
            probe_paths[name] = (
                path.relative_to(root).as_posix() if name.endswith("_path") else digest(path)
            )
        raw_probe_result: JsonValue = json.loads(presence_path.read_text(encoding="utf-8"))
        expected_variant_rows = [{"name": name, "present_on_board": True} for name in variants]
        if not isinstance(raw_probe_result, dict):
            raise TypeError("Native PCB variant probe returned malformed or unbound evidence")
        probe_result: dict[str, JsonValue] = raw_probe_result
        variant_rows_value = probe_result.get("variants")
        if (
            set(probe_result) != {"schema_version", "board_sha256", "project_sha256", "variants"}
            or probe_result.get("schema_version") != "1"
            or probe_result.get("board_sha256") != source_identity[board_relative]
            or probe_result.get("project_sha256") != source_identity[project_relative]
            or not isinstance(variant_rows_value, list)
        ):
            raise ValueError("Native PCB variant probe returned malformed or unbound evidence")
        variant_rows: list[JsonValue] = variant_rows_value
        rows_match = len(variant_rows) == len(expected_variant_rows)
        missing: list[str] = []
        for row_value, expected in zip(variant_rows, expected_variant_rows, strict=False):
            raw_row: JsonValue = row_value
            if not isinstance(raw_row, dict):
                rows_match = False
                continue
            row: dict[str, JsonValue] = raw_row
            if set(row) != {"name", "present_on_board"} or row != expected:
                rows_match = False
            if row.get("name") == expected["name"] and row.get("present_on_board") is False:
                missing.append(str(expected["name"]))
        if not rows_match:
            if missing:
                raise ValueError(
                    "PCB source does not contain the declared named variant(s) "
                    f"{', '.join(missing)}; refusing to compare a default-variant fallback"
                )
            raise ValueError("Native PCB variant names do not match the project variant list")
        sources: list[PcbVariantPopulationSource] = []
        for variant in variants:
            token = hashlib.sha256(variant.encode("utf-8")).hexdigest()[:12]
            netlist_path = output / f"variant-{token}.netlist.xml"
            all_positions_path = output / f"variant-{token}.board-all.csv"
            fitted_positions_path = output / f"variant-{token}.board-fitted.csv"
            netlist_command_path = output / f"variant-{token}.netlist.command.json"
            all_command_path = output / f"variant-{token}.board-all.command.json"
            fitted_command_path = output / f"variant-{token}.board-fitted.command.json"

            netlist_command = _run_export(
                root,
                output,
                image,
                (
                    "sch",
                    "export",
                    "netlist",
                    "--format",
                    "kicadxml",
                    "--variant",
                    variant,
                    "--output",
                    f"/output/{netlist_path.name}",
                    f"/work/{schematic_relative}",
                ),
            )
            write_model(netlist_command_path, netlist_command)
            _require_export(netlist_command, netlist_path, variant, "schematic netlist")
            observed_netlist = read_netlist(netlist_path)

            all_command = _run_export(
                root,
                output,
                image,
                (
                    "pcb",
                    "export",
                    "pos",
                    "--format",
                    "csv",
                    "--side",
                    "both",
                    "--units",
                    "mm",
                    "--variant",
                    variant,
                    "--output",
                    f"/output/{all_positions_path.name}",
                    f"/work/{board_relative}",
                ),
            )
            write_model(all_command_path, all_command)
            _require_export(all_command, all_positions_path, variant, "all PCB positions")

            fitted_command = _run_export(
                root,
                output,
                image,
                (
                    "pcb",
                    "export",
                    "pos",
                    "--format",
                    "csv",
                    "--side",
                    "both",
                    "--units",
                    "mm",
                    "--exclude-dnp",
                    "--variant",
                    variant,
                    "--output",
                    f"/output/{fitted_positions_path.name}",
                    f"/work/{board_relative}",
                ),
            )
            write_model(fitted_command_path, fitted_command)
            _require_export(fitted_command, fitted_positions_path, variant, "fitted PCB positions")

            all_position_export = read_pcb_variant_position_export(all_positions_path)
            fitted_position_export = read_pcb_variant_position_export(fitted_positions_path)
            board_references = all_position_export.references
            if supports_named_variant_pcb_values(kicad_version):
                if all_position_export.value_column_status != "PRESENT":
                    raise ValueError(
                        f"KiCad {kicad_version} position export has no value column for {variant!r}"
                    )
                board_values = all_position_export.values_by_reference
                board_value_status = "AVAILABLE"
            else:
                board_values = None
                board_value_status = "UNSUPPORTED_KICAD_VERSION"
            fitted_references = fitted_position_export.references
            netlist_relative = netlist_path.relative_to(root).as_posix()
            all_relative = all_positions_path.relative_to(root).as_posix()
            fitted_relative = fitted_positions_path.relative_to(root).as_posix()
            netlist_command_relative = netlist_command_path.relative_to(root).as_posix()
            all_command_relative = all_command_path.relative_to(root).as_posix()
            fitted_command_relative = fitted_command_path.relative_to(root).as_posix()
            evidence_row = PcbVariantPopulationEvidence(
                variant=variant,
                netlist_path=netlist_relative,
                netlist_sha256=digest(netlist_path),
                netlist_command_path=netlist_command_relative,
                netlist_command_sha256=digest(netlist_command_path),
                board_all_positions_path=all_relative,
                board_all_positions_sha256=all_position_export.source_sha256,
                board_all_command_path=all_command_relative,
                board_all_command_sha256=digest(all_command_path),
                board_fitted_positions_path=fitted_relative,
                board_fitted_positions_sha256=fitted_position_export.source_sha256,
                board_fitted_command_path=fitted_command_relative,
                board_fitted_command_sha256=digest(fitted_command_path),
            )
            evidence.append(evidence_row)
            sources.append(
                PcbVariantPopulationSource(
                    variant=variant,
                    netlist=observed_netlist,
                    board_references=board_references,
                    fitted_board_references=fitted_references,
                    board_values=board_values,
                    board_value_status=board_value_status,
                    position_receipt=PcbVariantPositionReceipt(
                        path=all_relative,
                        sha256=all_position_export.source_sha256,
                    ),
                )
            )

        if hashes(root, config.source_roots) != before:
            raise ValueError("Project sources changed during variant population capture")
        coverage = PcbVariantPopulationCoverage(
            status="COMPLETE",
            project_path=project_relative,
            project_sha256=source_identity[project_relative],
            schematic_path=schematic_relative,
            schematic_sha256=source_identity[schematic_relative],
            board_path=board_relative,
            board_sha256=source_identity[board_relative],
            kicad_version=kicad_version,
            image=image,
            board_variant_probe_path=probe_paths["probe_path"],
            board_variant_probe_sha256=probe_paths["probe_sha256"],
            board_variant_request_path=probe_paths["request_path"],
            board_variant_request_sha256=probe_paths["request_sha256"],
            board_variant_command_path=probe_paths["command_path"],
            board_variant_command_sha256=probe_paths["command_sha256"],
            evidence=tuple(evidence),
        )
        return PcbVariantPopulationCapture(tuple(sources), coverage)
    except (OSError, ValueError, TypeError, csv.Error) as exc:
        return PcbVariantPopulationCapture(
            sources=(),
            coverage=PcbVariantPopulationCoverage(
                status="BLOCKED",
                project_path=project_relative,
                project_sha256=source_identity.get(project_relative),
                schematic_path=schematic_relative,
                schematic_sha256=source_identity.get(schematic_relative),
                board_path=board_relative,
                board_sha256=source_identity.get(board_relative),
                kicad_version=kicad_version,
                image=config.image,
                board_variant_probe_path=probe_paths.get("probe_path"),
                board_variant_probe_sha256=probe_paths.get("probe_sha256"),
                board_variant_request_path=probe_paths.get("request_path"),
                board_variant_request_sha256=probe_paths.get("request_sha256"),
                board_variant_command_path=probe_paths.get("command_path"),
                board_variant_command_sha256=probe_paths.get("command_sha256"),
                evidence=tuple(evidence),
                issue=str(exc),
            ),
        )


def _run_export(
    root: Path,
    output: Path,
    image: str,
    command: tuple[str, ...],
) -> CommandEvidence:
    return run_variant_native_command(root, output, image, "kicad-cli", command)


def run_variant_native_command(
    root: Path,
    output: Path,
    image: str,
    entrypoint: str,
    command: tuple[str, ...],
) -> CommandEvidence:
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    docker = shutil.which("docker") if sys.platform == "win32" else None
    return run_command(
        root,
        (
            docker or "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m",
            *user,
            "-e",
            "HOME=/tmp",
            "-v",
            f"{root}:/work:ro",
            "-v",
            f"{output}:/output:rw",
            "-w",
            "/work",
            "--entrypoint",
            entrypoint,
            image,
            *command,
        ),
        timeout=600,
    )


def _require_export(
    command: CommandEvidence,
    output: Path,
    variant: str,
    label: str,
) -> None:
    if command.returncode != 0 or command.error is not None or not output.is_file():
        detail = command.error or command.stderr.strip() or "output file is missing"
        raise ValueError(f"KiCad {label} export for {variant!r} failed: {detail[:300]}")


def position_references(path: Path) -> tuple[str, ...]:
    """Read unique native PCB position references for review consumers."""
    return read_pcb_variant_position_export(path).references


_position_references = position_references
