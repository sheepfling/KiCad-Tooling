"""Build a named-variant BOM from verified schematic and PCB exports."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .artifact_access import artifact_file, read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import parse_model_text, read_model, repo_path, write_model
from .cross_probe import build_cross_probe
from .cross_probe_variant import read_variant_observation
from .discovery import load_config, load_registry
from .evidence import digest
from .findings_view_models import FindingsViewReport
from .models import PurchasingFinding
from .native_project_validation_models import ValidationSummary
from .native_summary_binding import validate_native_summary_binding
from .part_catalog_models import PartsCatalog
from .parts_receipts import read_parts_receipt
from .project_source_hashes import hash_project_sources as hashes
from .purchasing import plan, read_components, review_csv_text, write_csvs
from .review_overview_evidence import (
    ReviewContext,
    read_receipt,
    recorded_directory,
    selected_receipt,
    source_mismatch,
)
from .selection import resolve_project
from .variant_parts_population import reconcile_variant_population
from .variant_parts_review_html import render_variant_parts_review
from .variant_parts_review_models import VariantPartsReviewReport


def build_variant_parts_review(
    root: Path,
    project_id: str,
    parts_report: Path,
    findings_view: Path,
    assembly_variant: str,
    output: Path | None = None,
) -> VariantPartsReviewReport:
    """Prepare review quantities only where one native variant reconciles."""
    root = root.resolve()
    project = resolve_project(root, project_id)
    config = load_config(root, project.config)
    current = hashes(root, config.source_roots)
    parts_path, parts, parts_sha = read_parts_receipt(root, parts_report, project_id)
    registry = load_registry(root)
    if registry.catalogs.parts not in parts.input_hashes:
        raise ValueError("Parts receipt lacks source-bound parts catalog; prepare parts again")
    findings_path = selected_receipt(root, findings_view, "review.json")
    findings, findings_sha = read_receipt(findings_path, FindingsViewReport)
    if (
        dict(parts.source_hashes) != current
        or findings.project_id != project_id
        or dict(findings.source_hashes) != current
        or not recorded_directory(root, findings.output_directory, findings_path.parent)
    ):
        raise ValueError("Parts and findings receipts must match the current project source")
    context = ReviewContext(root, project_id, config, current)
    mismatch = source_mismatch(context, parts.input_hashes, exact_scope=False)
    if mismatch:
        raise ValueError(f"Parts catalog or preferences are stale: {mismatch}")
    summary_path = artifact_file(root, findings.native_summary)
    summary_bytes, _ = read_regular_bytes(summary_path, maximum=8 * 1024 * 1024)
    if digest(summary_path) != findings.native_summary_sha256:
        raise ValueError("Findings native summary changed")
    summary = parse_model_text(summary_bytes.decode("utf-8"), ValidationSummary)
    validate_native_summary_binding(summary, config, current)
    netlist_sha = summary.artifacts_sha256.get("netlist.xml")
    observed = read_variant_observation(
        root, config, current, findings, assembly_variant, netlist_sha
    )
    components, unresolved = reconcile_variant_population(
        observed, read_components(observed.netlist_path)
    )
    catalog_path = repo_path(root, registry.catalogs.parts)
    catalog_sha = digest(catalog_path)
    catalog = read_model(catalog_path, PartsCatalog)
    assert parts.plan is not None
    purchase_plan = plan(
        components, catalog, parts.plan.preferences, project.component_identity.part_ids
    )
    if unresolved:
        purchase_plan = purchase_plan.model_copy(
            update={
                "status": "NEEDS_PARTS",
                "findings": purchase_plan.findings
                + (
                    PurchasingFinding(
                        code="VARIANT_POPULATION_MISMATCH",
                        references=(),
                        message="Some variant references cannot be included in order quantities.",
                        action="Reconcile the named schematic and fitted PCB population.",
                    ),
                ),
            }
        )

    def verify_inputs() -> None:
        if (
            hashes(root, config.source_roots) != current
            or load_config(root, project.config) != config
        ):
            raise ValueError("Project source changed during variant parts review")
        again_path, again_parts, again_sha = read_parts_receipt(root, parts_path, project_id)
        if again_path != parts_path or again_sha != parts_sha or again_parts != parts:
            raise ValueError("Selected parts receipt changed during variant parts review")
        if (
            digest(findings_path) != findings_sha
            or digest(summary_path) != findings.native_summary_sha256
        ):
            raise ValueError("Selected findings evidence changed during variant parts review")
        if source_mismatch(context, parts.input_hashes, exact_scope=False):
            raise ValueError("Parts catalog or preferences changed during variant parts review")
        if load_registry(root) != registry or digest(catalog_path) != catalog_sha:
            raise ValueError("Parts catalog changed during variant parts review")
        if (
            read_variant_observation(root, config, current, findings, observed.name, netlist_sha)
            != observed
        ):
            raise ValueError("Named variant evidence changed during parts review")

    verify_inputs()
    target = output or Path("build/variant-parts") / f"{project_id}-{uuid4().hex[:12]}"
    directory = receipt_directory(root, project_id, target)
    navigation = build_cross_probe(
        root,
        project_id,
        parts_path,
        findings_path,
        directory / "navigation",
        observed.name,
    )
    if (
        navigation.variant_evidence_sha256 != observed.evidence_sha256
        or navigation.assembly_variant != observed.name
    ):
        raise ValueError("Navigation uses different native variant evidence")
    write_csvs(directory, purchase_plan)
    (directory / "unresolved.csv").write_text(
        review_csv_text(
            (("Reference", "Reason"),) + tuple((item.reference, item.reason) for item in unresolved)
        ),
        encoding="utf-8",
    )
    nav_path = directory / "navigation/cross-probe.json"
    report = VariantPartsReviewReport(
        project_id=project_id,
        assembly_variant=observed.name,
        parts_report=parts_path.relative_to(root).as_posix(),
        parts_report_sha256=parts_sha,
        findings_view=findings_path.relative_to(root).as_posix(),
        findings_view_sha256=findings_sha,
        lint_report=observed.lint_path.relative_to(root).as_posix(),
        lint_report_sha256=observed.lint_sha256,
        parts_catalog=registry.catalogs.parts,
        parts_catalog_sha256=catalog_sha,
        source_hashes=current,
        variant_evidence_sha256=observed.evidence_sha256,
        plan=purchase_plan,
        unresolved=unresolved,
        navigation_report=nav_path.relative_to(root).as_posix(),
        navigation_report_sha256=digest(nav_path),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(
        render_variant_parts_review(report, navigation), encoding="utf-8"
    )
    verify_inputs()
    report = report.model_copy(
        update={
            "artifacts_sha256": {
                path.name: digest(path) for path in directory.iterdir() if path.is_file()
            }
        }
    )
    write_model(directory / "variant-parts.json", report)
    return report
