"""Package verified releases and restore source plus evidence in an isolated checkout."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .contracts import read_model, repo_path, write_model
from .evidence import digest, git
from .models import ReleaseManifest, ReleasePackageIndex, ReleasePackageReport
from .release import check
from .releasing import retained_paths


def package(root: Path, manifest_name: str, output: Path) -> ReleasePackageReport:
    root = root.resolve()
    manifest_path = repo_path(root, manifest_name)
    manifest = read_model(manifest_path, ReleaseManifest)
    result = check(root, manifest)
    if result.status != "PASS":
        raise ValueError(f"Release is not ready: {result.issues}")
    output = output.absolute()
    if output.exists():
        raise ValueError("Refusing to replace an existing release package")
    if output.is_relative_to(root) and not output.is_relative_to(root / "build"):
        raise ValueError("In-repository release packages belong under build/")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kicad-package-") as temporary:
        staging = Path(temporary)
        refs = ("HEAD",) if manifest.source_tag is None else ("HEAD", f"refs/tags/{manifest.source_tag}")
        git(root, "bundle", "create", str(staging / "source.bundle"), *refs)
        files = {"source.bundle": staging / "source.bundle"}
        for name in retained_paths(root, manifest) | {manifest_name}:
            # .git is exclusively owned by restore's Git clone, never by payload files.
            if any(part.casefold() == ".git" for part in Path(name).parts):
                raise ValueError("Release payload may not contain .git")
            files[f"payload/{name}"] = repo_path(root, name)
        index = ReleasePackageIndex(source_commit=manifest.source_commit, manifest=manifest_name,
                                    files_sha256={name: digest(path) for name, path in sorted(files.items())})
        write_model(staging / "package.json", index)
        temporary_archive = staging / "release.zip"
        with zipfile.ZipFile(temporary_archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(staging / "package.json", "package.json")
            for name, path in sorted(files.items()):
                archive.write(path, name)
        # A package is not complete until source and evidence can actually be restored.
        restore(temporary_archive, staging / "restore-test")
        with output.open("xb") as stream, temporary_archive.open("rb") as incoming:
            shutil.copyfileobj(incoming, stream)
    return ReleasePackageReport(status="PASS", source_commit=manifest.source_commit,
                                package=str(output), package_sha256=digest(output),
                                manifest=manifest_name)


def restore(archive_path: Path, destination: Path) -> ReleasePackageReport:
    """Validate every member before copying; refuse overwrites and unsafe ZIP paths."""
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Restore destination already exists")
    if not destination.parent.is_dir():
        raise ValueError("Restore parent directory does not exist")
    with tempfile.TemporaryDirectory(prefix="kicad-restore-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        unpacked = staging / "unpacked"
        unpacked.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len({name.casefold() for name in names}) != len(names):
                raise ValueError("Duplicate or case-conflicting ZIP members")
            if len(names) > 100000 or sum(member.file_size for member in members) > 4 * 1024**3:
                raise ValueError("Release archive exceeds supported restore limits")
            for member in members:
                mode = member.external_attr >> 16
                if member.is_dir() or mode & 0o170000 not in {0, 0o100000}:
                    raise ValueError("Only regular files are allowed in release packages")
                path = repo_path(unpacked, member.filename)
                if any(part.casefold() == ".git" for part in Path(member.filename).parts):
                    raise ValueError("Release payload may not contain .git")
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream, archive.open(member) as incoming:
                    shutil.copyfileobj(incoming, stream)
        index = read_model(unpacked / "package.json", ReleasePackageIndex)
        if set(names) != set(index.files_sha256) | {"package.json"}:
            raise ValueError("Release archive inventory differs from its index")
        if "source.bundle" not in index.files_sha256 or any(
            name != "source.bundle" and not name.startswith("payload/") for name in index.files_sha256
        ):
            raise ValueError("Release archive has unexpected members")
        for name, expected in index.files_sha256.items():
            if digest(repo_path(unpacked, name)) != expected:
                raise ValueError(f"Release archive hash differs: {name}")
        checkout = staging / "checkout"
        # Disable machine-specific checkout filters and hooks; this restores data only.
        environment = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        for command in (
            ("git", "-c", f"core.hooksPath={os.devnull}", "clone", "--no-checkout", "--", str(unpacked / "source.bundle"), str(checkout)),
            ("git", "-C", str(checkout), "-c", "core.autocrlf=false", "-c", f"core.hooksPath={os.devnull}", "checkout", "--detach", index.source_commit),
        ):
            subprocess.run(command, env=environment, text=True, capture_output=True, check=True, timeout=120)
        for name in index.files_sha256:
            if name.startswith("payload/"):
                target = repo_path(checkout, name.removeprefix("payload/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                incoming = repo_path(unpacked, name)
                if target.exists() and digest(target) != digest(incoming):
                    raise ValueError("Release payload attempts to change restored source")
                shutil.copy2(incoming, target)
        manifest = read_model(repo_path(checkout, index.manifest), ReleaseManifest)
        if manifest.source_commit != index.source_commit:
            raise ValueError("Package and manifest source commits differ")
        result = check(checkout, manifest)
        if result.status != "PASS":
            raise ValueError(f"Restored release verification failed: {result.issues}")
        git(checkout, "remote", "remove", "origin")
        os.replace(checkout, destination)
    return ReleasePackageReport(status="PASS", source_commit=index.source_commit,
                                package=str(archive_path), package_sha256=digest(archive_path),
                                manifest=index.manifest)


def verify(archive_path: Path) -> ReleasePackageReport:
    with tempfile.TemporaryDirectory(prefix="kicad-verify-package-") as temporary:
        return restore(archive_path, Path(temporary) / "checkout")
