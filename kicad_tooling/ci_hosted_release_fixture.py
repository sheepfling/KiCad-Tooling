"""Prepare the disposable public-template release fixture."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .hwrepo.repository import ephemeral, generated_artifact


def release_fixture(root: Path, target: Path) -> None:
    """Restore the public examples in a disposable default-layout repository.

    Live catalogs, design roots and adopter configuration are deliberately absent:
    release rehearsal exercises the retained public template fixtures, even after
    adoption has replaced the live catalog or moved private designs elsewhere.
    """
    root = root.resolve()
    if target.exists():
        raise ValueError(f"Release rehearsal output already exists: {target}")
    directories = ("docs", "templates", "examples", ".github")
    files = (
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        "CHANGELOG.md",
        ".gitignore",
        ".gitattributes",
        "pyproject.toml",
        "requirements-tooling.txt",
        "catalog/documentation-policy.json",
    )
    references = (
        "examples/catalog/projects.json",
        "examples/catalog/products.json",
        "examples/catalog/parts.json",
        "examples/catalog/interfaces.json",
        "examples/catalog/libraries.json",
        "examples/catalog/toolchains.json",
        "examples/catalog/team-policy.json",
        "examples/catalog/release-policies.json",
        "examples/projects/arduino-uno-status-led/project.json",
    )
    missing = [name for name in (*directories, *files, *references) if not (root / name).exists()]
    if missing:
        raise ValueError(
            "Release rehearsal requires retained public template fixtures; restore these "
            f"paths from the matching template version: {', '.join(missing)}"
        )

    def ignore_local(directory: str, names: list[str]) -> set[str]:
        ignored = {
            name
            for name in names
            if name == ".git"
            or ephemeral(name)
            or generated_artifact((Path(directory) / name).relative_to(root).as_posix())
        }
        for name in set(names) - ignored:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f"Public release fixture must not follow a symlink: {path}")
        return ignored

    # Validate before creating output, including links in directory ancestors.
    for name in (*directories, *files):
        source = root / name
        if any((root / part).is_symlink() for part in (Path(name), *Path(name).parents)):
            raise ValueError(f"Public release fixture must not follow a symlink: {source}")
        if source.is_dir():
            for directory, children, filenames in os.walk(source):
                ignored = ignore_local(directory, children + filenames)
                children[:] = [name for name in children if name not in ignored]

    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    for directory in directories:
        shutil.copytree(root / directory, target / directory, ignore=ignore_local)
    for name in files:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, destination)
    for directory in ("catalog", "projects", "products", "libraries", "generated", "schemas"):
        (target / directory).mkdir(exist_ok=True)
        readme = root / directory / "README.md"
        if not (root / directory).is_symlink() and readme.is_file() and not readme.is_symlink():
            shutil.copy2(readme, target / directory / "README.md")
    shutil.copytree(
        root / "examples/catalog", target / "catalog", dirs_exist_ok=True, ignore=ignore_local
    )
    shutil.copy2(
        Path(__file__).resolve().parent / "fixtures/scaffold-license.txt", target / "LICENSE"
    )
