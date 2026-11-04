"""CLI and compatibility adapters for pinned native dependency preparation."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .hwrepo import native_dependencies as _native_dependencies
from .hwrepo.layout import default_project_root
from .hwrepo.native_dependency_models import NativeDependencyPreparationRequest

__all__ = ("copy_runtime", "prepare", "runtime_metadata")


def runtime_metadata() -> Path:
    """Compatibility export for the installed-runtime metadata lookup."""
    return _native_dependencies.runtime_metadata()


def copy_runtime(destination: Path, metadata: Path | None = None) -> None:
    """Compatibility export for copying the installed tooling runtime."""
    _native_dependencies.copy_runtime(destination, metadata)


def prepare(root: Path, image: str, output: Path) -> None:
    """Compatibility adapter for callers using the original positional API."""
    _native_dependencies.prepare_native_dependencies(
        NativeDependencyPreparationRequest(root=root, image=image, output=output)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, default=Path("build/policy-deps"))
    args = parser.parse_args()
    try:
        prepare(args.root, args.image, args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Native dependency preparation failed: {exc}", file=sys.stderr)
        caught_error: (
            OSError | ValueError | subprocess.SubprocessError | subprocess.CalledProcessError
        ) = exc
        if isinstance(caught_error, subprocess.CalledProcessError):
            stderr: str | bytes | None = caught_error.stderr
            if isinstance(stderr, str):
                print(stderr[-8000:], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
