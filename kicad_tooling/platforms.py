"""Shared host-platform probes for portable tooling behavior."""

from __future__ import annotations

import sys

_POSIX_PLATFORM_PREFIXES = (
    "aix",
    "cygwin",
    "darwin",
    "dragonfly",
    "freebsd",
    "linux",
    "netbsd",
    "openbsd",
    "sunos",
)


def is_windows_host() -> bool:
    """Return whether the current Python host uses Windows platform semantics."""
    return sys.platform == "win32"


def is_posix_host() -> bool:
    """Return whether the current Python host uses POSIX platform semantics."""
    return sys.platform.startswith(_POSIX_PLATFORM_PREFIXES)
