"""Read-only electrical-contract coaching from source-bound KiCad observations."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, TypeVar

from ..check_toolchain import cli_executable
from ..validate import hashes, read_netlist
from .contracts import read_model, repo_path, write_model
from .discovery import load_config, load_registry
from .evidence import digest
from .models import (
    CommandEvidence,
    ContractCoachReport,
    ContractDifference,
    NetlistContract,
    PcbValidationContract,
    ProjectConfig,
    ProjectKind,
    SchematicValidationContract,
    ValidationSummary,
)

Item = TypeVar("Item")


class NetlistRunner(Protocol):
    """Small native-export boundary shared by local and pinned-container capture."""

    def version(self, root: Path, config: ProjectConfig) -> CommandEvidence: ...

    def export(self, root: Path, config: ProjectConfig, output: Path) -> CommandEvidence: ...


def run_command(root: Path, argv: tuple[str, ...], timeout: int = 180) -> CommandEvidence:
    started = datetime.now(UTC).isoformat()
    try:
        result = subprocess.run(
            argv, cwd=root, capture_output=True, text=True, timeout=timeout, check=False,
        )
        return CommandEvidence(
            argv=argv, started_utc=started, returncode=result.returncode,
            stdout=result.stdout, stderr=result.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
        return CommandEvidence(
            argv=argv, started_utc=started, returncode=124, stdout=stdout,
            stderr=stderr, error=f"Timed out after {timeout} seconds",
        )
    except OSError as exc:
        return CommandEvidence(
            argv=argv, started_utc=started, returncode=127, error=str(exc),
        )


class LocalNetlistRunner:
    selected_runner: Literal["local"] = "local"

    def __init__(self, cli: str) -> None:
        executable = cli_executable(cli)
        candidate = Path(executable or cli)
        # Capture the caller's path before run_command changes cwd to the repo.
        self.cli = (
            str(candidate.resolve())
            if executable is not None or candidate.is_absolute() or candidate.parent != Path(".")
            else cli
        )

    def version(self, root: Path, config: ProjectConfig) -> CommandEvidence:
        return run_command(root, (self.cli, "version"))

    def export(self, root: Path, config: ProjectConfig, output: Path) -> CommandEvidence:
        schematic = repo_path(root, config.project).with_suffix(".kicad_sch")
        return run_command(root, (
            self.cli, "sch", "export", "netlist", "--format", "kicadxml",
            "--output", str(output), str(schematic),
        ))


def pinned_image(image: str) -> str:
    """The coach never starts Docker from a mutable tag, even with empty contracts."""
    if re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", image) is None:
        raise ValueError("Catalogued KiCad container must use a sha256 digest-pinned image")
    return image


def docker_prefix() -> tuple[str, ...]:
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    docker = shutil.which("docker") if sys.platform == "win32" else None
    return (
        docker or "docker", "run", "--rm", "--platform", "linux/amd64", *user,
        "--entrypoint", "kicad-cli", "-e", "HOME=/tmp/kicad-coach",
    )


class ContainerNetlistRunner:
    selected_runner: Literal["container"] = "container"

    def version(self, root: Path, config: ProjectConfig) -> CommandEvidence:
        image = pinned_image(config.image)
        return run_command(root, (*docker_prefix(), image, "version"), timeout=600)

    def export(self, root: Path, config: ProjectConfig, output: Path) -> CommandEvidence:
        image = pinned_image(config.image)
        schematic = repo_path(root, config.project).with_suffix(".kicad_sch")
        output = output.resolve()
        if not output.parent.is_relative_to(root.resolve()):
            raise ValueError("Container netlist output must be inside the repository")
        schematic_arg = f"/work/{schematic.relative_to(root).as_posix()}"
        return run_command(root, (
            *docker_prefix(),
            "-v", f"{root}:/work:ro",
            "-v", f"{output.parent}:/output:rw",
            "-w", "/work", image,
            "sch", "export", "netlist", "--format", "kicadxml",
            "--output", f"/output/{output.name}", schematic_arg,
        ), timeout=600)


class AutoNetlistRunner:
    """Use exact local KiCad when available, otherwise the pinned Docker image."""

    def __init__(self, cli: str) -> None:
        self.local = LocalNetlistRunner(cli)
        self.container = ContainerNetlistRunner()
        self.selected: NetlistRunner | None = None
        self.selected_runner: Literal["local", "container"] | None = None
        self.probes: dict[str, CommandEvidence] = {}

    def version(self, root: Path, config: ProjectConfig) -> CommandEvidence:
        local = self.local.version(root, config)
        self.probes["local_version"] = local
        if local.returncode == 0 and local.error is None and local.stdout.strip() == config.kicad_version:
            self.selected = self.local
            self.selected_runner = "local"
            return local
        container = self.container.version(root, config)
        self.probes["container_version"] = container
        self.selected = self.container
        self.selected_runner = "container"
        return container

    def export(self, root: Path, config: ProjectConfig, output: Path) -> CommandEvidence:
        if self.selected is None:
            raise ValueError("Check the exact KiCad runner version before exporting")
        return self.selected.export(root, config, output)


def project_context(root: Path, project_id: str) -> tuple[ProjectConfig, NetlistContract, dict[str, str]]:
    """Resolve only a schematic-backed island and its complete declared inputs."""
    project = next((item for item in load_registry(root).projects if item.id == project_id), None)
    if project is None:
        raise ValueError(f"Unknown project {project_id!r}")
    if project.kind is ProjectKind.PCB_ONLY:
        raise ValueError(
            "PCB-only has no authoritative schematic or electrical contract. "
            "Add and review a schematic, then migrate this island to pcb."
        )
    if project.kind not in {ProjectKind.PCB, ProjectKind.SCHEMATIC}:
        raise ValueError("Contract coaching is for pcb or schematic projects only")
    config = load_config(root, project.config)
    if config.project_id != project_id or config.kind is not project.kind:
        raise ValueError("Project manifest and resolved configuration disagree")
    validation = config.validation
    if not isinstance(validation, (PcbValidationContract, SchematicValidationContract)):
        raise TypeError("Project has no electrical component/net contract")
    current = hashes(root, config.source_roots)
    if set(current) != set(config.required_inputs):
        raise ValueError(
            "Declared source inventory differs from current design files; "
            "repair project.json before coaching"
        )
    return config, NetlistContract(
        components=validation.components, nets=validation.nets,
    ), current


def category_differences(
    kind: Literal["component", "net"],
    actual: Mapping[str, Item], expected: Mapping[str, Item],
) -> tuple[ContractDifference, ...]:
    changes: list[ContractDifference] = []
    for identifier in sorted(actual.keys() | expected.keys()):
        if identifier not in expected:
            difference = "observed_only"
        elif identifier not in actual:
            difference = "authored_only"
        elif actual[identifier] != expected[identifier]:
            difference = "different"
        else:
            continue
        changes.append(ContractDifference(
            kind=kind, identifier=identifier, difference=difference,
        ))
    return tuple(changes)


def differences(observed: NetlistContract, authored: NetlistContract) -> tuple[ContractDifference, ...]:
    return (
        *category_differences("component", observed.components, authored.components),
        *category_differences("net", observed.nets, authored.nets),
    )


def ready_report(
    project_id: str, config: ProjectConfig, current: dict[str, str],
    observed: NetlistContract, authored: NetlistContract, netlist_hash: str,
    native_status: Literal["PASS", "FAIL"] | None,
    commands: dict[str, CommandEvidence] | None = None,
    receipt_dir: str | None = None,
    selected_runner: Literal["local", "container"] | None = None,
) -> ContractCoachReport:
    changes = differences(observed, authored)
    actions = [(
        "Compare each UNREVIEWED observation with requirements and the KiCad design; "
        "do not copy exported values into tests/contract.json as an approval."
    )]
    if changes:
        actions.append(
            "Resolve each difference by reviewing the design and independently authored "
            "expectations with the responsible engineer."
        )
    else:
        actions.append("The inventories match; still review electrical intent before claiming coverage.")
    if native_status == "FAIL":
        actions.append("The native validation failed; inspect ERC, DRC and netlist checks separately.")
    actions.append("Rerun the selected portable and native lanes after an authored decision.")
    return ContractCoachReport(
        status="READY_FOR_REVIEW", project_id=project_id, project_kind=config.kind,
        selected_runner=selected_runner,
        source_hashes=current, netlist_sha256=netlist_hash,
        native_status=native_status, observed=observed, authored=authored,
        differences=changes, next_actions=tuple(actions),
        commands={} if commands is None else commands, receipt_dir=receipt_dir,
    )


def blocked_report(
    project_id: str, reason: str, project_kind: ProjectKind | None = None,
    commands: dict[str, CommandEvidence] | None = None,
    receipt_dir: str | None = None,
    selected_runner: Literal["local", "container"] | None = None,
) -> ContractCoachReport:
    return ContractCoachReport(
        status="BLOCKED", project_id=project_id, project_kind=project_kind,
        selected_runner=selected_runner,
        issues=(reason,), next_actions=((
            "Repair the named source or evidence problem, then capture or select a fresh "
            "netlist. Do not edit the authored contract from unverified output."
        ),), commands={} if commands is None else commands, receipt_dir=receipt_dir,
    )


def inspect_summary(root: Path, project_id: str, native_summary: Path) -> ContractCoachReport:
    """Accept a failed contract check only when the export and source are sound."""
    root = root.resolve()
    summary_path = native_summary / "summary.json" if native_summary.is_dir() else native_summary
    kind: ProjectKind | None = None
    try:
        config, authored, current = project_context(root, project_id)
        kind = config.kind
        summary = read_model(summary_path, ValidationSummary)
        if summary.project_id != project_id or summary.project_kind is not config.kind:
            raise ValueError("Native summary belongs to another project or project kind")
        toolchain_check = summary.checks.get("toolchain")
        if (
            toolchain_check is None or toolchain_check.status != "PASS"
            or toolchain_check.error is not None
            or toolchain_check.observed_version != config.kicad_version
            or toolchain_check.image != config.image
        ):
            raise ValueError(
                "Native summary toolchain version or image differs from the current "
                "project configuration; rerun native KiCad validation"
            )
        for key in ("source_scope", "source_unchanged"):
            check = summary.checks.get(key)
            if (check is None or check.status != "PASS" or check.error is not None
                    or check.source_hashes != current):
                raise ValueError(f"Native {key} hashes do not match current declared source")
        netlist_check = summary.checks.get("netlist")
        if (netlist_check is None or netlist_check.status == "NOT_RUN"
                or netlist_check.returncode != 0):
            raise ValueError("Native netlist export was not executed successfully")
        netlist_path = summary_path.parent / "netlist.xml"
        netlist_hash = digest(netlist_path)
        if summary.artifacts_sha256.get("netlist.xml") != netlist_hash:
            raise ValueError("Native netlist bytes differ from the summary artifact hash")
        command_path = summary_path.parent / "netlist.command.json"
        if summary.artifacts_sha256.get("netlist.command.json") != digest(command_path):
            raise ValueError("Native netlist command evidence differs from the summary artifact hash")
        command = read_model(command_path, CommandEvidence)
        if command.returncode != 0 or command.error is not None:
            raise ValueError("Native netlist command evidence records a failed export")
        observed = read_netlist(netlist_path)
        if hashes(root, config.source_roots) != current:
            raise ValueError("Declared source changed while reading native evidence")
        return ready_report(
            project_id, config, current, observed, authored, netlist_hash, summary.status,
        ).model_copy(update={"native_summary": str(summary_path)})
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        return blocked_report(project_id, str(exc), kind).model_copy(
            update={"native_summary": str(summary_path)},
        )


def receipt_directory(root: Path, project_id: str, output: Path | None) -> Path:
    """Create a fresh write-once receipt only below ignored build/."""
    root = root.resolve()
    if output is None:
        parent = repo_path(root, "build/contract-coach")
        parent.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix=f"{project_id}-", dir=parent))
    try:
        relative = output.relative_to(root) if output.is_absolute() else output
    except ValueError as exc:
        raise ValueError("Contract-coach receipts must be under ignored build/") from exc
    if not relative.parts or relative.parts[0] != "build":
        raise ValueError("Contract-coach receipts must be under ignored build/")
    directory = repo_path(root, relative.as_posix())
    directory.mkdir(parents=True, exist_ok=False)
    return directory


def capture(
    root: Path, project_id: str, output: Path, runner: NetlistRunner,
) -> ContractCoachReport:
    """Export an observed netlist using exact local KiCad or a digest-pinned image."""
    root = root.resolve()
    commands: dict[str, CommandEvidence] = {}
    kind: ProjectKind | None = None
    selected_runner: Literal["local", "container"] | None = None
    try:
        requested = output if output.is_absolute() else root / output
        relative = requested.relative_to(root)
        if not relative.parts or relative.parts[0] != "build":
            raise ValueError("Netlist capture output must be under ignored build/")
        output = repo_path(root, relative.as_posix())
        if not output.is_dir():
            raise ValueError("Netlist capture needs a fresh ignored receipt directory")
        config, authored, current = project_context(root, project_id)
        kind = config.kind
        version = runner.version(root, config)
        selected_runner = getattr(runner, "selected_runner", None)
        for probe_name, probe in getattr(runner, "probes", {}).items():
            commands[probe_name] = probe
            write_model(output / f"{probe_name}.command.json", probe)
        commands["version"] = version
        write_model(output / "version.command.json", version)
        if version.returncode != 0 or version.error is not None or version.stdout.strip() != config.kicad_version:
            observed = version.error or version.stderr.strip() or version.stdout.strip()
            raise ValueError(
                f"Exact KiCad {config.kicad_version} is required; runner reported "
                f"{observed[:300]!r}. Inspect version.command.json, then use "
                "--runner local with an exact --cli or --runner container with Docker."
            )
        netlist_path = output / "netlist.xml"
        exported = runner.export(root, config, netlist_path)
        commands["netlist"] = exported
        write_model(output / "netlist.command.json", exported)
        if exported.returncode != 0 or exported.error is not None:
            problem = exported.error or exported.stderr.strip() or "nonzero exit"
            raise ValueError(
                f"KiCad netlist export failed: {problem[:300]}. Inspect netlist.command.json"
            )
        observed = read_netlist(netlist_path)
        if hashes(root, config.source_roots) != current:
            raise ValueError("Declared source changed during netlist capture; rerun against saved source")
        return ready_report(
            project_id, config, current, observed, authored, digest(netlist_path),
            None, commands, str(output), selected_runner,
        )
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        return blocked_report(project_id, str(exc), kind, commands, str(output), selected_runner)


def text_report(report: ContractCoachReport, detail: str = "brief") -> str:
    lines = [
        f"Contract coach: {report.status}",
        f"Project: {report.project_id}; review state: {report.review_state}",
        "Electrical coverage: unapproved; build authorized: no",
    ]
    if report.receipt_dir is not None:
        lines.append(f"Receipt: {report.receipt_dir}")
    if report.selected_runner is not None:
        lines.append(f"KiCad runner: {report.selected_runner}")
    if report.native_summary is not None:
        lines.append(f"Native summary: {report.native_summary}")
    if report.observed is not None:
        lines.append(
            f"Observed: {len(report.observed.components)} components, "
            f"{len(report.observed.nets)} nets; differences: {len(report.differences)}"
        )
        lines.append(f"Bound design files: {len(report.source_hashes)}")
        selected = report.differences if detail == "full" else report.differences[:5]
        for change in selected:
            lines.append(f"- {change.kind} {change.identifier}: {change.difference}")
        if len(selected) < len(report.differences):
            lines.append("More differences are in --detail full or JSON.")
        if detail == "full":
            for reference, component in sorted(report.observed.components.items()):
                lines.append(
                    f"UNREVIEWED component {reference}: value={component.value!r}, "
                    f"footprint={component.footprint!r}, PART_ID={component.part_id!r}"
                )
            for name, nodes in sorted(report.observed.nets.items()):
                lines.append(f"UNREVIEWED net {name!r}: {', '.join(nodes)}")
    for issue in report.issues:
        lines.append(f"Blocked: {issue}")
    for action in report.next_actions:
        lines.append(f"Next: {action}")
    return "\n".join(lines)


def save_receipt(output: Path, report: ContractCoachReport) -> None:
    write_model(output / "report.json", report)
    (output / "report.txt").write_text(text_report(report, "full") + "\n", encoding="utf-8")
