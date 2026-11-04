"""Register source-bound offline visualization exports."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .assembly_clearance import build_assembly_clearance
from .assembly_clearance_models import AssemblyClearanceReport
from .assembly_review import build_assembly_review
from .assembly_review_models import AssemblyReviewReport
from .board_variant_compare import compare_board_variants as compare_native_board_variants
from .board_variant_compare_models import BoardVariantComparisonReport
from .bom_compare import compare_bom
from .bom_compare_models import BomComparisonReport
from .connectivity_view import build_connectivity_view
from .connectivity_view_models import ConnectivityViewReport
from .cross_probe import build_cross_probe
from .cross_probe_models import CrossProbeReport
from .electrical_ac_comparison import compare_ac_runs
from .electrical_chart_models import AcComparisonReport
from .findings_view import build_findings_view
from .findings_view_models import FindingsViewReport
from .grounding_view import build_grounding_view
from .grounding_view_models import GroundingViewReport
from .import_review import build_import_review
from .import_review_models import ImportReviewReport
from .mcp_server_guardrails import import_path, service_operation
from .mcp_workflow_paths import fresh_output
from .measured_comparison import compare_measured_series
from .measured_comparison_models import MeasuredComparisonReport
from .measured_series import import_measured_series
from .measured_series_models import MeasuredSeriesReport
from .physical_voltage import build_physical_voltage_review
from .physical_voltage_models import PhysicalVoltageReviewReport
from .power_tree_view import build_power_tree_view
from .power_tree_view_models import PowerTreeViewReport
from .product_revision_bom import compare_product_revisions
from .product_revision_bom_models import ProductRevisionBomReport
from .product_variant_bom import compare_product_variants
from .product_variant_bom_models import ProductVariantBomReport
from .product_visual import build_product_visual
from .product_visual_models import ProductVisualReport
from .release_readiness_view import capture_release_readiness
from .release_readiness_view_models import ReleaseReadinessViewReport
from .review_handoff import export_review_handoff
from .review_handoff_models import ReviewHandoffReport
from .supplier_analysis import compare_supplier_snapshots
from .supplier_analysis_models import SupplierAnalysisReport
from .variant_parts_review import build_variant_parts_review
from .variant_parts_review_models import VariantPartsReviewReport
from .verification_history import compare_verification_history
from .verification_history_models import VerificationHistoryReport


def register_visualization_export_tools(
    server: MCPServer[None],
    root: Path,
    operation: Lock,
    create_only: ToolAnnotations,
    permitted_sources: tuple[Path, ...],
) -> None:
    """Bind fresh, ignored visualization receipts to the shared typed services."""

    def export_assembly_clearance(
        project_id: str,
        view_id: str,
        board_receipt: str,
        placement_contract: str,
        clearance_contract: str,
    ) -> AssemblyClearanceReport:
        """Measure retained board geometry to an authored rectangular free space."""
        with service_operation(operation):
            return build_assembly_clearance(
                root,
                project_id,
                Path(board_receipt),
                Path(placement_contract),
                Path(clearance_contract),
                fresh_output(root, "assembly-clearance", view_id),
            )

    server.tool(annotations=create_only)(export_assembly_clearance)

    def export_assembly_review(
        project_id: str, view_id: str, board_receipt: str, placement_contract: str
    ) -> AssemblyReviewReport:
        """Display a hash-bound board and positioned adjacent GLB offline."""
        with service_operation(operation):
            return build_assembly_review(
                root,
                project_id,
                Path(board_receipt),
                Path(placement_contract),
                fresh_output(root, "assembly-review", view_id),
            )

    server.tool(annotations=create_only)(export_assembly_review)

    def export_connectivity_view(receipt: str, net: str, view_id: str) -> ConnectivityViewReport:
        """Explore one exact observed net and its neighboring component terminals."""
        with service_operation(operation):
            return build_connectivity_view(
                root, Path(receipt), net, fresh_output(root, "connectivity-view", view_id)
            )

    server.tool(annotations=create_only)(export_connectivity_view)

    def export_findings_view(
        project_id: str, view_id: str, native_summary: str, lint_report: str | None = None
    ) -> FindingsViewReport:
        """Export an offline review of saved source-bound ERC, DRC, and optional lint evidence.

        This reads existing evidence, does not execute KiCad or lint, and keeps
        unmapped findings visible. Outputs use a fresh build/findings-view/view_id.
        """
        with service_operation(operation):
            return build_findings_view(
                root,
                project_id,
                Path(native_summary),
                fresh_output(root, "findings-view", view_id),
                None if lint_report is None else Path(lint_report),
            )

    server.tool(annotations=create_only)(export_findings_view)

    def compare_electrical_ac_runs(
        project_id: str,
        baseline: str,
        candidate: str,
        case_id: str,
        measure_id: str,
        view_id: str,
    ) -> AcComparisonReport:
        """Overlay one matching AC measurement from two saved analysis receipts."""
        with service_operation(operation):
            return compare_ac_runs(
                root,
                project_id,
                Path(baseline),
                Path(candidate),
                case_id,
                measure_id,
                fresh_output(root, "electrical-ac-comparison", view_id),
            )

    server.tool(annotations=create_only)(compare_electrical_ac_runs)

    def export_product_visual(
        product_id: str, variant_id: str, view_id: str
    ) -> ProductVisualReport:
        """Explore authored assembly, interface and harness links for one variant."""
        with service_operation(operation):
            return build_product_visual(
                root,
                product_id,
                variant_id,
                fresh_output(root, "product-visual", view_id),
            )

    server.tool(annotations=create_only)(export_product_visual)

    def compare_product_variant_bom(
        product_id: str, before_variant: str, after_variant: str, view_id: str
    ) -> ProductVariantBomReport:
        """Compare two authored variants using the canonical product BOM projection."""
        with service_operation(operation):
            return compare_product_variants(
                root,
                product_id,
                before_variant,
                after_variant,
                fresh_output(root, "product-variant-bom", view_id),
            )

    server.tool(annotations=create_only)(compare_product_variant_bom)

    def compare_product_revision_bom(
        baseline: str, candidate: str, view_id: str
    ) -> ProductRevisionBomReport:
        """Compare two explicitly saved product views across source revisions."""
        with service_operation(operation):
            return compare_product_revisions(
                root,
                Path(baseline),
                Path(candidate),
                fresh_output(root, "product-revision-bom", view_id),
            )

    server.tool(annotations=create_only)(compare_product_revision_bom)

    def export_verification_history(
        project_id: str,
        view_id: str,
        baseline: str,
        candidate: str,
        baseline_release: str | None = None,
        candidate_release: str | None = None,
        baseline_readiness: str | None = None,
        candidate_readiness: str | None = None,
    ) -> VerificationHistoryReport:
        """Compare two explicit saved overviews without rerunning checks or granting approval."""
        with service_operation(operation):
            return compare_verification_history(
                root,
                project_id,
                Path(baseline),
                Path(candidate),
                baseline_release=None if baseline_release is None else Path(baseline_release),
                candidate_release=None if candidate_release is None else Path(candidate_release),
                baseline_readiness=None if baseline_readiness is None else Path(baseline_readiness),
                candidate_readiness=None
                if candidate_readiness is None
                else Path(candidate_readiness),
                output=fresh_output(root, "verification-history", view_id),
            )

    server.tool(annotations=create_only)(export_verification_history)

    def export_release_readiness_view(manifest: str, view_id: str) -> ReleaseReadinessViewReport:
        """Save a source-linked result of one read-only release check."""
        with service_operation(operation):
            return capture_release_readiness(
                root, Path(manifest), fresh_output(root, "release-readiness-view", view_id)
            )

    server.tool(annotations=create_only)(export_release_readiness_view)

    def export_review_handoff_packet(
        project_id: str,
        view_id: str,
        baseline: str,
        candidate: str,
        notes: str,
        fingerprints: Sequence[str],
    ) -> ReviewHandoffReport:
        """Retain selected historical findings and attributed project-owned notes."""
        with service_operation(operation):
            return export_review_handoff(
                root,
                project_id,
                Path(baseline),
                Path(candidate),
                Path(notes),
                tuple(fingerprints),
                fresh_output(root, "review-handoff", view_id),
            )

    server.tool(annotations=create_only)(export_review_handoff_packet)

    def compare_supplier_offers(
        project_id: str,
        view_id: str,
        parts_receipt: str,
        before: str,
        after: str,
        as_of: str,
        max_age_days: int,
    ) -> SupplierAnalysisReport:
        """Compare two dated, manually captured supplier snapshots for one saved BOM."""
        with service_operation(operation):
            return compare_supplier_snapshots(
                root,
                project_id,
                Path(parts_receipt),
                Path(before),
                Path(after),
                date.fromisoformat(as_of),
                max_age_days,
                fresh_output(root, "supplier-analysis", view_id),
            )

    server.tool(annotations=create_only)(compare_supplier_offers)

    def export_import_review(
        source: str, project_id: str, toolchain_id: str, view_id: str
    ) -> ImportReviewReport:
        """Show one permitted import's files, dependencies, toolchain and repair actions."""
        with service_operation(operation):
            path = import_path(root, source, permitted_sources, require_project=False)
            return build_import_review(
                root,
                path,
                project_id,
                toolchain_id,
                fresh_output(root, "import-review", view_id),
            )

    server.tool(annotations=create_only)(export_import_review)

    def import_measured_time_series(
        project_id: str,
        view_id: str,
        source: str,
        time_column: str,
        time_unit: Literal["s", "ms", "us", "ns", "iso8601"],
        channels: Sequence[str],
    ) -> MeasuredSeriesReport:
        """Import project-owned CSV with explicit time and channel=unit mappings."""
        with service_operation(operation):
            return import_measured_series(
                root,
                project_id,
                Path(source),
                time_column,
                time_unit,
                tuple(channels),
                fresh_output(root, "measured-series", view_id),
            )

    server.tool(annotations=create_only)(import_measured_time_series)

    def compare_measured_runs(
        project_id: str,
        view_id: str,
        baseline: str,
        candidate: str,
        channel: str,
        alignment: Literal["absolute", "elapsed"],
    ) -> MeasuredComparisonReport:
        """Overlay two retained measurements with explicit time alignment."""
        with service_operation(operation):
            return compare_measured_series(
                root,
                project_id,
                Path(baseline),
                Path(candidate),
                channel,
                alignment,
                fresh_output(root, "measured-comparison", view_id),
            )

    server.tool(annotations=create_only)(compare_measured_runs)

    def export_physical_voltage_review(
        project_id: str,
        view_id: str,
        measured_receipt: str,
        capture: str,
        requirement: str | None = None,
    ) -> PhysicalVoltageReviewReport:
        """Compare one saved voltage channel with exact project-authored conditions and limits."""
        with service_operation(operation):
            return build_physical_voltage_review(
                root,
                project_id,
                Path(measured_receipt),
                Path(capture),
                None if requirement is None else Path(requirement),
                fresh_output(root, "physical-voltage", view_id),
            )

    server.tool(annotations=create_only)(export_physical_voltage_review)

    def compare_parts_bom(
        project_id: str, view_id: str, before: str, after: str
    ) -> BomComparisonReport:
        """Compare two explicit saved parts plans in a fresh offline review."""
        with service_operation(operation):
            return compare_bom(
                root,
                project_id,
                Path(before),
                Path(after),
                fresh_output(root, "bom-comparison", view_id),
            )

    server.tool(annotations=create_only)(compare_parts_bom)

    def compare_board_variants(
        project_id: str,
        view_id: str,
        findings_view: str,
        before_variant: str,
        after_variant: str,
    ) -> BoardVariantComparisonReport:
        """Compare two retained named schematic and PCB populations."""
        with service_operation(operation):
            return compare_native_board_variants(
                root,
                project_id,
                Path(findings_view),
                before_variant,
                after_variant,
                fresh_output(root, "board-variant-comparison", view_id),
            )

    server.tool(annotations=create_only)(compare_board_variants)

    def export_bom_cross_probe(
        project_id: str,
        view_id: str,
        parts_report: str,
        findings_view: str,
        assembly_variant: str | None = None,
    ) -> CrossProbeReport:
        """Locate fitted BOM references on verified saved design drawings."""
        with service_operation(operation):
            return build_cross_probe(
                root,
                project_id,
                Path(parts_report),
                Path(findings_view),
                fresh_output(root, "cross-probe", view_id),
                assembly_variant,
            )

    server.tool(annotations=create_only)(export_bom_cross_probe)

    def export_variant_parts_review(
        project_id: str,
        view_id: str,
        parts_report: str,
        findings_view: str,
        assembly_variant: str,
    ) -> VariantPartsReviewReport:
        """Reconcile one native board variant into a review BOM and drawing navigation."""
        with service_operation(operation):
            return build_variant_parts_review(
                root,
                project_id,
                Path(parts_report),
                Path(findings_view),
                assembly_variant,
                fresh_output(root, "variant-parts", view_id),
            )

    server.tool(annotations=create_only)(export_variant_parts_review)

    def export_grounding_view(view_id: str, receipt: str, net: str) -> GroundingViewReport:
        """Review one authored ground net against a saved, hash-bound observation."""
        with service_operation(operation):
            return build_grounding_view(
                root, Path(receipt), net, fresh_output(root, "grounding-view", view_id)
            )

    server.tool(annotations=create_only)(export_grounding_view)

    def export_power_tree_view(view_id: str, receipt: str, rail: str) -> PowerTreeViewReport:
        """Review one authored power rail and retained native pin membership."""
        with service_operation(operation):
            return build_power_tree_view(
                root, Path(receipt), rail, fresh_output(root, "power-tree-view", view_id)
            )

    server.tool(annotations=create_only)(export_power_tree_view)
