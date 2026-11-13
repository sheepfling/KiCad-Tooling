"""Resolve modes and capture requirements for the shared PCB geometry scan."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_pcb_component_inventory_scan import (
    PcbComponentInventoryRuleModes,
    resolve_pcb_component_inventory_modes,
)
from .design_lint_pcb_coverage_common import PcbRuleMode
from .design_lint_pcb_route_skew_scan import route_measurement_enabled
from .design_lint_policy_models import DesignLintPolicy
from .project_models import ProjectConfig, ProjectKind


@dataclass(frozen=True, slots=True)
class PcbGeometryScanModes:
    """Selected rule severities and evidence demand for one geometry scan."""

    inventory_modes: PcbComponentInventoryRuleModes
    inventory_required: bool
    rules: dict[str, PcbRuleMode]
    disabled: dict[str, bool]
    route_measurement_active: bool


def resolve_pcb_geometry_scan_modes(
    config: ProjectConfig, policy: DesignLintPolicy
) -> PcbGeometryScanModes:
    """Keep project overrides, defaults, and evidence-demand flags in one owner."""
    overrides = {item.rule_id: item for item in policy.rules}

    def selected(rule_id: str, default: PcbRuleMode = "review") -> PcbRuleMode:
        override = overrides.get(rule_id)
        return default if override is None else override.mode

    inventory = resolve_pcb_component_inventory_modes(policy)
    inventory_required = config.kind is ProjectKind.PCB and inventory.required
    route_measurement_active = route_measurement_enabled(policy)
    rules: dict[str, PcbRuleMode] = {
        "pcb.decoupling_proximity": selected("pcb.decoupling_proximity"),
        "pcb.protection_entry_path": selected("pcb.protection_entry_path"),
        "pcb.minimum_track_width": selected("pcb.minimum_track_width"),
        "pcb.reference_plane_coverage": selected("pcb.reference_plane_coverage"),
        "pcb.switching_loop_geometry": selected("pcb.switching_loop_geometry"),
        "pcb.signal_path_rule_coverage": selected("pcb.signal_path_rule_coverage"),
        "pcb.keepout_intent_coverage": selected("pcb.keepout_intent_coverage"),
        "pcb.rf_module_antenna_keepout_coverage": selected(
            "pcb.rf_module_antenna_keepout_coverage"
        ),
        "pcb.touch_pad_reference_clearance": selected("pcb.touch_pad_reference_clearance"),
        "pcb.thermal_via_coverage": selected("pcb.thermal_via_coverage"),
        "pcb.fiducial_count": selected("pcb.fiducial_count"),
        "pcb.schematic_component_inventory": inventory.inventory,
        "pcb.schematic_pcb_dnp_mismatch": inventory.population,
        "pcb.schematic_pcb_value_mismatch": inventory.value,
        "pcb.schematic_pcb_pad_net_mismatch": inventory.pad_net,
        "pcb.board_only_footprint": inventory.board_only,
        "pcb.required_fitted_reference": inventory.required_fitted_reference,
    }
    configured = {
        "decoupling": policy.pcb_decoupling_map,
        "protection_path": policy.pcb_protection_path_map,
        "track_width": policy.pcb_track_width_map,
        "reference_plane": policy.pcb_reference_plane_map,
        "switching_loop": policy.pcb_switching_loop_map,
        "signal_path": policy.pcb_signal_path_rule_map,
        "keepout": policy.pcb_keepout_map,
        "rf_antenna": policy.pcb_rf_module_antenna_map,
        "touch_pad_clearance": policy.pcb_touch_pad_clearance_map,
        "thermal_via": policy.pcb_thermal_via_map,
        "fiducial": policy.pcb_fiducial_map,
    }
    disabled = {
        name: mapping is None or rules[rule_id] == "off"
        for name, mapping, rule_id in (
            ("decoupling", configured["decoupling"], "pcb.decoupling_proximity"),
            ("protection_path", configured["protection_path"], "pcb.protection_entry_path"),
            ("track_width", configured["track_width"], "pcb.minimum_track_width"),
            ("reference_plane", configured["reference_plane"], "pcb.reference_plane_coverage"),
            ("switching_loop", configured["switching_loop"], "pcb.switching_loop_geometry"),
            ("signal_path", configured["signal_path"], "pcb.signal_path_rule_coverage"),
            ("keepout", configured["keepout"], "pcb.keepout_intent_coverage"),
            (
                "rf_antenna",
                configured["rf_antenna"],
                "pcb.rf_module_antenna_keepout_coverage",
            ),
            (
                "touch_pad_clearance",
                configured["touch_pad_clearance"],
                "pcb.touch_pad_reference_clearance",
            ),
            ("thermal_via", configured["thermal_via"], "pcb.thermal_via_coverage"),
            ("fiducial", configured["fiducial"], "pcb.fiducial_count"),
        )
    }
    disabled["inventory"] = not inventory_required
    return PcbGeometryScanModes(
        inventory_modes=inventory,
        inventory_required=inventory_required,
        rules=rules,
        disabled=disabled,
        route_measurement_active=route_measurement_active,
    )
