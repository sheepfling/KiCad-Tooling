"""Scoped project-source reads and optimistic exact edits shared by adapters."""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Literal, NamedTuple

from .artifact_access import file_fingerprint, read_regular_bytes
from .bounded_file_content import MAX_CHUNK, read_file_content
from .contracts import parse_model_text, read_model, repo_path, validate_json_object
from .discovery import manifest_paths, settings
from .electrical import simulation_cases
from .electrical_analysis_contract_models import ElectricalAnalysisContract
from .file_access_models import McpEditPreview, McpEditResult, McpFileContent
from .project_models import (
    ProjectManifest,
    ProjectTestContract,
    ToolchainsCatalog,
)
from .purchasing_preference_models import PurchasingPreferences
from .selection import resolve_project

MAX_EDIT_BYTES = 1024 * 1024
MAX_DIFF = 60_000
CAD_TEXT_SUFFIXES = frozenset(
    {
        ".kicad_pro",
        ".kicad_sch",
        ".kicad_pcb",
        ".kicad_sym",
        ".kicad_mod",
        ".kicad_wks",
    }
)
FORBIDDEN_SOURCE_PARTS = frozenset(
    {
        "build",
        "generated",
        "schemas",
        "releases",
        "release",
        "restores",
        "__pycache__",
    }
)


def _island(root: Path, project_id: str) -> Path:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", project_id) is None:
        raise ValueError("Invalid project ID")
    matches = [path.parent for path in manifest_paths(root, project_id)]
    if len(matches) != 1:
        raise ValueError(
            f"Need one configured project island for {project_id}; found {len(matches)}"
        )
    # Do not parse the manifest here: this reader/editor also repairs malformed JSON.
    return matches[0]


def project_owned_source_path(
    root: Path,
    project_id: str,
    source: Path,
    suffix: str,
    *,
    require_existing: bool = True,
) -> tuple[Path, str]:
    """Select a regular, portable authored input inside one project island."""
    root = root.resolve()
    resolve_project(root, project_id)
    try:
        relative = source.relative_to(root) if source.is_absolute() else source
    except ValueError as exc:
        raise ValueError("Selected source must be inside the project island") from exc
    path = repo_path(root, relative.as_posix())
    island = _island(root, project_id)
    if not path.is_relative_to(island):
        raise ValueError("Selected source must be inside the project island")
    inner = path.relative_to(island)
    if (
        path.suffix.lower() != suffix
        or any(
            part.startswith(".")
            or part.casefold() in {"build", "generated", "releases", "restores"}
            for part in inner.parts
        )
        or (require_existing and not path.is_file())
        or (path.is_file() and path.stat().st_mode & 0o111)
    ):
        raise ValueError(f"Select an existing non-executable project-owned {suffix} source")
    return path, relative.as_posix()


def _test_contract(island: Path, value: str) -> bool:
    if value == "tests/contract.json":
        return True
    if not value.endswith(".json"):
        return False
    return read_model(repo_path(island, "project.json"), ProjectManifest).checks == value


def _electrical_sidecar(island: Path, value: str) -> bool:
    if value == "tests/electrical.json":
        return True
    if not value.endswith(".json") or value in {
        "project.json",
        "tests/contract.json",
        "docs/purchasing.json",
    }:
        return False
    manifest = read_model(repo_path(island, "project.json"), ProjectManifest)
    contract = read_model(repo_path(island, manifest.checks), ProjectTestContract)
    return contract.electrical == value


def _validate_electrical(root: Path, island: Path, project_id: str, text: str) -> None:
    contract = parse_model_text(text, ElectricalAnalysisContract)
    if contract.project_id != project_id:
        raise ValueError("Electrical requirements must retain the selected project ID")
    manifest = read_model(repo_path(island, "project.json"), ProjectManifest)
    for case in simulation_cases(contract):
        for name in case.model_sha256:
            model = repo_path(root, name)
            if any(
                part.startswith(".") or part.casefold() in FORBIDDEN_SOURCE_PARTS
                for part in model.relative_to(root.resolve()).parts
            ) or (not model.is_relative_to(island) and name not in manifest.shared_inputs):
                raise ValueError(
                    "Electrical models must be authored project source or declared shared inputs"
                )
            if not stat.S_ISREG(model.lstat().st_mode) or model.stat().st_mode & 0o111:
                raise ValueError(
                    "Electrical models must be existing non-executable regular source files"
                )


