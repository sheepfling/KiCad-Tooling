"""Prepare Linux dependency wheels on the host for the pip-free pinned KiCad image."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from .hwrepo.contracts import repo_path


def prepare(root: Path, image: str, output: Path) -> None:
    """Resolve wheels for the image's Python ABI, not the host's OS or Python."""
    root = root.resolve()
    destination = repo_path(root, output.as_posix())
    if output.parts[0] != "build":
        raise ValueError("Native dependencies belong in an ignored build/ directory")
    if destination.exists():
        raise ValueError(f"Dependency destination already exists: {output}")
    if "@sha256:" not in image:
        raise ValueError("Native image must be digest-pinned")
    probe = subprocess.run(
        ("docker", "run", "--rm", "--platform", "linux/amd64", "--entrypoint", "python3", image,
         "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"),
        check=True, capture_output=True, text=True, timeout=120,
    )
    version = probe.stdout.strip()
    parts = version.split(".")
    if len(parts) != 2 or not all(part.isdigit() for part in parts) or parts[0] != "3":
        raise ValueError(f"Unexpected container Python version: {version!r}")
    subprocess.run(
        (sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
         "--target", str(destination), "--platform", "manylinux2014_x86_64",
         "--implementation", "cp", "--python-version", version, "--abi", "cp" + "".join(parts),
         "--only-binary=:all:", "pydantic==2.13.5", "snakemd==2.4.1"),
        check=True, timeout=300,
    )
    # The KiCad image has Python but no pip. The host package is pure Python;
    # copy that exact checked-out/installed source alongside ABI-matched wheels.
    shutil.copytree(Path(__file__).resolve().parent, destination / "kicad_tooling",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, default=Path("build/policy-deps"))
    args = parser.parse_args()
    try:
        prepare(args.root, args.image, args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Native dependency preparation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
