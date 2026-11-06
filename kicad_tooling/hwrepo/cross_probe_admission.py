"""Admit and revalidate the source-bound receipts used by cross-probe exports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .artifact_access import artifact_file, read_regular_bytes
from .contracts import parse_model_text
from .cross_probe_operation_models import CrossProbeBuildRequest
from .cross_probe_variant import VariantObservation, read_variant_observation
from .discovery import load_config
from .evidence import digest
from .findings_view_evidence import verified_findings_drawing
from .findings_view_models import FindingsViewReport
from .model_primitives import RepositoryPath
from .native_project_validation_models import ValidationSummary
from .native_summary_binding import validate_native_summary_binding
from .parts_receipts import read_parts_receipt
from .project_models import ProjectConfig
from .project_source_hashes import hash_project_sources as hashes
from .purchasing_models import PurchasingReport
from .review_overview_evidence import (
    ReviewContext,
    read_receipt,
    recorded_directory,
    selected_receipt,
    source_mismatch,
)
from .selection import resolve_project
from .source_state_models import SourceHashInventory


@dataclass(frozen=True, slots=True)
class CrossProbeAdmittedInputs:
    """Receipts and observations admitted for one current project source snapshot."""

    request: CrossProbeBuildRequest
    project_config_path: RepositoryPath
    config: ProjectConfig
    source_hashes: SourceHashInventory
    parts_path: Path
    parts: PurchasingReport
    parts_sha256: str
    findings_path: Path
    findings: FindingsViewReport
    findings_sha256: str
    summary_path: Path
    summary: ValidationSummary
    variant: VariantObservation | None
    drawing_bytes: Mapping[str, bytes]

    def __post_init__(self) -> None:
        """Keep admitted source and drawing indexes stable through publication."""
        object.__setattr__(self, "source_hashes", MappingProxyType(dict(self.source_hashes)))
        object.__setattr__(
            self,
            "drawing_bytes",
            MappingProxyType(
                {name: bytes(content) for name, content in self.drawing_bytes.items()}
            ),
        )


def admit_cross_probe_inputs(
    root: Path, request: CrossProbeBuildRequest
) -> CrossProbeAdmittedInputs:
    """Verify selected receipts and retain the exact evidence accepted for export."""
    root = root.resolve()
    project = resolve_project(root, request.project_id)
    config = load_config(root, project.config)
    current = hashes(root, config.source_roots)
    context = ReviewContext(root, request.project_id, config, current)
    parts_path, parts, parts_sha = read_parts_receipt(
        root, request.parts_report, request.project_id
    )
    findings_path = selected_receipt(root, request.findings_view, "review.json")
    findings, findings_sha = read_receipt(findings_path, FindingsViewReport)
    if (
        findings.project_id != request.project_id
        or not recorded_directory(root, findings.output_directory, findings_path.parent)
        or dict(parts.source_hashes) != current
        or dict(findings.source_hashes) != current
    ):
        raise ValueError("Parts and drawings must match the current project and source scope")
    mismatch = source_mismatch(context, parts.input_hashes, exact_scope=False)
    if mismatch:
        raise ValueError(f"Parts catalog or input is stale: {mismatch}")
    summary_path = artifact_file(root, findings.native_summary)
    if digest(summary_path) != findings.native_summary_sha256:
        raise ValueError("Findings native summary changed")
    summary_bytes, _ = read_regular_bytes(summary_path, maximum=8 * 1024 * 1024)
    summary = parse_model_text(summary_bytes.decode("utf-8"), ValidationSummary)
    validate_native_summary_binding(summary, config, current)
    variant = (
        None
        if request.assembly_variant is None
        else read_variant_observation(
            root,
            config,
            current,
            findings,
            request.assembly_variant,
            summary.artifacts_sha256.get("netlist.xml"),
        )
    )
    drawing_bytes = {
        drawing.file: verified_findings_drawing(root, findings_path, drawing, findings)
        for drawing in findings.drawings
    }
    if len(drawing_bytes) != len(findings.drawings):
        raise ValueError("Findings receipt repeats a drawing filename")
    return CrossProbeAdmittedInputs(
        request=request,
        project_config_path=project.config,
        config=config,
        source_hashes=current,
        parts_path=parts_path,
        parts=parts,
        parts_sha256=parts_sha,
        findings_path=findings_path,
        findings=findings,
        findings_sha256=findings_sha,
        summary_path=summary_path,
        summary=summary,
        variant=variant,
        drawing_bytes=drawing_bytes,
    )


def verify_cross_probe_inputs(root: Path, admitted: CrossProbeAdmittedInputs) -> None:
    """Re-read the admitted receipts and sources before and after publication."""
    root = root.resolve()
    if (
        hashes(root, admitted.config.source_roots) != admitted.source_hashes
        or load_config(root, admitted.project_config_path) != admitted.config
    ):
        raise ValueError("Project source or configuration changed during cross-probe export")
    if (
        digest(admitted.parts_path) != admitted.parts_sha256
        or digest(admitted.findings_path) != admitted.findings_sha256
    ):
        raise ValueError("Selected parts or drawing receipt changed during export")
    if digest(admitted.parts_path.parent / "netlist.xml") != admitted.parts.netlist_sha256:
        raise ValueError("Retained parts netlist changed during export")
    if digest(admitted.summary_path) != admitted.findings.native_summary_sha256:
        raise ValueError("Retained native summary changed during export")
    for drawing in admitted.findings.drawings:
        if (
            verified_findings_drawing(root, admitted.findings_path, drawing, admitted.findings)
            != admitted.drawing_bytes[drawing.file]
        ):
            raise ValueError("Retained drawing changed during export")
    if admitted.variant is not None:
        requested_variant = admitted.request.assembly_variant
        if (
            requested_variant is None
            or read_variant_observation(
                root,
                admitted.config,
                admitted.source_hashes,
                admitted.findings,
                requested_variant,
                admitted.summary.artifacts_sha256.get("netlist.xml"),
            )
            != admitted.variant
        ):
            raise ValueError("Named variant evidence changed during export")
