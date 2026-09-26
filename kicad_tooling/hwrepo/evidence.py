"""Bind retained evidence to observed committed source and verify its bytes."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .contracts import read_model, repo_path
from .models import (
    CommandEvidence,
    EvidenceFile,
    ScopedReleasePortableReport,
    SourceState,
    StaticPipelineReport,
    ValidationSummary,
)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), *args),
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_state(root: Path) -> SourceState:
    """Local dirty checks remain useful, but cannot supply release evidence."""
    try:
        commit = git(root, "rev-parse", "HEAD")
        names = git(root, "ls-files", "-z").split("\0")
        files = {name: digest(repo_path(root, name)) for name in names if name}
        return SourceState(
            commit=commit,
            clean=(
                not git(root, "status", "--porcelain=v1", "--untracked-files=all")
                and files == committed_hashes(root, commit)
            ),
            files_sha256=files,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return SourceState()


def committed_hashes(root: Path, commit: str) -> dict[str, str]:
    """Compare against Git objects even when assume-unchanged hides local edits."""
    entries = git(root, "ls-tree", "-r", "--full-tree", "-z", commit).split("\0")
    objects: list[tuple[str, str]] = []
    for entry in entries:
        if not entry:
            continue
        metadata, name = entry.split("\t", 1)
        mode, kind, object_id = metadata.split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("Release source must contain regular files, not links or submodules")
        repo_path(root, name)
        objects.append((name, object_id))
    batch = subprocess.run(
        ("git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), "cat-file", "--batch"),
        input="".join(f"{oid}\n" for _, oid in objects).encode(),
        capture_output=True,
        check=True,
    )
    offset = 0
    hashes: dict[str, str] = {}
    for name, _ in objects:
        end = batch.stdout.index(b"\n", offset)
        size = int(batch.stdout[offset:end].split()[-1])
        start = end + 1
        hashes[name] = hashlib.sha256(batch.stdout[start : start + size]).hexdigest()
        offset = start + size + 1
    return hashes


def verify_source(observed: SourceState | None, expected: SourceState) -> None:
    if observed is None or not observed.clean or observed.commit is None:
        raise ValueError("Evidence was not produced from clean committed source")
    if observed != expected or not observed.files_sha256:
        raise ValueError("Evidence source commit or file hashes differ from the release source")


def evidence_path(root: Path, reference: EvidenceFile) -> Path:
    path = repo_path(root, reference.path)
    if digest(path) != reference.sha256:
        raise ValueError(f"Evidence hash differs: {reference.path}")
    return path


def verify_portable(
    root: Path, reference: EvidenceFile, source: SourceState
) -> StaticPipelineReport:
    report = read_model(evidence_path(root, reference), StaticPipelineReport)
    verify_source(report.source, source)
    gates = (
        report.registry,
        report.repository,
        report.documentation,
        report.product,
        report.generation,
        report.project_tests,
    )
    commands = (
        report.rumdl,
        report.mdrepo,
        report.ruff,
        report.pyright,
        report.unit_tests,
        *report.project_tests.commands.values(),
    )
    if (
        report.status != "PASS"
        or any(gate.status != "PASS" for gate in gates)
        or any(
            command.returncode != 0 or command.error is not None
            for command in commands
            if command is not None
        )
    ):
        raise ValueError("Portable report contains failed or missing checks")
    if any(
        (
            report.registry.issues,
            report.repository.issues,
            report.documentation.issues,
            report.product.issues,
            report.generation.issues,
        )
    ):
        raise ValueError("Portable report contains unresolved findings")
    return report


def verify_release_portable(
    root: Path,
    reference: EvidenceFile,
    source: SourceState,
    project_ids: tuple[str, ...],
) -> StaticPipelineReport | ScopedReleasePortableReport:
    """Accept full evidence or an explicitly scoped, exact-project release lane.

    A local ``kicad_tooling.ci --project`` report has no source identity and is never
    sufficient by itself. The release wrapper binds that report to the clean
    committed source and to the complete selected release project set.
    """
    path = evidence_path(root, reference)
    try:
        report = read_model(path, ScopedReleasePortableReport)
    except ValueError as scoped_error:
        # The other admitted shape is the full static report. Both adapters
        # reject extra fields, so a bare focused report cannot cross this gate.
        try:
            return verify_portable(root, reference, source)
        except ValueError as full_error:
            raise ValueError(
                f"Portable evidence is neither a full nor a valid scoped report: {scoped_error}"
            ) from full_error
    verify_source(report.source, source)
    expected = tuple(sorted(project_ids))
    checks = report.checks
    if (
        not expected
        or len(set(expected)) != len(expected)
        or (
            report.projects != expected
            or checks.projects != expected
            or checks.registry.projects != expected
        )
    ):
        raise ValueError("Portable release scope differs from selected projects")
    gates = (
        checks.registry,
        checks.repository,
        checks.product,
        checks.generation,
        checks.project_tests,
    )
    if (
        checks.status != "PASS"
        or any(gate.status != "PASS" for gate in gates)
        or any(
            command.returncode != 0 or command.error is not None
            for command in checks.project_tests.commands.values()
        )
    ):
        raise ValueError("Scoped portable report contains failed or missing checks")
    if any(
        (
            checks.registry.issues,
            checks.repository.issues,
            checks.product.issues,
            checks.generation.issues,
        )
    ):
        raise ValueError("Scoped portable report contains unresolved findings")
    from .product import load_repository

    repository = load_repository(root, expected)
    if repository.issues or checks.product.products != tuple(
        product.id for product in repository.products
    ):
        raise ValueError("Scoped portable report omits dependent product checks")
    return report


def verify_native(
    root: Path, reference: EvidenceFile, source: SourceState, project_id: str
) -> ValidationSummary:
    from .discovery import load_config, load_registry
    from .models import PcbOnlyValidationContract, ProjectKind, SchematicValidationContract

    path = evidence_path(root, reference)
    report = read_model(path, ValidationSummary)
    verify_source(report.source, source)
    project = next(project for project in load_registry(root).projects if project.id == project_id)
    config = load_config(root, project.config)
    if report.checked_commit != source.commit or report.project_id != project_id:
        raise ValueError("Native report identifies a different project or source commit")
    if (
        report.project_kind != config.kind
        or report.assurance_profile != config.assurance_profile
        or report.not_for_manufacture != config.not_for_manufacture
    ):
        raise ValueError("Native report metadata differs from the project manifest")
    required = {
        "governance",
        "repository",
        "product_policy",
        "source_scope",
        "source_unchanged",
        "toolchain",
    }
    if project.kind is ProjectKind.PCB:
        required.update({"erc", "schematic_svg", "drc", "netlist", "pcb_svg"})
    elif project.kind is ProjectKind.PCB_ONLY:
        required.update({"drc", "pcb_svg"})
    elif project.kind is ProjectKind.SYSTEM_WIRING:
        required.update({"erc", "schematic_svg", "system_contract"})
    elif project.kind is ProjectKind.HARNESS_INTERFACE:
        required.update({"erc", "schematic_svg", "harness_contract"})
    else:
        required.update({"erc", "schematic_svg"})
    if config.electrical is not None:
        required.add("grounding")
    if (
        config.electrical is not None
        or config.component_identity.required
        or (
            isinstance(config.validation, SchematicValidationContract)
            and config.validation.components
        )
    ):
        required.add("netlist")
    if (
        report.status != "PASS"
        or not required <= report.checks.keys()
        or any(
            check.status != "PASS"
            or check.error is not None
            or check.returncode not in {None, 0}
            or check.findings not in {None, 0}
            for check in report.checks.values()
        )
    ):
        raise ValueError("Native report contains failed or missing checks")
    toolchain = report.checks["toolchain"]
    if toolchain.observed_version != config.kicad_version or toolchain.image != config.image:
        raise ValueError("Native toolchain differs from the pinned project toolchain")
    expected = {name: source.files_sha256[name] for name in config.required_inputs}
    if any(
        report.checks[name].source_hashes != expected
        for name in ("source_scope", "source_unchanged")
    ):
        raise ValueError("Native design inventory differs from committed inputs")
    if not report.artifacts_sha256:
        raise ValueError("Native report retains no artifacts")
    for name, expected_digest in report.artifacts_sha256.items():
        if digest(repo_path(path.parent, name)) != expected_digest:
            raise ValueError(f"Missing or changed native artifact: {name}")
    # Re-evaluate the retained native outputs, rather than trusting summary labels.
    from ..validate import check_netlist, check_report, svg_files
    from .models import PcbValidationContract

    if config.electrical is not None:
        from ..validate import read_netlist
        from .electrical import grounding_checks, load_analysis

        electrical = load_analysis(root, config)
        if electrical is not None and any(
            row.status not in {"PASS", "NOT_APPLICABLE"}
            for row in grounding_checks(
                electrical.grounding, read_netlist(path.parent / "netlist.xml")
            )
        ):
            raise ValueError("Retained netlist fails current grounding requirements")

    commands = {"version"}
    if isinstance(config.validation, PcbOnlyValidationContract):
        commands.update({"drc", "pcb_svg"})
        if check_report(path.parent / "drc.json", "drc", config):
            raise ValueError("Retained DRC report contains findings")
        svg_files(path.parent, "pcb_svg")
    else:
        commands.update({"erc", "schematic_svg"})
        if check_report(path.parent / "erc.json", "erc", config):
            raise ValueError("Retained ERC report contains findings")
        svg_files(path.parent, "schematic_svg")
    if isinstance(config.validation, PcbValidationContract):
        commands.update({"drc", "netlist", "pcb_svg"})
        if check_report(path.parent / "drc.json", "drc", config):
            raise ValueError("Retained DRC report contains findings")
        svg_files(path.parent, "pcb_svg")
    if "netlist" in required:
        from .product import check_project_netlist

        commands.add("netlist")
        if isinstance(config.validation, (PcbValidationContract, SchematicValidationContract)):
            check_netlist(path.parent / "netlist.xml", config.validation)
        check_project_netlist(root, project_id, path.parent / "netlist.xml")
        if (
            config.component_identity.required
            and report.checks["netlist"].identity_status != "PASS"
        ):
            raise ValueError("Required component identity was not checked")
    for name in commands:
        filename = f"{name}.command.json"
        if filename not in report.artifacts_sha256:
            raise ValueError(f"Native command evidence is missing: {name}")
        command = read_model(path.parent / filename, CommandEvidence)
        if command.returncode != 0 or command.error is not None:
            raise ValueError(f"Retained native command failed: {name}")
    return report
