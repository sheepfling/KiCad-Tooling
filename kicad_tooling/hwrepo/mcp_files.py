"""Bounded local MCP artifact reads and explicit, stale-write-protected source edits."""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Literal, NamedTuple

from .contracts import parse_model_text, read_model, repo_path, validate_json_object
from .discovery import manifest_paths, settings
from .electrical import simulation_cases
from .layout import layout, within_roots
from .models import (
    ElectricalAnalysisContract,
    McpArtifactEntry,
    McpArtifactList,
    McpEditPreview,
    McpEditResult,
    McpFileContent,
    ProjectManifest,
    ProjectTestContract,
    PurchasingPreferences,
    ToolchainsCatalog,
)

MAX_CHUNK = 20_000
MAX_TEXT_BYTES = 10 * 1024 * 1024
MAX_EDIT_BYTES = 1024 * 1024
MAX_DIFF = 60_000
MAX_DIRECTORY_ENTRIES = 10_000
ARTIFACT_TEXT_SUFFIXES = frozenset(
    {
        ".json",
        ".jsonl",
        ".csv",
        ".tsv",
        ".txt",
        ".log",
        ".md",
        ".svg",
        ".xml",
        ".net",
        ".gbr",
        ".ger",
        ".gbrjob",
        ".drl",
        ".pos",
        ".yaml",
        ".yml",
        ".toml",
        ".cir",
        ".raw",
    }
)
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


def artifact_path(root: Path, value: str) -> Path:
    """Confine artifact paths to build trees; restored source is a separate boundary.

    The path may name an existing file/directory or a new output destination. Each
    caller checks the required kind. No symlink component or parent traversal is allowed.
    """
    path = repo_path(root, value)
    parts = path.relative_to(root.resolve()).parts
    boundary: int | None = None
    if parts[0] == "build":
        boundary = 0
    else:
        for index, component in enumerate(parts):
            if component != "build" or index == 0:
                continue
            owner = "/".join(parts[:index])
            # Project paths must resolve to an actual configured island. Product
            # artifact scope retains its configured source-root boundary.
            if any(path.parent == root.resolve() / owner for path in manifest_paths(root)):
                boundary = index
                break
            if within_roots(owner, layout(root).product_roots):
                from .contracts import read_model
                from .models import ProductIndex

                products = read_model(repo_path(root, layout(root).products), ProductIndex)
                if any(Path(entry.path).parent.as_posix() == owner for entry in products.products):
                    boundary = index
                    break
    if boundary is None or "restores" in parts[boundary + 1 :]:
        raise ValueError(
            "Artifacts must be under a direct repository/project/product build/; "
            "restored source is not an artifact read scope"
        )
    return path


def _bounds(offset: int, limit: int, maximum: int) -> None:
    if (
        isinstance(offset, bool)
        or isinstance(limit, bool)
        or offset < 0
        or not 1 <= limit <= maximum
    ):
        raise ValueError(f"Use offset >= 0 and a limit between 1 and {maximum}")


