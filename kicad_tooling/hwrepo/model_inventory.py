"""Read-only, project-scoped inventory of PCB footprint 3D model assignments.

This is a static source inventory, not a geometry loader or mechanical approval.
The board's footprint instances are authoritative: library footprints may differ
from the copies already placed on a board.
"""
from __future__ import annotations

import os
import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from .contracts import repo_path
from .models import (
    DiagnosticFinding,
    FootprintModels,
    InventoryStatus,
    ModelAssignment,
    ModelInventoryReport,
    ProjectConfig,
    ProjectKind,
    Resolution,
)
from .repository import cad_dependencies

# Preserve the original service-module import surface for existing consumers.
__all__ = [
    "FootprintModels",
    "InventoryStatus",
    "ModelAssignment",
    "ModelInventoryReport",
    "Resolution",
    "inspect_models",
]

MODEL_SUFFIXES = frozenset({".step", ".stp", ".wrl", ".idf", ".igs", ".iges"})
GUIDE = "docs/workflow/LIBRARIES.md"



@dataclass(frozen=True)
class _Span:
    start: int
    end: int


def _children(text: str, start: int, end: int) -> tuple[_Span, ...]:
    """Return direct S-expression children, respecting strings and comments."""
    children: list[_Span] = []
    depth = 0
    opening = 0
    quoted = False
    escaped = False
    comment = False
    for position in range(start, end):
        char = text[position]
        if comment:
            if char == "\n":
                comment = False
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == "#":
            comment = True
        elif char == '"':
            quoted = True
        elif char == "(":
            if depth == 0:
                opening = position
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("Unmatched closing parenthesis in PCB source")
            if depth == 0:
                children.append(_Span(opening, position + 1))
    if quoted:
        raise ValueError("Unterminated quoted string in PCB source")
    if depth:
        raise ValueError("Unclosed parenthesis in PCB source")
    return tuple(children)


def _atoms(text: str, span: _Span) -> tuple[str, ...]:
    """Read only a node's leading atoms, before its first child expression."""
    values: list[str] = []
    position = span.start + 1
    while position < span.end - 1:
        while position < span.end - 1 and text[position].isspace():
            position += 1
        if position >= span.end - 1 or text[position] in "()":
            break
        if text[position] == "#":
            newline = text.find("\n", position, span.end)
            if newline < 0:
                break
            position = newline + 1
            continue
        if text[position] == '"':
            position += 1
            value: list[str] = []
            while position < span.end - 1:
                char = text[position]
                if char == "\\" and position + 1 < span.end - 1:
                    following = text[position + 1]
                    # Only quote and backslash need unescaping for model paths.
                    value.append(following if following in {'"', "\\"} else "\\" + following)
                    position += 2
                elif char == '"':
                    position += 1
                    break
                else:
                    value.append(char)
                    position += 1
            else:
                raise ValueError("Unterminated quoted atom in PCB source")
            values.append("".join(value))
        else:
            start = position
            while position < span.end - 1 and not text[position].isspace() and text[position] not in "()":
                position += 1
            values.append(text[start:position])
    return tuple(values)


def _finding(code: str, location: str, observed: str, action: str,
             blocking: bool = False) -> DiagnosticFinding:
    return DiagnosticFinding(
        severity="BLOCKING" if blocking else "REVIEW", code=code,
        location=location, observed=observed, action=action, guide=GUIDE,
    )


def _source_candidates(root: Path, config: ProjectConfig) -> dict[str, tuple[str, ...]]:
    candidates: dict[str, list[str]] = {}
    for name in config.required_inputs:
        path = Path(name)
        if path.suffix.lower() not in MODEL_SUFFIXES:
            continue
        if not any(name.startswith(f"{source}/") for source in config.source_roots):
            continue
        try:
            if not repo_path(root, name).is_file():
                continue
        except ValueError:
            continue
        candidates.setdefault(path.stem, []).append(name)
    return {stem: tuple(sorted(paths)) for stem, paths in candidates.items()}


