"""Validate portable release evidence against source and selected project scope."""

from __future__ import annotations

from pathlib import Path

from .contracts import read_model
from .evidence import evidence_path, verify_portable, verify_source
from .models import EvidenceFile, ScopedReleasePortableReport, SourceState, StaticPipelineReport
from .product import load_repository


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

    repository = load_repository(root, expected)
    if repository.issues or checks.product.products != tuple(
        product.id for product in repository.products
    ):
        raise ValueError("Scoped portable report omits dependent product checks")
    return report
