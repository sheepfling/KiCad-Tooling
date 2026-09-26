"""Prepare Linux dependency wheels on the host for the pip-free pinned KiCad image."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path, PurePosixPath

from .hwrepo.contracts import repo_path


def runtime_metadata() -> Path:
    """Locate the caller's installed distribution identity without private metadata APIs."""
    try:
        installed = distribution("kicad-team-tooling")
    except PackageNotFoundError as exc:
        raise ValueError("Install kicad-team-tooling before preparing its native runtime") from exc
    metadata = tuple(
        Path(str(installed.locate_file(entry))).parent.resolve()
        for entry in installed.files or ()
        if (entry.name == "METADATA" and entry.parent.name.endswith(".dist-info"))
        or (entry.name == "PKG-INFO" and entry.parent.name.endswith(".egg-info"))
    )
    if len(metadata) != 1 or not metadata[0].is_dir():
        raise ValueError("Installed kicad-team-tooling distribution metadata is incomplete")
    return metadata[0]


def copy_runtime(destination: Path, metadata: Path | None = None) -> None:
    """Copy exact executing package bytes, assets/profiles, and installed identity.

    The destination is the native virtual environment's actual site-packages.
    No consuming-project source directory is added to Python's import path.
    """
    metadata = runtime_metadata() if metadata is None else metadata
    shutil.copytree(
        Path(__file__).resolve().parent,
        destination / "kicad_tooling",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(metadata, destination / metadata.name)


def prepare(root: Path, image: str, output: Path) -> None:
    """Resolve wheels for the image's Python ABI, not the host's OS or Python."""
    root = root.resolve()
    destination = repo_path(root, output.as_posix())
    if len(output.parts) < 2 or output.parts[0] != "build":
        raise ValueError("Native dependencies belong in an ignored build/ directory")
    if destination.exists():
        raise ValueError(f"Dependency destination already exists: {output}")
    if re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", image) is None:
        raise ValueError("Native image must be digest-pinned")
    metadata = runtime_metadata()
    probe = subprocess.run(
        (
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--entrypoint",
            "python3",
            image,
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
        ),
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    version = probe.stdout.strip()
    parts = version.split(".")
    if len(parts) != 2 or not all(part.isdigit() for part in parts) or parts[0] != "3":
        raise ValueError(f"Unexpected container Python version: {version!r}")
    if int(parts[1]) < 11:
        raise ValueError(f"Native tooling requires Python >=3.11; image provides {version}")
    # The image has no pip, but stdlib venv supplies normal interpreter-owned
    # import paths. Inherit only the digest-pinned image's KiCad Python bindings.
    destination.parent.mkdir(parents=True, exist_ok=True)
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        import os

        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    environment_path = PurePosixPath("/work") / output.as_posix()
    create = subprocess.run(
        (
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            *user,
            "--entrypoint",
            "python3",
            "--mount",
            f"type=bind,source={root},target=/work",
            image,
            "-I",
            "-c",
            (
                "import subprocess,sys,venv; "
                "venv.EnvBuilder(with_pip=False, system_site_packages=True).create(sys.argv[1]); "
                "subprocess.run([sys.argv[1] + '/bin/python', '-I', '-c', "
                "\"import sysconfig; print(sysconfig.get_path('purelib'))\"], check=True)"
            ),
            str(environment_path),
        ),
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    native_site = PurePosixPath(create.stdout.strip())
    if (
        not native_site.is_absolute()
        or ".." in native_site.parts
        or not native_site.is_relative_to(environment_path)
        or native_site == environment_path
    ):
        raise ValueError(
            f"Native environment returned an invalid site-packages path: {native_site}"
        )
    site_packages = destination / native_site.relative_to(environment_path).as_posix()
    subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--target",
            str(site_packages),
            "--platform",
            "manylinux2014_x86_64",
            "--implementation",
            "cp",
            "--python-version",
            version,
            "--abi",
            "cp" + "".join(parts),
            "--only-binary=:all:",
            "pydantic==2.13.5",
            "snakemd==2.4.1",
        ),
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    copy_runtime(site_packages, metadata)


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
        if isinstance(exc, subprocess.CalledProcessError) and isinstance(exc.stderr, str):
            print(exc.stderr[-8000:], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