def _resolve_model(
    root: Path, config: ProjectConfig, board: Path, value: str, line: int,
    embedded_issue: str | None,
) -> ModelAssignment:
    if not value:
        return ModelAssignment(path=value, line=line, resolution="broken",
                               reason="Empty 3D model path")
    if Path(value).suffix.casefold() not in MODEL_SUFFIXES:
        return ModelAssignment(path=value, line=line, resolution="broken",
                               reason="Unsupported KiCad 3D model file format")
    if value.startswith("kicad-embed://"):
        return ModelAssignment(
            path=value, line=line,
            resolution="broken" if embedded_issue else "embedded_present",
            reason=embedded_issue,
        )
    if "\\" in value or value.startswith("/") or PureWindowsPath(value).drive:
        return ModelAssignment(path=value, line=line, resolution="broken",
                               reason="Machine-local or backslash path")
    major = config.kicad_version.split(".")[0]
    variables = re.findall(r"\$\{([^}]+)\}", value)
    if variables and len(variables) == 1 and variables[0] in {
        f"KICAD{major}_SYMBOL_DIR", f"KICAD{major}_FOOTPRINT_DIR",
        f"KICAD{major}_3DMODEL_DIR",
    }:
        if value.startswith("${" + variables[0] + "}/") and ".." not in value.split("/"):
            return ModelAssignment(path=value, line=line, resolution="toolchain_dependent",
                                   reason="Resolve with the project's exact native KiCad toolchain")
        return ModelAssignment(path=value, line=line, resolution="broken",
                               reason="Invalid versioned KiCad library path")
    if any(variable != "KIPRJMOD" for variable in variables) or "$" in value.replace(
        "${KIPRJMOD}", ""
    ):
        return ModelAssignment(path=value, line=line, resolution="broken",
                               reason="Undeclared path variable")
    if value.count("${KIPRJMOD}") > 1:
        return ModelAssignment(path=value, line=line, resolution="broken",
                               reason="Repeated KIPRJMOD variable")
    project_dir = board.parent
    target = Path(value.replace("${KIPRJMOD}", str(project_dir)))
    if not target.is_absolute():
        target = project_dir / target
    try:
        normalized = Path(os.path.abspath(target))
        relative = normalized.relative_to(root).as_posix()
        resolved = repo_path(root, relative)
        if not resolved.is_file():
            raise ValueError("Model file does not exist")
        if relative not in config.required_inputs:
            raise ValueError("Model file is not declared in this project's required_inputs")
        if not any(relative.startswith(f"{source}/") for source in config.source_roots):
            raise ValueError("Model file is outside this project's declared source roots")
    except ValueError as exc:
        return ModelAssignment(path=value, line=line, resolution="broken", reason=str(exc))
    return ModelAssignment(path=value, line=line, resolution="source_present",
                           source_path=relative)


