"""Build distributions and prove the source archive reproduces its wheel."""

from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path

from kicad_tooling.package_assets import wheel_contents

Stage = Callable[..., subprocess.CompletedProcess[str]]


def only_artifact(directory: Path, pattern: str) -> Path:
    matches = tuple(directory.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {pattern} in {directory}")
    return matches[0]


def clear_distribution_build_cache(root: Path) -> None:
    """Remove setuptools staging trees so stale modules cannot leak into a wheel."""
    build_root = root / "build"
    paths = (build_root / "lib", *build_root.glob("bdist.*"), *build_root.glob("temp.*"))
    for path in paths:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def build_distributions(
    root: Path,
    output: Path,
    build_python: str,
    stage: Stage,
) -> tuple[Path, str]:
    """Prove a source archive reproduces its wheel without access to Git metadata."""
    clear_distribution_build_cache(root)
    wheels = output / "wheels"
    wheels.mkdir()
    stage(
        "wheel",
        (build_python, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(wheels), "."),
        output,
        cwd=root,
    )
    checkout_wheel = only_artifact(wheels, "kicad_team_tooling-*.whl")
    version, payload = wheel_contents(checkout_wheel)
    sdists = output / "sdists"
    sdists.mkdir()
    stage(
        "sdist",
        (build_python, "-m", "build", "--sdist", "--no-isolation", "--outdir", str(sdists), "."),
        output,
        cwd=root,
    )
    sdist = only_artifact(sdists, "kicad_team_tooling-*.tar.gz")
    rebuilt_dir = output / "rebuilt-wheels"
    rebuilt_dir.mkdir()
    with tempfile.TemporaryDirectory(prefix="kicad-tooling-sdist-") as temporary:
        extracted = Path(temporary)
        with tarfile.open(sdist) as archive:
            archive.extractall(extracted, filter="data")
        source = only_artifact(extracted, "kicad_team_tooling-*")
        if any(source.rglob(".git")) or any(
            (parent / ".git").exists() for parent in source.parents
        ):
            raise RuntimeError("Source rebuild must have no Git metadata or parent checkout")
        stage(
            "sdist-wheel",
            (
                build_python,
                "-m",
                "build",
                "--wheel",
                "--no-isolation",
                "--outdir",
                str(rebuilt_dir),
                ".",
            ),
            output,
            cwd=source,
        )
    rebuilt_wheel = only_artifact(rebuilt_dir, "kicad_team_tooling-*.whl")
    rebuilt_version, rebuilt_payload = wheel_contents(rebuilt_wheel)
    if (version, payload) != (rebuilt_version, rebuilt_payload):
        raise RuntimeError("Source distribution rebuild changed package metadata or payload")
    (output / "packaging.json").write_text(
        json.dumps(
            {
                "version": version,
                "source_distribution_version": rebuilt_version,
                "package_files": len(payload),
                "source_distribution_contains_git": False,
                "status": "PASS",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return rebuilt_wheel, version
