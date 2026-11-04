"""Shared typed projection for source-bound named PCB population exports."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import CandidateEvidenceProjection
from .pcb_component_inventory_models import PcbVariantPopulationCoverage


def project_named_variant_population_evidence(
    variant: str | None,
    coverage: PcbVariantPopulationCoverage,
    *,
    rule_id: DesignLintRuleId,
) -> CandidateEvidenceProjection:
    """Project the exact paired export for a named variant, if one is available."""
    if variant is None:
        return CandidateEvidenceProjection(rule_id=rule_id, evidence={})
    exported = next((item for item in coverage.evidence if item.variant == variant), None)
    if exported is None:
        return CandidateEvidenceProjection(
            rule_id=rule_id,
            evidence={"variant": (variant,), "variant_evidence": ("unavailable",)},
        )
    return CandidateEvidenceProjection(
        rule_id=rule_id,
        evidence={
            "variant": (variant,),
            "variant_project_path": (
                () if coverage.project_path is None else (coverage.project_path,)
            ),
            "variant_project_sha256": (
                () if coverage.project_sha256 is None else (coverage.project_sha256,)
            ),
            "variant_schematic_path": (
                () if coverage.schematic_path is None else (coverage.schematic_path,)
            ),
            "variant_schematic_sha256": (
                () if coverage.schematic_sha256 is None else (coverage.schematic_sha256,)
            ),
            "variant_board_path": (() if coverage.board_path is None else (coverage.board_path,)),
            "variant_board_sha256": (
                () if coverage.board_sha256 is None else (coverage.board_sha256,)
            ),
            "variant_board_probe_path": (
                ()
                if coverage.board_variant_probe_path is None
                else (coverage.board_variant_probe_path,)
            ),
            "variant_board_probe_sha256": (
                ()
                if coverage.board_variant_probe_sha256 is None
                else (coverage.board_variant_probe_sha256,)
            ),
            "variant_board_request_path": (
                ()
                if coverage.board_variant_request_path is None
                else (coverage.board_variant_request_path,)
            ),
            "variant_board_request_sha256": (
                ()
                if coverage.board_variant_request_sha256 is None
                else (coverage.board_variant_request_sha256,)
            ),
            "variant_board_probe_command_path": (
                ()
                if coverage.board_variant_command_path is None
                else (coverage.board_variant_command_path,)
            ),
            "variant_board_probe_command_sha256": (
                ()
                if coverage.board_variant_command_sha256 is None
                else (coverage.board_variant_command_sha256,)
            ),
            "variant_kicad_version": (
                () if coverage.kicad_version is None else (coverage.kicad_version,)
            ),
            "variant_image": (() if coverage.image is None else (coverage.image,)),
            "variant_netlist_path": (exported.netlist_path,),
            "variant_netlist_sha256": (exported.netlist_sha256,),
            "variant_netlist_command_path": (exported.netlist_command_path,),
            "variant_netlist_command_sha256": (exported.netlist_command_sha256,),
            "variant_board_all_positions_path": (exported.board_all_positions_path,),
            "variant_board_all_positions_sha256": (exported.board_all_positions_sha256,),
            "variant_board_all_command_path": (exported.board_all_command_path,),
            "variant_board_all_command_sha256": (exported.board_all_command_sha256,),
            "variant_board_fitted_positions_path": (exported.board_fitted_positions_path,),
            "variant_board_fitted_positions_sha256": (exported.board_fitted_positions_sha256,),
            "variant_board_fitted_command_path": (exported.board_fitted_command_path,),
            "variant_board_fitted_command_sha256": (exported.board_fitted_command_sha256,),
        },
    )