def inspect_models(root: Path, config: ProjectConfig) -> ModelInventoryReport:
    """Inspect placed footprint models without modifying KiCad or repository files.

    READY means static references and coverage are present. Native export and a
    visual/mechanical review remain separate checks.
    """
    root = root.resolve()
    derived = repo_path(root, config.project).with_suffix(".kicad_pcb")
    board = repo_path(root, derived.relative_to(root).as_posix())
    board_name = board.relative_to(root).as_posix()
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        raise ValueError("3D model inventory requires a pcb or pcb_only project")
    if not board.is_file():
        finding = _finding("MODEL_BOARD_MISSING", board_name, "PCB source file is missing",
                           "Restore the authoritative PCB source, then rerun the inventory.", True)
        return ModelInventoryReport(project_id=config.project_id, board=board_name, status="FAIL",
                                    footprints=(), findings=(finding,),
                                    next_actions=(finding.action,))
    source = board.read_text(encoding="utf-8")
    try:
        roots = _children(source, 0, len(source))
        if len(roots) != 1 or not _atoms(source, roots[0]) or _atoms(source, roots[0])[0] != "kicad_pcb":
            raise ValueError("Expected exactly one kicad_pcb root expression")
        board_nodes = _children(source, roots[0].start + 1, roots[0].end - 1)
    except ValueError as exc:
        finding = _finding("MODEL_BOARD_PARSE", board_name, str(exc),
                           "Open and repair the authoritative board in KiCad, then rerun the inventory.",
                           True)
        return ModelInventoryReport(project_id=config.project_id, board=board_name, status="FAIL",
                                    footprints=(), findings=(finding,),
                                    next_actions=(finding.action,))
    newline_positions = tuple(match.start() for match in re.finditer("\n", source))

    def line(position: int) -> int:
        return bisect_right(newline_positions, position) + 1

    # Retain the existing embedded-record check. Native KiCad still owns decoding.
    dependency_issues = cad_dependencies(
        root, board, board.parent, config.kicad_version.split(".")[0],
        frozenset(config.required_inputs), frozenset(config.source_roots),
    )
    candidates = _source_candidates(root, config)
    footprints: list[FootprintModels] = []
    findings: list[DiagnosticFinding] = []
    for node in board_nodes:
        header = _atoms(source, node)
        if not header or header[0] not in {"footprint", "module"}:
            continue
        footprint_id = header[1] if len(header) > 1 else "<unknown>"
        reference = ""
        model_nodes: list[_Span] = []
        for child in _children(source, node.start + 1, node.end - 1):
            values = _atoms(source, child)
            if len(values) > 2 and (
                values[:2] == ("property", "Reference")
                or (values[:2] == ("fp_text", "reference") and not reference)
            ):
                reference = values[2]
            elif values and values[0] == "model":
                model_nodes.append(child)
        missing_reference = not reference
        if missing_reference:
            reference = f"<unknown@{line(node.start)}>"
            findings.append(_finding(
                "MODEL_REFERENCE_UNKNOWN", f"{board_name}:{line(node.start)}",
                f"Footprint {footprint_id!r} has no readable reference designator",
                "Open this footprint in KiCad and restore its reference designator.", True,
            ))
        entries: list[ModelAssignment] = []
        for model_node in model_nodes:
            values = _atoms(source, model_node)
            value = values[1] if len(values) > 1 else ""
            model_line = line(model_node.start)
            embedded_issue = next((
                issue for issue in dependency_issues
                if issue.startswith(f"CAD_PATH: {board_name}:{model_line}:")
                and "missing embedded model" in issue and repr(value) in issue
            ), None)
            entry = _resolve_model(root, config, board, value, model_line, embedded_issue)
            hidden = any(
                (tokens := _atoms(source, child)) and tokens[0] == "hide"
                and (len(tokens) == 1 or tokens[1].lower() in {"yes", "true", "1"})
                for child in _children(source, model_node.start + 1, model_node.end - 1)
            )
            if hidden:
                entry = ModelAssignment(
                    path=entry.path, line=entry.line, resolution=entry.resolution,
                    source_path=entry.source_path, hidden=True, reason=entry.reason,
                )
            entries.append(entry)
            if entry.resolution == "broken":
                findings.append(_finding(
                    "MODEL_PATH", f"{board_name}:{model_line}",
                    f"{reference}: {value!r}: {entry.reason}",
                    "Correct the model reference or add the intended, reviewed model to this "
                    "project or a declared shared library; then rerun portable and native checks.", True,
                ))
            elif entry.resolution == "toolchain_dependent":
                findings.append(_finding(
                    "MODEL_TOOLCHAIN", f"{board_name}:{model_line}",
                    f"{reference}: {value!r} depends on installed KiCad model libraries",
                    "Check this exact model in the pinned native KiCad runner and inspect the render.",
                ))
        visible = tuple(entry for entry in entries if not entry.hidden and entry.resolution != "broken")
        has_step_model = any(
            Path(entry.path).suffix.casefold() in {".step", ".stp", ".igs", ".iges"}
            for entry in visible
        )
        missing_step_substitute = False
        for entry in visible:
            if entry.resolution != "source_present" or not entry.path.lower().endswith(".wrl"):
                continue
            source_path = entry.source_path
            if not has_step_model and source_path is not None and not any(
                Path(source_path).with_suffix(extension).as_posix() in config.required_inputs
                for extension in (".step", ".stp", ".igs", ".iges")
            ):
                missing_step_substitute = True
                findings.append(_finding(
                    "MODEL_STEP_SUBSTITUTE", f"{board_name}:{entry.line}",
                    f"{reference}: VRML model {entry.path!r} has no declared STEP/IGES body",
                    "Add and review a STEP/IGES model for mechanical export, "
                    "or inspect and document why this component will be absent from STEP.",
                ))
        idf_only = bool(visible) and all(
            Path(entry.path).suffix.casefold() == ".idf" for entry in visible
        )
        if idf_only:
            idf = visible[0]
            findings.append(_finding(
                "MODEL_IDF_ONLY", f"{board_name}:{idf.line}",
                f"{reference}: IDF model {idf.path!r} does not supply a 3D body for these exports",
                "Assign and review a STEP/IGES or VRML model for 3D views and STEP/GLB; "
                "keep IDF for its separate mechanical handoff if needed.",
            ))
        asset_stem = footprint_id.rsplit(":", 1)[-1]
        exact_candidates = candidates.get(asset_stem, ())
        if not entries:
            findings.append(_finding(
                "MODEL_UNASSIGNED", f"{board_name}:{line(node.start)}",
                f"{reference} ({footprint_id}) has no assigned 3D model",
                "Decide whether this footprint needs a model. If so, assign the reviewed source "
                "in KiCad; if intentionally model-free, record that design decision.",
            ))
        elif all(entry.hidden for entry in entries):
            findings.append(_finding(
                "MODEL_HIDDEN", f"{board_name}:{line(node.start)}",
                f"{reference} has model assignments, but all are hidden",
                "Show the intended model in KiCad or record why this footprint is omitted from 3D views.",
            ))
        status: InventoryStatus = (
            "FAIL" if missing_reference or any(entry.resolution == "broken" for entry in entries)
            else "REVIEW" if not entries or all(entry.hidden for entry in entries)
            or missing_step_substitute or idf_only
            or any(entry.resolution == "toolchain_dependent" for entry in entries)
            else "READY"
        )
        footprints.append(FootprintModels(
            reference=reference, footprint_id=footprint_id, line=line(node.start),
            models=tuple(entries), candidate_assets=exact_candidates, status=status,
        ))
    if not footprints:
        findings.append(_finding(
            "MODEL_NO_FOOTPRINTS", board_name, "Board contains no placed footprints",
            "Confirm this is the intended board before requesting an assembled 3D view.",
        ))
    overall: InventoryStatus = (
        "FAIL" if any(item.severity == "BLOCKING" for item in findings)
        else "REVIEW" if findings else "READY"
    )
    actions = tuple(dict.fromkeys(item.action for item in findings))
    return ModelInventoryReport(
        project_id=config.project_id, board=board_name, status=overall,
        footprints=tuple(footprints), findings=tuple(findings), next_actions=actions,
    )
