"""Explicit hosted setup of an exact simulator from a verified public source archive."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Protocol

from .models import CommandEvidence
from .spice import observed_versions

# Reviewed upstream archive pin already used by the template's electrical lane.
SOURCE_PINS = {"47": "894e649651f1838a14095e5a5439e7d3aa63e87ede14d283173fda4fcdef675f"}


class SetupLog(Protocol):
    def event(self, stage: str, status: str, **details: str | float) -> None: ...

    def run(self, stage: str, argv: tuple[str, ...], *, cwd: Path) -> Path: ...


def exact_executable(executable: str, version: str) -> str | None:
    path = shutil.which(executable)
    if path is None:
        return None
    try:
        process = subprocess.run(
            (path, "--version"), text=True, capture_output=True, check=False, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    command = CommandEvidence(
        argv=(path, "--version"),
        started_utc="setup-probe",
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )
    return (
        str(Path(path).resolve())
        if process.returncode == 0 and version in observed_versions(command)
        else None
    )


def unpack(archive: Path, destination: Path, version: str) -> Path:
    """Reject links and escaping members even after the archive hash was verified."""
    prefix = f"ngspice-{version}"
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        if len(members) > 50000 or sum(m.size for m in members) > 512 * 1024**2:
            raise ValueError("Simulator archive exceeds supported size")
        names: set[str] = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or path.parts[0] != prefix
                or "\\" in member.name
                or not (member.isfile() or member.isdir())
                or member.name in names
            ):
                raise ValueError(f"Unsafe simulator archive member: {member.name}")
            names.add(member.name)
        bundle.extractall(destination, members=members, filter="data")
    return destination / prefix


def ensure(
    root: Path,
    version: str,
    expected_sha256: str | None,
    log: SetupLog,
    executable: str = "ngspice",
) -> str:
    """Use the exact installed tool, or build in a fresh ignored directory with full logs."""
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", version) is None:
        raise ValueError("Review the exact ngspice version before hosted setup")
    installed = exact_executable(executable, version)
    if installed is not None:
        log.event("simulator", "PASS", executable=installed, version=version)
        return installed
    expected = expected_sha256 or SOURCE_PINS.get(version)
    if expected is None or re.fullmatch(r"[a-f0-9]{64}", expected) is None:
        raise ValueError(
            f"ngspice {version} is unavailable; install it or review ngspice_source_sha256"
        )
    missing = [name for name in ("make", "cc", "bison", "flex") if shutil.which(name) is None]
    if missing:
        raise ValueError(
            f"Simulator build prerequisites missing: {missing}; install build-essential, bison and flex"
        )
    parent = root / "build/ngspice-build"
    parent.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix=f"{version}-", dir=parent))
    archive = output / f"ngspice-{version}.tar.gz"
    url = f"https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/{version}/{archive.name}"
    log.event("simulator-download", "START", url=url, expected_sha256=expected)
    hasher = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(url, timeout=120) as response, archive.open("xb") as stream:
        if not response.url.startswith("https://"):
            raise ValueError("Simulator download redirected away from HTTPS")
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > 64 * 1024**2:
                raise ValueError("Simulator download exceeds supported size")
            hasher.update(chunk)
            stream.write(chunk)
    if hasher.hexdigest() != expected:
        raise ValueError("Simulator archive SHA-256 mismatch; no source was executed")
    log.event("simulator-download", "PASS", sha256=expected, archive=str(archive))
    source = unpack(archive, output, version)
    prefix = output / "installed"
    log.run(
        "simulator-configure",
        (
            str(source / "configure"),
            f"--prefix={prefix}",
            "--without-x",
            "--disable-debug",
            "--with-readline=no",
            "--disable-openmp",
        ),
        cwd=source,
    )
    log.run("simulator-make", ("make", "-j2"), cwd=source)
    log.run("simulator-install", ("make", "install"), cwd=source)
    installed = exact_executable(str(prefix / "bin/ngspice"), version)
    if installed is None:
        raise ValueError("Built simulator did not report the approved version")
    log.event("simulator", "PASS", executable=installed, version=version)
    return installed
