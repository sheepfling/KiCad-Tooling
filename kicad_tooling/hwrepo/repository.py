"""Portable CAD dependencies, project discovery, and tracked-state hygiene."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath

from .contracts import repo_path
from .discovery import load_config, load_registry, settings
from .models import RepositoryPolicyReport

LOCAL_STATE_NAMES = frozenset(
    {
        ".directory",
        ".ds_store",
        ".lsoverride",
        "desktop.ini",
        "ehthumbs.db",
        "fp-info-cache",
        "thumbs.db",
        ".coverage",
    }
)
LOCAL_STATE_DIRECTORIES = frozenset(
    {
        ".appledouble",
        ".evidence",
        ".fseventsd",
        ".history",
        ".idea",
        ".pytest_cache",
        ".ruff_cache",
        ".spotlight-v100",
        ".trashes",
        ".vscode",
        ".vs",
        ".venv",
        "venv",
        "dist",
        "htmlcov",
        "$recycle.bin",
        "__macosx",
        "__pycache__",
        "build",
        "lost+found",
    }
)
LOCAL_STATE_SUFFIXES = frozenset(
    {
        ".bak",
        ".kicad_prl",
        ".lck",
        ".log",
        ".old",
        ".orig",
        ".pid",
        ".pyc",
        ".rej",
        ".swo",
        ".swp",
        ".temp",
        ".tmp",
    }
)
UNMANAGED_ARTIFACT_SUFFIXES = frozenset(
    {
        ".7z",
        ".aac",
        ".aif",
        ".aiff",
        ".apk",
        ".app",
        ".appx",
        ".avi",
        ".avif",
        ".bmp",
        ".bz2",
        ".bundle",
        ".doc",
        ".docm",
        ".docx",
        ".dot",
        ".dotm",
        ".dotx",
        ".dmg",
        ".deb",
        ".eml",
        ".exe",
        ".flac",
        ".gif",
        ".gz",
        ".heic",
        ".ico",
        ".iso",
        ".jpeg",
        ".jpg",
        ".key",
        ".m4a",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp3",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".msg",
        ".msi",
        ".msix",
        ".numbers",
        ".odg",
        ".odp",
        ".ods",
        ".odt",
        ".ogg",
        ".ogv",
        ".one",
        ".opus",
        ".pages",
        ".pkg",
        ".pot",
        ".potm",
        ".potx",
        ".png",
        ".pps",
        ".ppsm",
        ".ppsx",
        ".ppt",
        ".pptm",
        ".pptx",
        ".psd",
        ".rar",
        ".rpm",
        ".svg",
        ".tar",
        ".tgz",
        ".tif",
        ".tiff",
        ".wav",
        ".webm",
        ".webp",
        ".wmv",
        ".xls",
        ".xlsm",
        ".xlsx",
        ".xlt",
        ".xltm",
        ".xltx",
        ".xz",
        ".zip",
        ".zst",
    }
)


def ephemeral(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        path.suffix.casefold() in LOCAL_STATE_SUFFIXES
        or path.name.casefold() in LOCAL_STATE_NAMES
        or path.name.startswith(("._", ".nfs", "_autosave-", "~"))
        or path.name.startswith(".coverage.")
        or path.name.endswith("-bak")
        or any(
            part.casefold() in LOCAL_STATE_DIRECTORIES
            or part.casefold().endswith("-backups")
            or part.casefold().endswith(".egg-info")
            or part.casefold().startswith(".trash-")
            for part in path.parts
        )
    )


def generated_artifact(name: str) -> bool:
    """Classify output locations and unambiguous native manufacturing exports."""
    path = PurePosixPath(name)
    return (
        (bool(path.parts) and path.parts[0].casefold() in {"generated", "schemas"}
         and name not in {"generated/README.md", "schemas/README.md"})
        or path.suffix.casefold() in {".gbr", ".gbrjob", ".ger", ".drl", ".pos", ".net"}
    )


def unmanaged_artifact(name: str) -> bool:
    """Return whether a force-added Office, archive, installer or media file is forbidden."""
    path = PurePosixPath(name)
    # Authored documentation figures are source. CAD exports belong in build/.
    if path.suffix.casefold() in {".png", ".svg", ".jpg", ".jpeg", ".webp", ".gif"} and any(
        pair == ("docs", "assets") for pair in zip(path.parts, path.parts[1:])
    ):
        return False
    return path.suffix.casefold() in UNMANAGED_ARTIFACT_SUFFIXES


def cad_dependencies(
    root: Path, file: Path, project_dir: Path, major: str,
    inventoried_inputs: frozenset[str],
    source_roots: frozenset[str],
    exposed_inputs: frozenset[str] | None = None,
) -> list[str]:
    issues: list[str] = []
    text = file.read_text(encoding="utf-8")
    embedded = set(re.findall(
        r'\(file\s+\(name\s+"([^"\n]+)"\)\s+\(type\s+model\)\s+'
        r'\(data\s+\|[A-Za-z0-9+/=\s]+\|\s*\)\s+\(checksum\s+"[A-Fa-f0-9]+"\)\s*\)', text))
    previous_match = 0
    line = 1
    for match in re.finditer(r'\((?:uri|model)\s+"([^"\n]*)"', text):
        value = match.group(1)
        line += text.count("\n", previous_match, match.start())
        previous_match = match.start()
        label = f"{file.relative_to(root).as_posix()}:{line}"
        if value.startswith("kicad-embed://"):
            # The containing native file is itself inventoried and hashed. Check
            # record presence here; native KiCad owns decoding the embedded bytes.
            if value.removeprefix("kicad-embed://") not in embedded:
                issues.append(f"CAD_PATH: {label}: missing embedded model {value!r}")
            continue
        if "\\" in value or PureWindowsPath(value).drive or value.startswith("/"):
            issues.append(f"CAD_PATH: {label}: machine-local dependency {value!r}")
            continue
        allowed = {f"KICAD{major}_SYMBOL_DIR", f"KICAD{major}_FOOTPRINT_DIR", f"KICAD{major}_3DMODEL_DIR"}
        variables = re.findall(r'\$\{([^}]+)\}', value)
        if variables and variables[0] in allowed and len(variables) == 1:
            if not value.startswith("${" + variables[0] + "}/") or ".." in value.split("/"):
                issues.append(f"CAD_PATH: {label}: invalid versioned KiCad library path")
            continue  # Bundled library dependency resolved by the pinned KiCad lane.
        if any(variable != "KIPRJMOD" for variable in variables) or "$" in value.replace("${KIPRJMOD}", ""):
            issues.append(f"CAD_PATH: {label}: undocumented path variable {value!r}")
            continue
        target = Path(value.replace("${KIPRJMOD}", project_dir.as_posix()))
        if not target.is_absolute():
            target = project_dir / target
        try:
            # Collapse relative .. only after anchoring at the project directory.
            normalized = Path(os.path.abspath(target))
            relative = normalized.relative_to(root).as_posix()
            dependency = repo_path(root, relative)
            if not dependency.exists():
                raise ValueError("missing dependency")
            if dependency.is_file() and relative not in inventoried_inputs:
                raise ValueError("dependency is not in this project's required_inputs")
            if dependency.is_dir():
                if not any(
                    relative == source or relative.startswith(f"{source}/")
                    for source in source_roots
                ):
                    raise ValueError("library directory is outside this project's source_roots")
                exposed = (
                    {
                        child.relative_to(root).as_posix()
                        for child in dependency.rglob("*")
                        if child.is_file() and child.suffix != ".kicad_prl"
                        and child.name != "fp-info-cache"
                    }
                    if exposed_inputs is None else {
                        name for name in exposed_inputs if name.startswith(f"{relative}/")
                    }
                )
                if not exposed:
                    raise ValueError("library directory has no inventoried inputs for this project")
                if unlisted := exposed - inventoried_inputs:
                    raise ValueError(f"library directory exposes unlisted files: {sorted(unlisted)}")
        except ValueError as exc:
            issues.append(f"CAD_PATH: {label}: {value!r}: {exc}")
    return issues


def check_repository(
    root: Path, selected_project_ids: tuple[str, ...] | None = None
) -> RepositoryPolicyReport:
    """Check shared hygiene plus CAD dependencies for all or selected projects."""
    root = root.resolve()
    selected = None if selected_project_ids is None else frozenset(selected_project_ids)
    issues: list[str] = []
    try:
        registry = load_registry(root)
        inventories: set[str] = set()
        selected_roots: set[Path] = set()
        available_ids = {project.id for project in registry.projects}
        if selected is not None and (unknown := selected - available_ids):
            issues.append(f"PROJECT_SELECTION: unknown project IDs: {sorted(unknown)}")
        for project in registry.projects:
            if selected is not None and project.id not in selected:
                continue
            config = load_config(root, project.config)
            directory = repo_path(root, project.project).parent
            selected_roots.add(repo_path(root, project.config).parent)
            inventories.update(config.required_inputs)
            inventoried_inputs = frozenset(config.required_inputs)
            source_roots = frozenset(config.source_roots)
            for name in config.required_inputs:
                path = repo_path(root, name)
                if path.suffix in {".kicad_pcb", ".kicad_mod"} or path.name in {"sym-lib-table", "fp-lib-table"}:
                    issues.extend(
                        cad_dependencies(
                            root,
                            path,
                            directory,
                            config.kicad_version.split(".")[0],
                            inventoried_inputs,
                            source_roots,
                        )
                    )
        scan_roots = (
            tuple(root / directory for directory in settings(root).project_roots)
            if selected is None else tuple(selected_roots)
        )
        found = {
            path.relative_to(root).as_posix()
            for directory in scan_roots
            if directory.is_dir()
            for path in directory.rglob("*")
            if path.suffix in {".kicad_pro", ".kicad_sch", ".kicad_pcb"}
            and not ephemeral(path.relative_to(root).as_posix())
        }
        issues.extend(f"UNREGISTERED_DESIGN: {name}" for name in sorted(found - inventories))
        result = subprocess.run(["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True, check=True)
        for name in result.stdout.split("\0"):
            if name and generated_artifact(name) and (root / name).exists():
                # A working-tree deletion is the intended fix; CI checks the committed tree.
                issues.append(f"TRACKED_GENERATED_OUTPUT: {name}")
            elif name and ephemeral(name):
                issues.append(f"TRACKED_LOCAL_STATE: {name}")
            elif name and unmanaged_artifact(name):
                issues.append(f"TRACKED_UNMANAGED_ARTIFACT: {name}")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        issues.append(f"REPOSITORY_LOAD: {exc}")
    return RepositoryPolicyReport(
        status="FAIL" if issues else "PASS",
        issues=tuple(sorted(set(issues))),
    )
