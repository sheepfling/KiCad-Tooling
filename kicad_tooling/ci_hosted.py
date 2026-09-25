"""Hosted CI orchestration with the same selection and checks available locally.

GitHub Actions owns runner allocation, job dependencies and artifact uploads. This
module owns decisions and commands, recording each stage under ignored build/.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import time
from datetime import UTC, datetime
from pathlib import Path

from .ci_matrix import build_matrix
from .hwrepo.contracts import read_model, write_model
from .hwrepo.models import (
    ForeignPcbReport,
    ImpactPlan,
    ProjectImportReport,
    ProjectKind,
    ProjectManifest,
)
from .hwrepo.repository import ephemeral, generated_artifact
from .impact import build_plan


class HostedLog:
    """Small append-only stage journal that survives a failed hosted command."""

    def __init__(self, root: Path, lane: str) -> None:
        self.directory = root / "build/ci-hosted" / lane
        self.directory.mkdir(parents=True, exist_ok=True)
        self.events = self.directory / "events.jsonl"
        self.event("lane", "START")

    def event(self, stage: str, status: str, **details: str | float) -> None:
        entry: dict[str, str | float | int] = {
            "time_utc": datetime.now(UTC).isoformat(), "stage": stage, "status": status,
            **details,
        }
        with self.events.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, sort_keys=True) + "\n")
        suffix = " " + " ".join(f"{key}={value}" for key, value in details.items()) if details else ""
        print(f"hosted-ci: {stage} {status.lower()}{suffix}", file=sys.stderr, flush=True)

    def run(self, stage: str, argv: tuple[str, ...], *, cwd: Path,
            stdout_path: Path | None = None, env: dict[str, str] | None = None,
            merge_stderr: bool = False) -> Path:
        """Retain stdout and stderr separately; stream progress to the Actions log."""
        output = stdout_path or self.directory / f"{stage}.stdout.log"
        error = self.directory / f"{stage}.stderr.log"
        output.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        self.event(stage, "START", command=" ".join(argv))
        try:
            with output.open("w", encoding="utf-8") as stdout, error.open(
                "w", encoding="utf-8"
            ) as stderr:
                process = subprocess.Popen(
                    argv, cwd=cwd, stdout=stdout, stderr=subprocess.PIPE,
                    text=True, env=env,
                )
                assert process.stderr is not None
                for line in process.stderr:
                    stderr.write(line)
                    stderr.flush()
                    if merge_stderr:
                        stdout.write(line)
                        stdout.flush()
                    sys.stderr.write(line)
                    sys.stderr.flush()
                process.stderr.close()
                code = process.wait()
        except OSError as exc:
            self.event(stage, "ERROR", elapsed_seconds=round(time.monotonic() - started, 3),
                       error=str(exc))
            raise
        self.event(stage, "PASS" if code == 0 else "FAIL",
                   elapsed_seconds=round(time.monotonic() - started, 3), exit_code=code)
        if code:
            tail = output.read_text(encoding="utf-8", errors="replace")[-4000:].strip()
            if tail:
                print(f"hosted-ci: {stage} stdout tail:\n{tail}", file=sys.stderr)
            raise RuntimeError(f"{stage} failed ({code}); inspect {error} and {output}")
        return output

    def finish(self) -> None:
        self.event("lane", "PASS")


def write_action_outputs(values: dict[str, str]) -> None:
    destination = os.environ.get("GITHUB_OUTPUT")
    if destination is None:
        return
    with Path(destination).open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise ValueError(f"Multiline GitHub output is not allowed: {key}")
            stream.write(f"{key}={value}\n")


def plan_scope(
    root: Path, *, event: str, base: str | None, focus: str, value: str | None,
    exclude_tag: str | None, shard: str | None, head: str = "HEAD",
) -> ImpactPlan:
    """Use the same typed impact planner for PRs, branch diffs and manual cohorts."""
    if event == "pull_request":
        if not base:
            raise ValueError("Pull-request planning requires a base commit")
        if focus != "full" or value or exclude_tag:
            raise ValueError("Pull-request planning uses its Git diff, not manual focus inputs")
        return build_plan(root, base=base, head=head, shard=shard)
    if focus == "branch":
        if not value:
            raise ValueError("Branch focus requires the base branch or commit in value")
        if exclude_tag:
            raise ValueError("exclude_tag is available only with project/product/tag focus")
        return build_plan(root, base=value, head=head, shard=shard)
    if focus in {"project", "product", "tag"}:
        if not value:
            raise ValueError(f"{focus} focus requires a value")
        if focus == "project":
            return build_plan(root, select_project=value, exclude_tag=exclude_tag, shard=shard)
        if focus == "product":
            return build_plan(root, select_product=value, exclude_tag=exclude_tag, shard=shard)
        return build_plan(root, select_tag=value, exclude_tag=exclude_tag, shard=shard)
    if focus == "full":
        if value or exclude_tag:
            raise ValueError("Full focus does not take a value or exclude_tag")
        return build_plan(root, full=True, shard=shard)
    raise ValueError(f"Unknown CI focus: {focus}")


def plan_lane(root: Path, args: argparse.Namespace, log: HostedLog) -> None:
    plan = plan_scope(
        root, event=args.event, base=args.base or None, focus=args.focus,
        value=args.value or None, exclude_tag=args.exclude_tag or None,
        shard=args.shard or None,
        head=args.head,
    )
    destination = root / "build/impact.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
    systems = ["ubuntu-24.04", "windows-2022", "macos-14"] if plan.scope == "full" else [
        "ubuntu-24.04"
    ]
    write_action_outputs({
        "scope": plan.scope,
        "projects": " ".join(plan.projects),
        "docs-changed": str(plan.docs_changed).lower(),
        "portable-matrix": json.dumps({"os": systems, "python": ["3.11"]}),
    })
    log.event("scope", "PASS", scope=plan.scope, projects=len(plan.projects))
    print(plan.model_dump_json(indent=2))


def matrix_lane(root: Path, projects: tuple[str, ...] | None, log: HostedLog) -> None:
    matrix = build_matrix(root, projects)
    destination = root / "build/build-matrix.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(matrix.model_dump_json(indent=2) + "\n", encoding="utf-8")
    write_action_outputs({
        "matrix": matrix.model_dump_json(),
        "has-projects": str(bool(matrix.include)).lower(),
    })
    log.event("matrix", "PASS", projects=len(matrix.include))
    print(matrix.model_dump_json())


def markdown_checks(root: Path, log: HostedLog) -> None:
    log.run("docs-policy", (sys.executable, "-B", "-m", "kicad_tooling.docs_policy"), cwd=root)
    rumdl = Path(sysconfig.get_path("scripts")) / (
        "rumdl.exe" if sys.platform == "win32" else "rumdl")
    log.run("rumdl", (str(rumdl), "check", ".", "--no-cache"), cwd=root)
    log.run("mdrepo", (sys.executable, "-B", "-m", "mdrepo", "check", "."), cwd=root)


def portable_lane(root: Path, scope: str, projects: tuple[str, ...],
                  docs_changed: bool, jobs: int, log: HostedLog) -> None:
    if scope == "docs":
        markdown_checks(root, log)
    elif scope == "focused":
        if not projects:
            raise ValueError("Focused portable lane requires selected projects")
        argv = (sys.executable, "-B", "-m", "kicad_tooling.ci", *(
            part for project in projects for part in ("--project", project)
        ), "--jobs", str(jobs), "--output", "build/portable")
        log.run("portable-focused", argv, cwd=root)
        if docs_changed:
            markdown_checks(root, log)
    elif scope == "full":
        log.run("portable-full", (sys.executable, "-B", "-m", "kicad_tooling.ci",
                                  "--jobs", str(jobs), "--output", "build/portable"), cwd=root)
    else:
        raise ValueError(f"Unknown portable scope: {scope}")


def windows_types(root: Path, log: HostedLog) -> None:
    log.run("windows-types", (sys.executable, "-B", "-m", "pyright", "--pythonpath",
                              sys.executable, "--pythonplatform", "Windows",
                              "--pythonversion", "3.11", str(Path(__file__).resolve().parent)), cwd=root,
            stdout_path=root / "build/portable/windows-types.txt")


def windows_smoke(root: Path, log: HostedLog) -> None:
    log.run("windows-inventory", (sys.executable, "-B", "-m", "kicad_tooling.template", "list",
                                  "--format", "json"), cwd=root,
            stdout_path=root / "build/portable/windows-inventory.json")
    log.run("windows-policy", (sys.executable, "-B", "-m", "kicad_tooling.ci",
                               "--format", "json"), cwd=root,
            stdout_path=root / "build/portable/windows-policy.json")


def checked_source(root: Path, log: HostedLog) -> None:
    log.run("source-diff", ("git", "diff", "--exit-code"), cwd=root)
    log.run("index-diff", ("git", "diff", "--cached", "--exit-code"), cwd=root)


def native_lane(root: Path, *, project: str, image: str, pr_head: str,
                fault_probes: bool, log: HostedLog) -> None:
    if not project or "@sha256:" not in image:
        raise ValueError("Native lane requires a project and digest-pinned image")
    if sys.platform == "win32":
        raise ValueError("The Docker native lane requires a Unix runner")
    checked = subprocess.run(("git", "rev-parse", "HEAD"), cwd=root, capture_output=True,
                             text=True, check=True).stdout.strip()
    (root / "build").mkdir(exist_ok=True)
    (root / "build/checked-commit.txt").write_text(checked + "\n", encoding="utf-8")
    log.run("status-before", ("git", "status", "--porcelain=v1"), cwd=root,
            stdout_path=root / "build/status-before.txt")
    log.run("source-archive", ("git", "archive", "--format=tar.gz",
                               "--output=build/checked-source.tar.gz", "HEAD"), cwd=root)
    environment = os.environ.copy()
    environment.update({"CHECKED_SHA": checked, "PR_HEAD_SHA": pr_head, "PROJECT_ID": project})
    docker = (
        "docker", "run", "--rm", "--platform", "linux/amd64", "--user",
        f"{os.getuid()}:{os.getgid()}", "--entrypoint", "sh",
        "-e", "HOME=/tmp/kicad-template", "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "PYTHONPATH=/work/build/policy-deps", "-e", "CHECKED_SHA",
        "-e", "PR_HEAD_SHA", "-e", "PROJECT_ID", "-v", f"{root}:/work",
        "-w", "/work", image, "-ec",
    )
    try:
        log.run("docker-pull", ("docker", "pull", image), cwd=root)
        log.run("native-deps", (sys.executable, "-B", "-m", "kicad_tooling.native_deps",
                                "--image", image), cwd=root)
        log.run("native-check", (*docker,
                                 'python3 -m kicad_tooling.ci --kicad --project "$PROJECT_ID" '
                                 + "--output build/review"), cwd=root, env=environment)
        if fault_probes:
            log.run("fault-probes", (*docker, "python3 -m kicad_tooling.ci --fault-probes --output build/fault-probes"), cwd=root, env=environment)
    finally:
        checked_source(root, log)


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
        "README.md", "AGENTS.md", "CLAUDE.md", "CHANGELOG.md",
        ".gitignore", ".gitattributes", "pyproject.toml", "requirements-tooling.txt",
        "catalog/documentation-policy.json",
    )
    references = (
        "examples/catalog/projects.json", "examples/catalog/products.json",
        "examples/catalog/parts.json", "examples/catalog/interfaces.json",
        "examples/catalog/libraries.json", "examples/catalog/toolchains.json",
        "examples/catalog/team-policy.json", "examples/catalog/release-policies.json",
        "examples/projects/arduino-uno-status-led/project.json",
    )
    missing = [name for name in (*directories, *files, *references)
               if not (root / name).exists()]
    if missing:
        raise ValueError(
            "Release rehearsal requires retained public template fixtures; restore these "
            f"paths from the matching template version: {', '.join(missing)}"
        )

    def ignore_local(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name == ".git" or ephemeral(name)
                   or generated_artifact((Path(directory) / name).relative_to(root).as_posix())}
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
    shutil.copytree(root / "examples/catalog", target / "catalog", dirs_exist_ok=True,
                    ignore=ignore_local)
    shutil.copy2(Path(__file__).resolve().parent / "fixtures/scaffold-license.txt", target / "LICENSE")


def release_lane(root: Path, log: HostedLog) -> None:
    """Exercise a committed disposable fixture without changing checked-out source."""
    target = root / "build/rehearsal-source"
    release_fixture(root, target)
    log.event("fixture-copy", "PASS")
    manifest_path = target / "examples/projects/arduino-uno-status-led/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    if manifest.release_exports is None:
        raise ValueError("Reference project lacks release export settings")
    settings = manifest.release_exports.model_copy(update={
        "supplier_formats": ("odb", "ipc2581", "ipcd356"),
    })
    write_model(manifest_path, manifest.model_copy(update={"release_exports": settings}))
    log.event("supplier-formats", "PASS")
    log.run("fixture-init", ("git", "init", "-q"), cwd=target)
    log.run("fixture-add", ("git", "add", "--all"), cwd=target)
    log.run("fixture-commit", ("git", "-c", "user.name=Scaffold CI fixture",
                               "-c", "user.email=fixture@example.invalid", "commit", "-qm",
                               "Disposable release rehearsal"), cwd=target)
    for stage, command in (
        ("release-prepare", ("kicad_tooling.release", "prepare", "--project",
                             "arduino-uno-status-led", "--release-id", "ci-review")),
        ("release-package", ("kicad_tooling.release", "package", "--manifest",
                             "build/releases/ci-review/manifest.json", "--output", "build/ci-review.zip")),
        ("release-verify", ("kicad_tooling.release", "verify", "--archive", "build/ci-review.zip")),
    ):
        log.run(stage, (sys.executable, "-B", "-m", *command), cwd=target)
    checked_source(target, log)
    fixture = Path(__file__).resolve().parent / "fixtures/foreign-eagle-board.xml"
    conversion = log.run("foreign-conversion", (
        sys.executable, "-B", "-m", "kicad_tooling.template", "convert-pcb",
        "--source", str(fixture), "--project-id",
        "foreign-smoke", "--toolchain", "kicad-10.0.5", "--input-format", "eagle",
        "--runner", "container", "--format", "json",
    ), cwd=target, stdout_path=target / "build/foreign-pcb-conversion.json")
    receipt = read_model(conversion, ForeignPcbReport)
    native_summary = receipt.native_summary
    if (receipt.status != "PASS" or not receipt.review_required
            or receipt.build_authorized or native_summary is None
            or native_summary.errors or native_summary.source_format.lower() != "eagle"):
        raise ValueError("Foreign conversion receipt failed review assertions")
    source = Path(receipt.run_directory) / "stage/foreign-smoke.kicad_pro"
    if source.with_suffix(".kicad_pcb").read_text(encoding="utf-8").count(
        '(layer "Edge.Cuts")'
    ) != 4:
        raise ValueError("Foreign PCB edge geometry changed")
    imported_path = log.run("foreign-import", (
        sys.executable, "-B", "-m", "kicad_tooling.template", "import-project", "--source",
        str(source), "--project-id", "foreign-smoke", "--toolchain", "kicad-10.0.5",
        "--format", "json",
    ), cwd=target)
    imported = read_model(imported_path, ProjectImportReport)
    if imported.status != "PASS" or not imported.review_required:
        raise ValueError("Foreign import receipt failed review assertions")
    project = read_model(target / "projects/foreign-smoke/project.json", ProjectManifest)
    if project.kind is not ProjectKind.PCB_ONLY or project.status != "engineering":
        raise ValueError("Foreign import did not create an engineering PCB-only project")
    log.event("foreign-review", "PASS")


def gate_result(scope_result: str, scope: str, unit_result: str, matrix_result: str,
                kicad_result: str, has_projects: str, release_result: str) -> None:
    """Fail closed on every expected prerequisite, including skipped jobs."""
    if scope_result != "success" or unit_result != "success":
        raise ValueError("Planning and portable checks must both succeed")
    expected: dict[str, tuple[str, str]] = {
        "docs": ("skipped", "skipped"),
        "focused": ("success", "success"),
        "full": ("success", "success" if has_projects == "true" else "skipped"),
    }
    if scope not in expected:
        raise ValueError(f"Unknown acceptance scope: {scope}")
    expected_matrix, expected_kicad = expected[scope]
    if matrix_result != expected_matrix or kicad_result != expected_kicad:
        raise ValueError("Matrix or KiCad job outcome does not match the planned scope")
    if scope == "focused" and has_projects != "true":
        raise ValueError("Focused acceptance requires selected projects")
    if scope == "full" and has_projects not in {"true", "false"}:
        raise ValueError("Full acceptance requires a definite project-presence result")
    expected_release = "success" if scope == "full" and has_projects == "true" else "skipped"
    if release_result != expected_release:
        raise ValueError("Release rehearsal outcome does not match the planned scope")
    if scope == "full" and has_projects == "false":
        print("Scaffold checks passed; no live designs are declared or validated.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Plan PR, branch or manually focused acceptance")
    plan.add_argument("--event", choices=("pull_request", "workflow_dispatch", "push", "local"),
                      default="local")
    plan.add_argument("--base")
    plan.add_argument("--head", default="HEAD")
    plan.add_argument("--focus", choices=("full", "branch", "project", "product", "tag"),
                      default="full")
    plan.add_argument("--value")
    plan.add_argument("--exclude-tag")
    plan.add_argument("--shard")
    matrix = commands.add_parser("matrix", help="Build native project matrix")
    matrix.add_argument("--scope", choices=("full", "focused"), required=True)
    matrix.add_argument("--projects", default="", help="Space-separated planned IDs")
    portable = commands.add_parser("portable", help="Run full, focused or docs portable checks")
    portable.add_argument("--scope", choices=("full", "focused", "docs"), required=True)
    portable.add_argument("--projects", default="", help="Space-separated planned IDs")
    portable.add_argument("--docs-changed", choices=("true", "false"), default="false")
    portable.add_argument("--jobs", type=int, default=4)
    commands.add_parser("windows-types", help="Check Windows-targeted Python types")
    commands.add_parser("windows-smoke", help="Run Windows portability smoke tests")
    commands.add_parser("source-clean", help="Verify tracked source and index are unchanged")
    native = commands.add_parser("native", help="Run pinned KiCad lane and optional fault probes")
    native.add_argument("--project", required=True)
    native.add_argument("--image", required=True)
    native.add_argument("--pr-head", required=True)
    native.add_argument("--fault-probes", choices=("true", "false"), default="false")
    commands.add_parser("release", help="Run disposable release and foreign-board rehearsal")
    gate = commands.add_parser("gate", help="Verify every hosted prerequisite outcome")
    gate.add_argument("--scope-result", default=os.environ.get("SCOPE_RESULT"))
    gate.add_argument("--scope", default=os.environ.get("SCOPE"))
    gate.add_argument("--unit-result", default=os.environ.get("UNIT_RESULT"))
    gate.add_argument("--matrix-result", default=os.environ.get("MATRIX_RESULT"))
    gate.add_argument("--kicad-result", default=os.environ.get("KICAD_RESULT"))
    gate.add_argument("--has-projects", default=os.environ.get("HAS_PROJECTS"))
    gate.add_argument("--release-result", default=os.environ.get("RELEASE_RESULT"))
    args = parser.parse_args()
    root = args.root.resolve()
    log = HostedLog(root, args.command)
    try:
        if args.command == "plan":
            plan_lane(root, args, log)
        elif args.command == "matrix":
            selected = tuple(args.projects.split()) if args.scope == "focused" else None
            if args.scope == "focused" and not selected:
                raise ValueError("Focused matrix requires selected projects")
            matrix_lane(root, selected, log)
        elif args.command == "portable":
            portable_lane(root, args.scope, tuple(args.projects.split()),
                          args.docs_changed == "true", args.jobs, log)
        elif args.command == "windows-types":
            windows_types(root, log)
        elif args.command == "windows-smoke":
            windows_smoke(root, log)
        elif args.command == "source-clean":
            checked_source(root, log)
        elif args.command == "native":
            native_lane(root, project=args.project, image=args.image, pr_head=args.pr_head,
                        fault_probes=args.fault_probes == "true", log=log)
        elif args.command == "release":
            release_lane(root, log)
        elif args.command == "gate":
            gate_result(args.scope_result, args.scope, args.unit_result,
                        args.matrix_result, args.kicad_result, args.has_projects,
                        args.release_result)
        log.finish()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        log.event("lane", "FAIL", error=str(exc))
        print(f"hosted-ci: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
