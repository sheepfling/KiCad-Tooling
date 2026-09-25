"""Create a new project island without inventing or copying an electrical design."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .contracts import read_model, repo_path, write_model
from .discovery import load_registry, settings
from .markdown import design_notes, project_readme, write_markdown
from .models import ProjectKind, ProjectManifest, ProjectScaffoldReport, ToolchainsCatalog


def prepare_manifest(root: Path, project_id: str, kind: ProjectKind, toolchain_id: str) -> ProjectManifest:
    """Validate identity, destination and toolchain before making any files."""
    template = read_model(repo_path(root, f"templates/{kind.domain_name}-project-config.example.json"), ProjectManifest)
    # Validate the identifier before substituting it into template paths.
    manifest = ProjectManifest.model_validate({**template.model_dump(), "id": project_id})
    manifest = ProjectManifest.model_validate_json(manifest.model_dump_json().replace(
        "REPLACE-WITH-PROJECT-ID", project_id))
    policy = settings(root)
    toolchains = read_model(repo_path(root, policy.catalogs.toolchains), ToolchainsCatalog)
    if toolchain_id not in {toolchain.id for toolchain in toolchains.toolchains}:
        raise ValueError(f"Unknown toolchain: {toolchain_id}")
    if manifest.id.casefold() in {project.id.casefold() for project in load_registry(root).projects}:
        raise ValueError(f"Project id already exists: {manifest.id}")
    destination = repo_path(root, f"projects/{manifest.id}")
    if destination.exists():
        raise ValueError(f"Project directory already exists: {destination}")
    if "projects" not in policy.project_roots:
        raise ValueError("Enable projects in catalog/projects.json project_roots first")
    return manifest.model_copy(update={"toolchain_id": toolchain_id})


def write_scaffold(root: Path, stage: Path, manifest: ProjectManifest) -> None:
    """Populate a caller-owned staging directory; publish only when fully prepared."""
    for folder in ("kicad", "docs", "tests"):
        (stage / folder).mkdir()
    write_model(stage / "project.json", manifest)
    shutil.copy2(repo_path(root, f"templates/project-tests/{manifest.kind.value}.json"), stage / "tests/contract.json")
    write_markdown(stage / "README.md", project_readme(manifest.id, manifest.kind))
    write_markdown(stage / "docs/README.md", design_notes())


def new_project(root: Path, project_id: str, kind: ProjectKind, toolchain_id: str) -> ProjectScaffoldReport:
    root = root.resolve()
    stage: Path | None = None
    try:
        manifest = prepare_manifest(root, project_id, kind, toolchain_id)
        destination = repo_path(root, f"projects/{manifest.id}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".new-project-", dir=destination.parent))
        write_scaffold(root, stage, manifest)
        os.replace(stage, destination)
        stage = None
        return ProjectScaffoldReport(
            status="PASS", directory=destination.relative_to(root).as_posix(),
            next_step=(
                "Create the native KiCad design and complete the test contract, then run "
                f"python -B -m kicad_tooling.verify --project {manifest.id}."
            ),
        )
    except (OSError, ValueError) as exc:
        return ProjectScaffoldReport(status="FAIL", directory=f"projects/{project_id}", issues=(str(exc),))
    finally:
        if stage is not None:
            shutil.rmtree(stage)