def project_file_path(root: Path, project_id: str, value: str) -> Path:
    """Select existing authored text in one island, excluding code and approval records."""
    island = _island(root, project_id)
    path = repo_path(island, value)
    parts = path.relative_to(island).parts
    if any(part.startswith(".") or part.casefold() in FORBIDDEN_SOURCE_PARTS for part in parts):
        raise ValueError(
            "Local state, build outputs, releases and hidden paths are not editable source"
        )
    allowed = (
        value in {"project.json", "tests/contract.json", "README.md", "docs/purchasing.json"}
        or _test_contract(island, value)
        or _electrical_sidecar(island, value)
        or path.suffix.lower() == ".cir"
        or (parts[0] == "docs" and path.suffix.lower() == ".md")
        or path.suffix.lower() in CAD_TEXT_SUFFIXES
        or path.name in {"fp-lib-table", "sym-lib-table"}
    )
    if not allowed:
        raise ValueError(
            "Only authored KiCad text, project.json, the declared check contract and "
            "electrical requirements/models, docs/purchasing.json and project Markdown are available"
        )
    if not path.is_file() or path.stat().st_mode & 0o111:
        raise ValueError("Select an existing non-executable source file")
    return path


def read_project_file(
    root: Path, project_id: str, path: str, offset: int = 0, limit: int = MAX_CHUNK
) -> McpFileContent:
    """Read authored project text and its digest before requesting an exact edit."""
    return read_file_content(root, project_file_path(root, project_id, path), offset, limit, True)


def _validate_edit(
    root: Path, project_id: str, path: Path, text: str
) -> Literal["JSON_MODEL", "TEXT_ONLY"]:
    island = _island(root, project_id)
    relative = path.relative_to(island).as_posix()
    if relative == "project.json":
        manifest = parse_model_text(text, ProjectManifest)
        if manifest.id != project_id:
            raise ValueError("An edit cannot change the project ID")
        project = repo_path(island, manifest.project)
        if project.suffix != ".kicad_pro" or not project.is_file():
            raise ValueError("The project identity must name an existing local .kicad_pro")
        contract = read_model(repo_path(island, manifest.checks), ProjectTestContract)
        if contract.validation.kind is not manifest.kind:
            raise ValueError("Project kind must match the authored test contract")
        for name in (
            *manifest.source_roots,
            *manifest.required_inputs,
            *(
                item
                for item in (manifest.mechanical_handoff, manifest.governance_record)
                if item is not None
            ),
        ):
            repo_path(island, name)
        for name in (*manifest.shared_source_roots, *manifest.shared_inputs):
            repo_path(root, name)
        policy = settings(root)
        catalog = read_model(repo_path(root, policy.catalogs.toolchains), ToolchainsCatalog)
        if manifest.toolchain_id not in {item.id for item in catalog.toolchains}:
            raise ValueError("The proposed toolchain is not catalogued")
        return "JSON_MODEL"
    if _test_contract(island, relative):
        contract = parse_model_text(text, ProjectTestContract)
        manifest = read_model(repo_path(island, "project.json"), ProjectManifest)
        if contract.validation.kind is not manifest.kind:
            raise ValueError("Test contract kind must match the project")
        if contract.electrical is not None:
            sidecar = repo_path(island, contract.electrical)
            parts = sidecar.relative_to(island).parts
            if sidecar.suffix != ".json" or any(
                part.startswith(".") or part.casefold() in FORBIDDEN_SOURCE_PARTS for part in parts
            ):
                raise ValueError("Electrical requirements must name an authored local JSON sidecar")
            data, _ = read_regular_bytes(sidecar, MAX_EDIT_BYTES)
            _validate_electrical(root, island, project_id, data.decode("utf-8"))
        return "JSON_MODEL"
    if _electrical_sidecar(island, relative):
        _validate_electrical(root, island, project_id, text)
        return "JSON_MODEL"
    if relative == "docs/purchasing.json":
        parse_model_text(text, PurchasingPreferences)
        return "JSON_MODEL"
    if path.suffix.lower() == ".kicad_pro":
        try:
            validate_json_object(text)
        except TypeError as exc:
            raise ValueError(str(exc)) from exc
    # KiCad documents are authored text here; KiCad syntax and engineering checks
    # remain required. No format parser or independent expectation is invented.
    return "TEXT_ONLY"