def _fingerprint(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _bytes(path: Path, maximum: int | None = None) -> tuple[bytes, os.stat_result]:
    """Read a stable regular file without following a final-component symlink."""
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("Select a regular file without symlinks")
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Select a regular file")
        if maximum is not None and before.st_size > maximum:
            raise ValueError(f"File exceeds the {maximum}-byte limit")
        data = stream.read() if maximum is None else stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        if _fingerprint(before) != _fingerprint(after):
            raise ValueError("File changed while reading; retry from fresh metadata")
        if maximum is not None and len(data) > maximum:
            raise ValueError(f"File exceeds the {maximum}-byte limit")
    return data, after


def read_regular_bytes(path: Path, maximum: int | None = None) -> tuple[bytes, os.stat_result]:
    """Expose the stable, bounded regular-file boundary to other review adapters."""
    return _bytes(path, maximum)


def _digest(path: Path) -> tuple[str, int]:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("Select a regular file without symlinks")
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Select a regular file")
        digest = hashlib.sha256()
        while block := stream.read(1024 * 1024):
            digest.update(block)
        after = os.fstat(stream.fileno())
        if _fingerprint(before) != _fingerprint(after):
            raise ValueError("File changed while reading; retry from fresh metadata")
    return digest.hexdigest(), after.st_size


def list_artifacts(
    root: Path, directory: str = "build", offset: int = 0, limit: int = 100
) -> McpArtifactList:
    """List one directory level with stable ordering and bounded response size."""
    _bounds(offset, limit, 100)
    base = artifact_path(root, directory)
    if not base.is_dir():
        raise ValueError("Artifact directory does not exist")
    children: list[Path] = []
    for child in base.iterdir():
        if child.name == "restores":
            continue
        if len(children) >= MAX_DIRECTORY_ENTRIES:
            raise ValueError("Artifact directory has too many entries; choose a narrower receipt")
        children.append(child)
    children.sort(key=lambda child: child.name)
    entries: list[McpArtifactEntry] = []
    for child in children[offset : offset + limit]:
        name = child.relative_to(root.resolve()).as_posix()
        safe = artifact_path(root, name)
        information = safe.stat()
        if stat.S_ISDIR(information.st_mode):
            entries.append(McpArtifactEntry(path=name, kind="directory"))
        elif stat.S_ISREG(information.st_mode):
            digest = _digest(safe)[0] if information.st_size <= MAX_EDIT_BYTES else None
            entries.append(
                McpArtifactEntry(
                    path=name, kind="file", size_bytes=information.st_size, sha256=digest
                )
            )
        else:
            raise ValueError(f"Artifact is not a regular file or directory: {name}")
    next_offset = offset + len(entries)
    more = next_offset < len(children)
    return McpArtifactList(
        directory=base.relative_to(root.resolve()).as_posix(),
        entries=tuple(entries),
        offset=offset,
        total_entries=len(children),
        truncated=more,
        next_offset=next_offset if more else None,
    )


def _content(root: Path, path: Path, offset: int, limit: int, permit_text: bool) -> McpFileContent:
    _bounds(offset, limit, MAX_CHUNK)
    relative = path.relative_to(root.resolve()).as_posix()
    size = path.stat().st_size
    if size > MAX_TEXT_BYTES or not permit_text:
        digest, size = _digest(path)
        return McpFileContent(
            path=relative,
            sha256=digest,
            size_bytes=size,
            content_kind="metadata_only",
            offset=offset,
            note="Content is not exposed for this file type or size; metadata only.",
        )
    data, _ = _bytes(path, MAX_TEXT_BYTES)
    digest = hashlib.sha256(data).hexdigest()
    try:
        text = data.decode("utf-8")
        if "\x00" in text:
            raise UnicodeError("Binary NUL character")
    except UnicodeError:
        return McpFileContent(
            path=relative,
            sha256=digest,
            size_bytes=len(data),
            content_kind="binary",
            offset=offset,
            note="Binary content is not embedded in MCP responses.",
        )
    next_offset = min(offset + limit, len(text))
    more = next_offset < len(text)
    return McpFileContent(
        path=relative,
        sha256=digest,
        size_bytes=len(data),
        content_kind="text",
        text=text[offset : offset + limit],
        offset=offset,
        total_characters=len(text),
        truncated=more,
        next_offset=next_offset if more else None,
    )


def read_artifact(root: Path, path: str, offset: int = 0, limit: int = MAX_CHUNK) -> McpFileContent:
    """Read a UTF-8 artifact chunk; unsupported/binary files return metadata only."""
    selected = artifact_path(root, path)
    return _content(
        root, selected, offset, limit, selected.suffix.lower() in ARTIFACT_TEXT_SUFFIXES
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
    return _content(root, project_file_path(root, project_id, path), offset, limit, True)


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
            data, _ = _bytes(sidecar, MAX_EDIT_BYTES)
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
    before, information = _bytes(selected, MAX_EDIT_BYTES)
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
        current_bytes, information = _bytes(current, MAX_EDIT_BYTES)
        if current_bytes != edit.before or _fingerprint(information) != _fingerprint(
            edit.information
        ):
            raise ValueError("Source changed before publication; edit was not applied")
        os.replace(temporary, current)
        verified, _ = _bytes(project_file_path(root, project_id, path), MAX_EDIT_BYTES)
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
