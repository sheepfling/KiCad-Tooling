"""Exercise the installed package against a relocated reference project."""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import JsonValue

from kicad_tooling.hwrepo.contracts import repo_path_is_within

StageRunner = Callable[..., subprocess.CompletedProcess[str]]


def adapted_project_fixture(project: Path, destination: Path) -> Path:
    """Copy a reference into a nested adopter layout without rewriting source.

    Only layout declarations change; native source and expectations stay byte-identical.
    """

    def copy_regular(source: str, target: str) -> str:
        if not stat.S_ISREG(Path(source).lstat().st_mode):
            raise ValueError(f"Cannot copy nonregular fixture input: {source}")
        return shutil.copy2(source, target)

    shutil.copytree(
        project,
        destination,
        symlinks=True,
        copy_function=copy_regular,
        ignore=shutil.ignore_patterns(
            "build", ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"
        ),
    )

    def fixture_path(value: str) -> Path:
        path = destination
        for component in Path(value).parts:
            path /= component
            if path.is_symlink():
                raise ValueError(f"Cannot relocate or rewrite a linked fixture path: {value}")
        return path

    moves = (
        ("examples/projects", "engineering/reference"),
        ("projects", "designs"),
        ("catalog", "policy"),
    )
    for previous, current in moves:
        source, target = fixture_path(previous), fixture_path(current)
        if source.is_symlink() or (source.exists() and not source.is_dir()):
            raise ValueError(f"Fixture source tree must be an ordinary directory: {previous}")
        if target.exists() or target.is_symlink():
            raise ValueError(f"Fixture relocation target already exists: {current}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            source.rename(target)
        else:
            target.mkdir()

    def relocated(value: str) -> str:
        for previous, current in moves:
            if repo_path_is_within(value, previous, include_directory=True):
                return current + value[len(previous) :]
        return value

    def save(path: Path, document: JsonValue) -> None:
        path = fixture_path(path.relative_to(destination).as_posix())
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    discovery_path = fixture_path("policy/projects.json")
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    discovery["catalogs"] = {key: relocated(value) for key, value in discovery["catalogs"].items()}
    discovery["project_roots"] = ["engineering", "designs"]
    discovery["project_depth"] = 2
    save(discovery_path, discovery)
    contract_path = fixture_path("templates/template-contract.json")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["required_paths"] = [relocated(value) for value in contract["required_paths"]]
    save(contract_path, contract)
    for directory in ("engineering/reference", "designs"):
        for path in sorted(fixture_path(directory).glob("*/project.json")):
            if path.is_symlink() or path.parent.is_symlink():
                raise ValueError(f"Fixture manifest cannot be linked: {path}")
            manifest = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for field in ("shared_source_roots", "shared_inputs"):
                if field in manifest:
                    original = manifest[field]
                    replacement = [relocated(value) for value in original]
                    if replacement != original:
                        manifest[field] = replacement
                        changed = True
            if changed:
                save(path, manifest)
    fixture_path("kicad-tooling.toml").write_text(
        '[layout]\ndiscovery = "policy/projects.json"\n'
        'products = "policy/products.json"\nteam_policy = "policy/team-policy.json"\n'
        'new_project_root = "designs"\n',
        encoding="utf-8",
    )
    return destination


def verify_adapted_project(
    project: Path,
    command: Path,
    output: Path,
    environment: Mapping[str, str],
    run_stage: StageRunner,
) -> None:
    """Exercise the installed wheel against the adapted checkout from an outside cwd."""
    adapted = adapted_project_fixture(project, output / "adapted-project")
    # A separate index makes the portable hygiene gate inspect this fixture's files,
    # rather than accidentally finding the tooling checkout's parent Git repository.
    run_stage("adapted-git-init", ("git", "init", str(adapted)), output, cwd=output)
    run_stage("adapted-git-index", ("git", "-C", str(adapted), "add", "--all"), output, cwd=output)
    result = run_stage(
        "adapted-inventory",
        (str(command), "template", "list", "--root", str(adapted), "--format", "json"),
        output,
        cwd=output,
        environment=environment,
    )
    inventory = json.loads(result.stdout)
    controllers = [item for item in inventory["projects"] if item["id"] == "controller"]
    if (
        inventory["status"] != "PASS"
        or len(controllers) != 1
        or controllers[0]["manifest"] != "engineering/reference/controller/project.json"
    ):
        raise RuntimeError("Adapted inventory did not discover the relocated controller")
    result = run_stage(
        "adapted-surface",
        (str(command), "surface", "--root", str(adapted), "--format", "json"),
        output,
        cwd=output,
        environment=environment,
    )
    if json.loads(result.stdout)["status"] != "PASS":
        raise RuntimeError("Adapted CLI/MCP declaration parity did not pass")
    result = run_stage(
        "adapted-verify",
        (
            str(command),
            "verify",
            "--root",
            str(adapted),
            "--project",
            "controller",
            "--format",
            "json",
        ),
        output,
        cwd=output,
        environment=environment,
    )
    report = json.loads(result.stdout)
    if report["status"] != "PASS" or report["depth"] != "portable":
        raise RuntimeError("Adapted project portable verification did not pass")
    if report["build_authorized"] is not False:
        raise RuntimeError("Adapted project verification must not authorize a build")
