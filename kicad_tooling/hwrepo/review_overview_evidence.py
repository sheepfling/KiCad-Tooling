"""Safe generated-receipt reads and hash comparisons for project overviews."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .artifact_access import artifact_path, file_fingerprint, read_regular_bytes
from .contracts import parse_model_text, repo_path
from .evidence import digest
from .project_models import ProjectConfig
from .review_overview_models import OverviewLink

Model = TypeVar("Model", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ReviewContext:
    root: Path
    project_id: str
    config: ProjectConfig
    source_hashes: Mapping[str, str]


def selected_receipt(root: Path, requested: Path, filename: str) -> Path:
    """Keep even absent selections inside a configured generated build tree."""
    try:
        relative = requested.relative_to(root) if requested.is_absolute() else requested
    except ValueError as exc:
        raise ValueError("Select receipts inside this project checkout") from exc
    selected = artifact_path(root, relative.as_posix())
    if selected.name != filename and not selected.is_file() and selected.suffix != ".json":
        selected = artifact_path(root, (relative / filename).as_posix())
    return selected


def read_receipt(path: Path, model: type[Model]) -> tuple[Model, str]:
    content, _ = read_regular_bytes(path, maximum=16 * 1024 * 1024)
    return parse_model_text(content.decode("utf-8"), model), hashlib.sha256(content).hexdigest()


def recorded_directory(root: Path, value: str, expected: Path) -> bool:
    """Accept a saved absolute or repository-relative directory only at the selected location."""
    path = Path(value)
    try:
        relative = path.relative_to(root) if path.is_absolute() else path
        return artifact_path(root, relative.as_posix()) == expected
    except ValueError:
        return False


def source_mismatch(
    context: ReviewContext, expected: Mapping[str, str], *, exact_scope: bool
) -> str | None:
    """Return a concrete mismatch, or None when every declared byte still matches."""
    if exact_scope and dict(expected) != dict(context.source_hashes):
        return "Declared source inventory differs from the current project source."
    for name, recorded in expected.items():
        try:
            current = context.source_hashes.get(name)
            if current is None:
                path = repo_path(context.root, name)
                current = digest(path) if path.is_file() else None
            if current != recorded:
                return f"Source or input changed or is missing: {name}"
        except (OSError, ValueError):
            return f"Source or input is unavailable: {name}"
    return None


def checked_artifact_digest(root: Path, path: Path) -> str | None:
    """Hash a stable regular generated file without following symlinks."""
    try:
        relative = path.relative_to(root).as_posix()
        selected = artifact_path(root, relative)
        if not stat.S_ISREG(selected.lstat().st_mode):
            return None
        descriptor = os.open(
            selected,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                return None
            checksum = hashlib.sha256()
            for chunk in iter(lambda: stream.read(65536), b""):
                checksum.update(chunk)
            after = os.fstat(stream.fileno())
            if file_fingerprint(before) != file_fingerprint(after) or file_fingerprint(
                after
            ) != file_fingerprint(os.stat(selected, follow_symlinks=False)):
                return None
            return checksum.hexdigest()
    except (OSError, ValueError):
        return None


def checked_link(
    context: ReviewContext,
    path: Path,
    label: str,
    expected: str | None = None,
) -> OverviewLink | None:
    """Link only stable local files, matching the receipt hash when one exists."""
    actual = checked_artifact_digest(context.root, path)
    if actual is None or expected is not None and actual != expected:
        return None
    try:
        return OverviewLink(
            label=label,
            path=path.relative_to(context.root).as_posix(),
            sha256=actual,
            receipt_bound=expected is not None,
        )
    except ValueError:
        return None


def artifact_issues(
    context: ReviewContext, directory: Path, recorded: Mapping[str, str]
) -> tuple[str, ...]:
    """Verify every file named by a saved receipt, including non-displayed outputs."""
    issues: list[str] = []
    if len(recorded) > 2000:
        return ("Receipt lists more than 2000 artifacts; inventory was not verified.",)
    for name, expected in sorted(recorded.items()):
        try:
            path = repo_path(directory, name)
            link = checked_link(context, path, name, expected)
        except ValueError:
            link = None
        if link is None:
            issues.append(f"Recorded artifact changed or is missing: {name}")
    return tuple(issues)


def dependency_issue(context: ReviewContext, value: str, expected: str) -> str | None:
    """Verify one referenced source receipt without scanning for replacement runs."""
    try:
        selected = selected_receipt(context.root, Path(value), Path(value).name)
        if checked_link(context, selected, selected.name, expected) is None:
            return f"Referenced receipt changed or is missing: {value}"
    except ValueError:
        return f"Referenced receipt is outside the selected checkout: {value}"
    return None
