"""Capture source-bound PCB inventory and optional named-variant evidence."""

from __future__ import annotations

from pathlib import Path

from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence, PcbRuleMode
from .discovery import ProjectConfig
from .models import ContractCoachReport
from .pcb_component_inventory import evaluate_native_component_inventory_coverage
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_variant_population_capture import capture_variant_population


def scan_pcb_component_inventory(
    root: Path,
    config: ProjectConfig,
    coach: ContractCoachReport,
    evidence: PcbGeometrySourceEvidence,
    output: Path,
    *,
    inventory_mode: PcbRuleMode,
    population_mode: PcbRuleMode,
    value_mode: PcbRuleMode,
    pad_net_mode: PcbRuleMode,
    board_only_mode: PcbRuleMode = "off",
) -> PcbComponentInventoryCoverageReport:
    """Compare inventory evidence and capture named variants when enabled."""
    variant_population = (
        capture_variant_population(
            root,
            config,
            output / "variant-population",
            expected_source_hashes=coach.source_hashes,
            kicad_version=evidence.snapshot.kicad_version,
        )
        if population_mode != "off"
        else None
    )
    return evaluate_native_component_inventory_coverage(
        coach.observed,
        evidence.snapshot,
        mode=inventory_mode,
        netlist_sha256=coach.netlist_sha256,
        board_path=evidence.board_path,
        board_sha256=evidence.board_sha256,
        snapshot_path=evidence.snapshot_relative_path,
        snapshot_sha256=evidence.snapshot_sha256,
        probe_sha256=evidence.probe_sha256,
        value_mode=value_mode,
        pad_net_mode=pad_net_mode,
        board_only_mode=board_only_mode,
        variant_population=variant_population,
    )
