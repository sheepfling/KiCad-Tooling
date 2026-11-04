"""Join explicit parts and drawing receipts into source-matched navigation."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

from .artifact_access import artifact_file, read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import parse_model_text, repo_path, write_model
from .cross_probe_board import BoardFootprintAnchor, board_footprint_anchors
from .cross_probe_html import render_cross_probe
from .cross_probe_models import CrossProbeEntry, CrossProbeLocation, CrossProbeReport
from .cross_probe_schematic import (
    SchematicSymbolAnchor,
    schematic_drawing_bindings,
    schematic_symbol_anchors,
)
from .cross_probe_variant import VariantObservation, read_variant_observation
from .discovery import load_config
from .evidence import digest
from .findings_view_evidence import verified_findings_drawing
from .findings_view_models import FindingsViewReport, ReviewDrawing
from .native_project_validation_models import ValidationSummary
from .native_summary_binding import validate_native_summary_binding
from .parts_receipts import read_parts_receipt
from .project_source_hashes import hash_project_sources as hashes
from .purchasing import read_components
from .purchasing_models import PurchasingComponent
from .review_overview_evidence import (
    ReviewContext,
    read_receipt,
    recorded_directory,
    selected_receipt,
    source_mismatch,
)
from .schematic_geometry_source import schematic_root, schematic_scalar, schematic_sheet_references
from .selection import resolve_project


def _source_bytes(root: Path, name: str, sha256: str) -> bytes:
    content, _ = read_regular_bytes(repo_path(root, name), maximum=32 * 1024 * 1024)
    if hashlib.sha256(content).hexdigest() != sha256:
        raise ValueError(f"Project source changed while reading: {name}")
    return content


def _entry(
    component: PurchasingComponent,
    *,
    duplicate: bool,
    board_path: str,
    board_anchors: Mapping[str, tuple[BoardFootprintAnchor, ...]],
    schematic_anchors: Mapping[str, tuple[SchematicSymbolAnchor, ...]],
    board_drawing: ReviewDrawing | None,
    schematic_drawings: Mapping[str, ReviewDrawing],
) -> CrossProbeEntry:
    excluded = component.dnp or component.exclude_from_bom
    population = (
        "DUPLICATE"
        if duplicate
        else "DNP"
        if component.dnp
        else "EXCLUDED"
        if component.exclude_from_bom
        else "FITTED"
    )
    if duplicate:
        return CrossProbeEntry(
            reference=component.reference,
            part_id=component.part_id,
            value=component.value,
            footprint=component.footprint,
            population=population,
            issues=("Duplicate case-insensitive parts reference; no unique location assigned.",),
        )
    if excluded:
        return CrossProbeEntry(
            reference=component.reference,
            part_id=component.part_id,
            value=component.value,
            footprint=component.footprint,
            population=population,
            issues=("DNP or excluded component; no fitted placement asserted.",),
        )
    key = component.reference.casefold()
    issues: list[str] = []
    board: list[CrossProbeLocation] = []
    placed = board_anchors.get(key, ())
    if len(placed) > 1:
        issues.append("PCB has duplicate reference placements; no board location assigned.")
    elif not placed:
        issues.append("No matching PCB footprint placement.")
    else:
        item = placed[0]
        if item.issue or item.x_mm is None or item.y_mm is None or item.side is None:
            issues.append(item.issue or "PCB position is unsupported.")
        else:
            if component.footprint and component.footprint != item.footprint:
                issues.append(
                    "Assigned and placed footprint identities differ; inspect both sources."
                )
            drawing_file = (
                board_drawing.file
                if board_drawing is not None
                and board_drawing.mapping_supported
                and item.side == "F.Cu"
                and 0 <= item.x_mm <= board_drawing.width_mm
                and 0 <= item.y_mm <= board_drawing.height_mm
                else None
            )
            if drawing_file is None:
                issues.append("PCB source position has no supported front-board drawing marker.")
            board.append(
                CrossProbeLocation(
                    kind="pcb",
                    source_path=board_path,
                    x_mm=item.x_mm,
                    y_mm=item.y_mm,
                    side=item.side,
                    drawing_file=drawing_file,
                )
            )
    schematic: list[CrossProbeLocation] = []
    symbols = schematic_anchors.get(key, ())
    if not symbols:
        issues.append("No uniquely instance-mapped schematic symbol location.")
    for symbol in symbols:
        schematic_drawing = schematic_drawings.get(symbol.sheet_instance_path)
        drawing_file = (
            schematic_drawing.file
            if schematic_drawing is not None
            and schematic_drawing.mapping_supported
            and (
                schematic_drawing.schematic_source is None
                or schematic_drawing.schematic_source == symbol.source_path
            )
            and 0 <= symbol.x_mm <= schematic_drawing.width_mm
            and 0 <= symbol.y_mm <= schematic_drawing.height_mm
            else None
        )
        if drawing_file is None:
            issues.append(
                "Schematic symbol has a source coordinate without a supported SVG marker."
            )
        schematic.append(
            CrossProbeLocation(
                kind="schematic",
                source_path=symbol.source_path,
                x_mm=symbol.x_mm,
                y_mm=symbol.y_mm,
                drawing_file=drawing_file,
                sheet_instance_path=symbol.sheet_instance_path,
                sheet_path=symbol.sheet_path,
                symbol_uuid=symbol.symbol_uuid,
            )
        )
    return CrossProbeEntry(
        reference=component.reference,
        part_id=component.part_id,
        value=component.value,
        footprint=component.footprint,
        population=population,
        board=tuple(board),
        schematic=tuple(schematic),
        issues=tuple(dict.fromkeys(issues)),
    )


def build_cross_probe(
    root: Path,
    project_id: str,
    parts_report: Path,
    findings_view: Path,
    output: Path | None = None,
    assembly_variant: str | None = None,
) -> CrossProbeReport:
    """Export reversible links only for current, explicit, matching evidence."""
    root = root.resolve()
    project = resolve_project(root, project_id)
    config = load_config(root, project.config)
    current = hashes(root, config.source_roots)
    context = ReviewContext(root, project_id, config, current)
    parts_path, parts, parts_sha = read_parts_receipt(root, parts_report, project_id)
    findings_path = selected_receipt(root, findings_view, "review.json")
    findings, findings_sha = read_receipt(findings_path, FindingsViewReport)
    if (
        findings.project_id != project_id
        or not recorded_directory(root, findings.output_directory, findings_path.parent)
        or dict(parts.source_hashes) != current
        or dict(findings.source_hashes) != current
    ):
        raise ValueError("Parts and drawings must match the current project and source scope")
    mismatch = source_mismatch(context, parts.input_hashes, exact_scope=False)
    if mismatch:
        raise ValueError(f"Parts catalog or input is stale: {mismatch}")
    summary_path = artifact_file(root, findings.native_summary)
    if digest(summary_path) != findings.native_summary_sha256:
        raise ValueError("Findings native summary changed")
    summary_bytes, _ = read_regular_bytes(summary_path, maximum=8 * 1024 * 1024)
    summary = parse_model_text(summary_bytes.decode("utf-8"), ValidationSummary)
    validate_native_summary_binding(summary, config, current)
    variant: VariantObservation | None = (
        None
        if assembly_variant is None
        else read_variant_observation(
            root,
            config,
            current,
            findings,
            assembly_variant,
            summary.artifacts_sha256.get("netlist.xml"),
        )
    )
    drawing_bytes = {
        drawing.file: verified_findings_drawing(root, findings_path, drawing, findings)
        for drawing in findings.drawings
    }
    if len(drawing_bytes) != len(findings.drawings):
        raise ValueError("Findings receipt repeats a drawing filename")
    board_path = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    board_anchors: dict[str, tuple[BoardFootprintAnchor, ...]] = {}
    if board_path in current:
        board_anchors = board_footprint_anchors(
            _source_bytes(root, board_path, current[board_path])
        )
    root_schematic = Path(config.project).with_suffix(".kicad_sch").as_posix()
    schematic_files = {
        name: _source_bytes(root, name, sha)
        for name, sha in current.items()
        if name.endswith(".kicad_sch")
    }
    schematic_anchors, schematic_issues = schematic_symbol_anchors(
        schematic_files,
        root_path=root_schematic,
        project_directory=Path(config.project).parent.as_posix(),
        project_name=Path(config.project).stem,
    )
    board_drawings = tuple(item for item in findings.drawings if item.kind == "pcb")
    schematic_drawings = tuple(item for item in findings.drawings if item.kind == "schematic")
    board_drawing = board_drawings[0] if len(board_drawings) == 1 else None
    root_instance = None
    if root_schematic in schematic_files:
        document = schematic_root(schematic_files[root_schematic])
        text = document.text
        root_node = document.root
        if not schematic_sheet_references(schematic_files[root_schematic]):
            root_instance = "/" + schematic_scalar(text, root_node, "uuid")
    schematic_by_instance, drawing_issues = schematic_drawing_bindings(
        schematic_drawings,
        current,
        root_source=root_schematic,
        legacy_root_instance=root_instance,
    )
    plan = parts.plan
    assert plan is not None
    base_keys = {item.reference.casefold() for item in plan.components}
    extra = (
        tuple(
            item
            for item in read_components(variant.netlist_path)
            if item.reference.casefold() not in base_keys
        )
        if variant is not None
        else ()
    )
    components = (*plan.components, *extra)
    counts = Counter(item.reference.casefold() for item in components)
    entries = tuple(
        _entry(
            component,
            duplicate=counts[component.reference.casefold()] > 1,
            board_path=board_path,
            board_anchors=board_anchors,
            schematic_anchors=schematic_anchors,
            board_drawing=board_drawing,
            schematic_drawings=schematic_by_instance,
        ).model_copy(
            update={
                "origin": (
                    "PARTS_PLAN"
                    if component.reference.casefold() in base_keys
                    else "VARIANT_NATIVE"
                )
            }
        )
        for component in components
    )
    if variant is not None:
        observed_entries: list[CrossProbeEntry] = []
        for entry, component in zip(entries, components, strict=True):
            key = entry.reference.casefold()
            native_component = variant.schematic.get(key)
            schematic_population = (
                "ABSENT"
                if native_component is None
                else "DNP"
                if key in variant.schematic_dnp
                else "FITTED"
            )
            board_population = (
                "FITTED"
                if key in variant.board_fitted
                else "DNP"
                if key in variant.board_all
                else "ABSENT"
            )
            located = entry
            if (
                entry.population in {"DNP", "EXCLUDED"}
                and board_population == "FITTED"
                and counts[key] == 1
            ):
                located = _entry(
                    component.model_copy(update={"dnp": False, "exclude_from_bom": False}),
                    duplicate=False,
                    board_path=board_path,
                    board_anchors=board_anchors,
                    schematic_anchors=schematic_anchors,
                    board_drawing=board_drawing,
                    schematic_drawings=schematic_by_instance,
                )
            row_issues = list(located.issues)
            if entry.origin == "VARIANT_NATIVE":
                row_issues.append(
                    "Reference comes from the selected variant, not the parts receipt."
                )
            board = located.board
            if board_population != "FITTED" and board:
                board = ()
                row_issues.append("Selected variant does not have a fitted PCB position.")
            if entry.origin == "PARTS_PLAN":
                if entry.population == "FITTED" and board_population != "FITTED":
                    row_issues.append("Parts-plan fitted state differs from selected PCB variant.")
                elif entry.population in {"DNP", "EXCLUDED"} and board_population == "FITTED":
                    row_issues.append("Selected PCB variant fits a parts-plan excluded reference.")
            if schematic_population == "DNP" and board_population == "FITTED":
                row_issues.append("Selected variant schematic and PCB population differ.")
            if schematic_population == "ABSENT" and board_population == "FITTED":
                row_issues.append(
                    "Selected variant PCB reference is absent from its schematic netlist."
                )
            if (
                native_component is not None
                and entry.population != "DUPLICATE"
                and entry.origin == "PARTS_PLAN"
            ):
                if entry.part_id != native_component.part_id:
                    row_issues.append("Parts-plan and selected variant part identities differ.")
                if entry.value != native_component.value:
                    row_issues.append("Parts-plan and selected variant values differ.")
                if entry.footprint != native_component.footprint:
                    row_issues.append("Parts-plan and selected variant footprints differ.")
            observed_entries.append(
                located.model_copy(
                    update={
                        "population": entry.population,
                        "origin": entry.origin,
                        "board": board,
                        "variant_schematic": schematic_population,
                        "variant_board": board_population,
                        "variant_part_id": (
                            native_component.part_id if native_component is not None else None
                        ),
                        "variant_value": (
                            native_component.value if native_component is not None else None
                        ),
                        "variant_footprint": (
                            native_component.footprint if native_component is not None else None
                        ),
                        "issues": tuple(row_issues),
                    }
                )
            )
        entries = tuple(observed_entries)
    part_keys = {item.reference.casefold() for item in entries}
    board_only = (
        tuple(sorted((ref for key, ref in variant.board_all.items() if key not in part_keys)))
        if variant is not None
        else ()
    )
    issues = [*schematic_issues, *drawing_issues]
    if not board_drawings:
        issues.append("No retained PCB drawing is available for markers.")
    if any(location.drawing_file is None for entry in entries for location in entry.schematic):
        issues.append("Some schematic symbol instances have no uniquely bound SVG drawing.")
    if variant is None:
        issues.append(
            "Variant identity is not recorded in the selected parts and drawing receipts."
        )
    else:
        issues.append(
            "Selected named variant is observed in native exports; the parts receipt has no variant identity."
        )
        if board_only:
            issues.append("Selected variant has PCB references absent from its schematic netlist.")

    def verify_inputs() -> None:
        if (
            hashes(root, config.source_roots) != current
            or load_config(root, project.config) != config
        ):
            raise ValueError("Project source or configuration changed during cross-probe export")
        if digest(parts_path) != parts_sha or digest(findings_path) != findings_sha:
            raise ValueError("Selected parts or drawing receipt changed during export")
        if digest(parts_path.parent / "netlist.xml") != parts.netlist_sha256:
            raise ValueError("Retained parts netlist changed during export")
        if digest(summary_path) != findings.native_summary_sha256:
            raise ValueError("Retained native summary changed during export")
        for drawing in findings.drawings:
            if (
                verified_findings_drawing(root, findings_path, drawing, findings)
                != drawing_bytes[drawing.file]
            ):
                raise ValueError("Retained drawing changed during export")
        if (
            variant is not None
            and read_variant_observation(
                root,
                config,
                current,
                findings,
                variant.name,
                summary.artifacts_sha256.get("netlist.xml"),
            )
            != variant
        ):
            raise ValueError("Named variant evidence changed during export")

    verify_inputs()
    target = output or Path("build/cross-probe") / f"{project_id}-{uuid4().hex[:12]}"
    directory = receipt_directory(root, project_id, target)
    for name, content in drawing_bytes.items():
        (directory / name).write_bytes(content)
    report = CrossProbeReport(
        project_id=project_id,
        parts_report=parts_path.relative_to(root).as_posix(),
        parts_report_sha256=parts_sha,
        findings_view=findings_path.relative_to(root).as_posix(),
        findings_view_sha256=findings_sha,
        source_hashes=current,
        variant_scope="NAMED_OBSERVED" if variant is not None else "NOT_RECORDED",
        assembly_variant=variant.name if variant is not None else None,
        variant_lint_report=(
            variant.lint_path.relative_to(root).as_posix() if variant is not None else None
        ),
        variant_lint_report_sha256=variant.lint_sha256 if variant is not None else None,
        variant_evidence_sha256=variant.evidence_sha256 if variant is not None else {},
        variant_board_only=board_only,
        entries=entries,
        drawings=findings.drawings,
        issues=tuple(issues),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_cross_probe(report), encoding="utf-8")
    verify_inputs()
    report = report.model_copy(
        update={"artifacts_sha256": {path.name: digest(path) for path in directory.iterdir()}}
    )
    write_model(directory / "cross-probe.json", report)
    return report
