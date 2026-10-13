"""Capture source-bound PCB inventory and optional named-variant evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence, PcbRuleMode
from .design_lint_policy_models import DesignLintPolicy
from .discovery import ProjectConfig
from .models import ContractCoachReport
from .pcb_component_inventory import evaluate_native_component_inventory_coverage
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_required_fitted_reference_models import PcbRequiredFittedReferenceMap
from .pcb_variant_population_capture import capture_variant_population


@dataclass(frozen=True)
class PcbComponentInventoryRuleModes:
    """Resolved project modes for checks sharing one native footprint snapshot."""

    inventory: PcbRuleMode
    population: PcbRuleMode
    value: PcbRuleMode
    pad_net: PcbRuleMode
    board_only: PcbRuleMode
    required_fitted_reference: PcbRuleMode

    @property
    def scan_mode(self) -> PcbRuleMode:
        selected: PcbRuleMode | None = next(
            (mode for mode in self.as_tuple if mode != "off"),
            None,
        )
        return "off" if selected is None else selected

    @property
    def required(self) -> bool:
        return any(mode != "off" for mode in self.as_tuple)

    @property
    def as_tuple(self) -> tuple[PcbRuleMode, ...]:
        return (
            self.inventory,
            self.population,
            self.value,
            self.pad_net,
            self.board_only,
            self.required_fitted_reference,
        )


def resolve_pcb_component_inventory_modes(
    policy: DesignLintPolicy,
) -> PcbComponentInventoryRuleModes:
    """Resolve defaults and explicit overrides for PCB inventory subrules."""
    overrides = {item.rule_id: item for item in policy.rules}

    def selected(rule_id: str, default: PcbRuleMode) -> PcbRuleMode:
        override = overrides.get(rule_id)
        return default if override is None else override.mode

    required_map = policy.pcb_required_fitted_reference_map
    required_override = overrides.get("pcb.required_fitted_reference")
    required_default: PcbRuleMode = "off" if required_map is None else "block"
    required_mode = required_default if required_override is None else required_override.mode
    return PcbComponentInventoryRuleModes(
        inventory=selected("pcb.schematic_component_inventory", "review"),
        population=selected("pcb.schematic_pcb_dnp_mismatch", "review"),
        value=selected("pcb.schematic_pcb_value_mismatch", "review"),
        pad_net=selected("pcb.schematic_pcb_pad_net_mismatch", "review"),
        board_only=selected("pcb.board_only_footprint", "off"),
        required_fitted_reference=required_mode,
    )


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
    required_fitted_reference_map: PcbRequiredFittedReferenceMap | None = None,
    required_fitted_reference_mode: PcbRuleMode = "off",
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
        required_fitted_reference_map=required_fitted_reference_map,
        required_fitted_reference_mode=required_fitted_reference_mode,
        variant_population=variant_population,
    )
