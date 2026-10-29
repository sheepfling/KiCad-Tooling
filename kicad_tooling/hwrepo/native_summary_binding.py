"""Validate native summary identity against project-owned source and toolchain."""

from __future__ import annotations

from collections.abc import Mapping

from .models import ValidationSummary
from .project_models import ProjectConfig


def validate_native_toolchain(summary: ValidationSummary, config: ProjectConfig) -> None:
    """Require the recorded native run to use the selected exact toolchain."""
    check = summary.checks.get("toolchain")
    if (
        check is None
        or check.status != "PASS"
        or check.error is not None
        or check.observed_version != config.kicad_version
        or check.image != config.image
    ):
        raise ValueError(
            "Native summary toolchain version or image differs from the current "
            "project configuration; rerun native KiCad validation"
        )


def validate_native_summary_binding(
    summary: ValidationSummary, config: ProjectConfig, source_hashes: Mapping[str, str]
) -> None:
    """Check the project, exact toolchain, and completed source-scope receipts."""
    if summary.project_id != config.project_id or summary.project_kind is not config.kind:
        raise ValueError("Native summary belongs to another project or project kind")
    validate_native_toolchain(summary, config)
    for key in ("source_scope", "source_unchanged"):
        check = summary.checks.get(key)
        if (
            check is None
            or check.status != "PASS"
            or check.error is not None
            or check.source_hashes != source_hashes
        ):
            raise ValueError(f"Native {key} hashes do not match current declared source")
