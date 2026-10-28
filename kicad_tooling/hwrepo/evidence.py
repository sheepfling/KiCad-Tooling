"""Bind retained evidence to observed committed source and verify its bytes."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from ..git import git_output, run_git_bytes, run_git_text
from .contracts import read_model, repo_path
from .models import (
    EvidenceFile,
    ScopedReleasePortableReport,
    SourceState,
    StaticPipelineReport,
    ValidationSummary,
)


def git(root: Path, *args: str) -> str:
    return git_output(root, *args)


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def source_state(root: Path) -> SourceState:
    """Local dirty checks remain useful, but cannot supply release evidence."""
    try:
        commit = git(root, "rev-parse", "HEAD")
        names = git(root, "ls-files", "-z").split("\0")
        files = {name: digest(repo_path(root, name)) for name in names if name}
        return SourceState(
            commit=commit,
            clean=(
                not git(root, "status", "--porcelain=v1", "--untracked-files=all")
                and files == committed_hashes(root, commit)
            ),
            files_sha256=files,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return SourceState()


def committed_hashes(root: Path, commit: str) -> dict[str, str]:
    """Compare against Git objects even when assume-unchanged hides local edits."""
    entries = run_git_text(root, "ls-tree", "-r", "--full-tree", "-z", commit).stdout.split("\0")
    objects: list[tuple[str, str]] = []
    for entry in entries:
        if not entry:
            continue
        metadata, name = entry.split("\t", 1)
        mode, kind, object_id = metadata.split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("Release source must contain regular files, not links or submodules")
        repo_path(root, name)
        objects.append((name, object_id))
    batch = run_git_bytes(
        root,
        "cat-file",
        "--batch",
        input_bytes="".join(f"{oid}\n" for _, oid in objects).encode(),
    )
    offset = 0
    hashes: dict[str, str] = {}
    for name, _ in objects:
        end = batch.stdout.index(b"\n", offset)
        size = int(batch.stdout[offset:end].split()[-1])
        start = end + 1
        hashes[name] = hashlib.sha256(batch.stdout[start : start + size]).hexdigest()
        offset = start + size + 1
    return hashes


def verify_source(observed: SourceState | None, expected: SourceState) -> None:
    if observed is None or not observed.clean or observed.commit is None:
        raise ValueError("Evidence was not produced from clean committed source")
    if observed != expected or not observed.files_sha256:
        raise ValueError("Evidence source commit or file hashes differ from the release source")


def evidence_path(root: Path, reference: EvidenceFile) -> Path:
    path = repo_path(root, reference.path)
    if digest(path) != reference.sha256:
        raise ValueError(f"Evidence hash differs: {reference.path}")
    return path


def verify_portable(
    root: Path, reference: EvidenceFile, source: SourceState
) -> StaticPipelineReport:
    report = read_model(evidence_path(root, reference), StaticPipelineReport)
    verify_source(report.source, source)
    gates = (
        report.registry,
        report.repository,
        report.documentation,
        report.product,
        report.generation,
        report.project_tests,
    )
    commands = (
        report.rumdl,
        report.mdrepo,
        report.ruff,
        report.pyright,
        report.unit_tests,
        *report.project_tests.commands.values(),
    )
    if (
        report.status != "PASS"
        or any(gate.status != "PASS" for gate in gates)
        or any(
            command.returncode != 0 or command.error is not None
            for command in commands
            if command is not None
        )
    ):
        raise ValueError("Portable report contains failed or missing checks")
    if any(
        (
            report.registry.issues,
            report.repository.issues,
            report.documentation.issues,
            report.product.issues,
            report.generation.issues,
        )
    ):
        raise ValueError("Portable report contains unresolved findings")
    return report


def verify_release_portable(
    root: Path,
    reference: EvidenceFile,
    source: SourceState,
    project_ids: tuple[str, ...],
) -> StaticPipelineReport | ScopedReleasePortableReport:
    """Preserve the evidence-service import path for portable release verification."""
    from .portable_evidence import verify_release_portable as verify

    return verify(root, reference, source, project_ids)


def verify_native(
    root: Path, reference: EvidenceFile, source: SourceState, project_id: str
) -> ValidationSummary:
    """Preserve the evidence-service import path for native evidence verification."""
    from .native_evidence import verify_native as verify

    return verify(root, reference, source, project_id)