class _PreparedEdit(NamedTuple):
    path: Path
    before: bytes
    after: bytes
    information: os.stat_result
    preview: McpEditPreview


def _prepare_edit(
    root: Path, project_id: str, path: str, expected_sha256: str, old_text: str, new_text: str
) -> _PreparedEdit:
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("expected_sha256 must be a lowercase SHA-256 digest from the current read")
    if not old_text or old_text == new_text:
        raise ValueError("Supply a nonempty old_text and a different replacement")
    if max(len(old_text), len(new_text)) > MAX_CHUNK:
        raise ValueError(f"Edit fragments must not exceed {MAX_CHUNK} characters")
    selected = project_file_path(root, project_id, path)
    before, information = read_regular_bytes(selected, MAX_EDIT_BYTES)
    digest = hashlib.sha256(before).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Source hash mismatch; read the current file and review a fresh edit")
    text = before.decode("utf-8")
    if "\x00" in text or "\x00" in new_text:
        raise ValueError("Source edits require UTF-8 text without binary NUL characters")
    first_match = text.find(old_text)
    if first_match < 0 or text.find(old_text, first_match + 1) >= 0:
        raise ValueError(
            "old_text must match exactly once; include enough unique surrounding context"
        )
    updated = text.replace(old_text, new_text, 1)
    after = updated.encode("utf-8")
    if len(after) > MAX_EDIT_BYTES:
        raise ValueError(f"Edited source exceeds the {MAX_EDIT_BYTES}-byte limit")
    validation = _validate_edit(root, project_id, selected, updated)
    relative = selected.relative_to(root.resolve()).as_posix()
    diff = "".join(
        difflib.unified_diff(
            text.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=relative,
            tofile=relative,
        )
    )
    if len(diff) > MAX_DIFF:
        raise ValueError("Edit diff is too large for review; use smaller source fragments")
    depth = (
        "electrical"
        if selected.suffix.lower() == ".cir" or _electrical_sidecar(_island(root, project_id), path)
        else "native"
    )
    preview = McpEditPreview(
        project_id=project_id,
        path=relative,
        before_sha256=digest,
        after_sha256=hashlib.sha256(after).hexdigest(),
        diff=diff,
        validation=validation,
        next_command=f"python -B -m kicad_tooling.verify --project {project_id} --depth {depth}",
    )
    return _PreparedEdit(selected, before, after, information, preview)


def preview_project_edit(
    root: Path, project_id: str, path: str, expected_sha256: str, old_text: str, new_text: str
) -> McpEditPreview:
    """Preview one exact caller-supplied replacement; never infer electrical expectations."""
    return _prepare_edit(root, project_id, path, expected_sha256, old_text, new_text).preview


def apply_project_edit(
    root: Path, project_id: str, path: str, expected_sha256: str, old_text: str, new_text: str
) -> McpEditResult:
    """Apply a reviewed replacement with rechecked digest and atomic publication.

    Close KiCad/external editors first. This is optimistic stale-write protection;
    it is not a cross-process filesystem transaction against uncooperative writers.
    The MCP server serializes its own operations. Source checks remain required.
    """
    edit = _prepare_edit(root, project_id, path, expected_sha256, old_text, new_text)
    descriptor, name = tempfile.mkstemp(prefix=".mcp-edit-", dir=edit.path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(edit.after)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(stat.S_IMODE(edit.information.st_mode))
        current = project_file_path(root, project_id, path)
        current_bytes, information = read_regular_bytes(current, MAX_EDIT_BYTES)
        if current_bytes != edit.before or file_fingerprint(information) != file_fingerprint(
            edit.information
        ):
            raise ValueError("Source changed before publication; edit was not applied")
        os.replace(temporary, current)
        verified, _ = read_regular_bytes(project_file_path(root, project_id, path), MAX_EDIT_BYTES)
        readback = hashlib.sha256(verified).hexdigest()
        if readback != edit.preview.after_sha256:
            raise ValueError(
                "Source changed after publication; inspect the current file before retrying"
            )
        return McpEditResult(
            project_id=project_id,
            path=edit.preview.path,
            before_sha256=edit.preview.before_sha256,
            after_sha256=edit.preview.after_sha256,
            readback_sha256=readback,
            next_command=edit.preview.next_command,
        )
    finally:
        temporary.unlink(missing_ok=True)
