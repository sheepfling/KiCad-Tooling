"""Bounded, stable file reads shared by source and artifact services."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from .artifact_access import file_fingerprint, read_regular_bytes
from .file_access_models import McpFileContent

MAX_CHUNK = 20_000
MAX_TEXT_BYTES = 10 * 1024 * 1024


def validate_bounds(offset: int | bool, limit: int | bool, maximum: int) -> None:
    if (
        isinstance(offset, bool)
        or isinstance(limit, bool)
        or offset < 0
        or not 1 <= limit <= maximum
    ):
        raise ValueError(f"Use offset >= 0 and a limit between 1 and {maximum}")


def file_digest(path: Path) -> tuple[str, int]:
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
        if file_fingerprint(before) != file_fingerprint(after):
            raise ValueError("File changed while reading; retry from fresh metadata")
    return digest.hexdigest(), after.st_size


def read_file_content(
    root: Path, path: Path, offset: int, limit: int, permit_text: bool
) -> McpFileContent:
    validate_bounds(offset, limit, MAX_CHUNK)
    relative = path.relative_to(root.resolve()).as_posix()
    size = path.stat().st_size
    if size > MAX_TEXT_BYTES or not permit_text:
        digest, size = file_digest(path)
        return McpFileContent(
            path=relative,
            sha256=digest,
            size_bytes=size,
            content_kind="metadata_only",
            offset=offset,
            note="Content is not exposed for this file type or size; metadata only.",
        )
    data, _ = read_regular_bytes(path, MAX_TEXT_BYTES)
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
