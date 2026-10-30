"""Explicit pytest marker ownership by lint theme and catalogued rule."""

from __future__ import annotations

from collections import defaultdict
from types import MappingProxyType

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.design_lint_component_test_markers import COMPONENT_LINT_TEST_MODULES
from tests.design_lint_connector_test_markers import CONNECTOR_LINT_TEST_MODULES
from tests.design_lint_interface_test_markers import INTERFACE_LINT_TEST_MODULES
from tests.design_lint_pcb_test_markers import PCB_LINT_TEST_MODULES
from tests.design_lint_return_path_test_markers import RETURN_PATH_LINT_TEST_MODULES

# Keep the area catalog explicit. Adding a lint test module here also includes
# it in the portable design_lint selection derived below.
_LINT_AREA_MODULES = MappingProxyType(
    {
        "catalog_lint": frozenset(
            {
                "tests/test_design_lint_backlog.py",
                "tests/test_design_lint_catalog.py",
                "tests/test_design_lint_default_mode_policy.py",
                "tests/test_design_lint_catalog_fixtures.py",
                "tests/test_design_lint_catalog_reachability.py",
                "tests/test_design_lint_architecture_catalog.py",
                "tests/test_design_lint_field_maturity.py",
                "tests/test_design_lint_field_evidence_sources.py",
                "tests/test_design_lint_fixture_reachability.py",
                "tests/test_design_lint_architecture_theme_suites.py",
                "tests/test_design_lint_architecture_pcb_mechanical_edge.py",
                "tests/test_design_lint_native_gate_architecture.py",
                "tests/test_design_lint_native_fixture_inventory_architecture.py",
                "tests/test_design_lint_architecture_pytest_markers.py",
                "tests/test_design_lint_architecture_pytest_collection.py",
                "tests/test_design_lint_architecture_rule_selectors.py",
                "tests/test_design_lint_architecture_serial_endpoint_role_collision.py",
                "tests/test_design_lint_architecture_named_rail_protocols.py",
            }
        ),
        "schematic_lint": frozenset(
            {
                "tests/test_schematic_geometry_text.py",
                "tests/test_design_lint_schematic_text.py",
                "tests/test_schematic_geometry_symbol_body.py",
                "tests/test_schematic_geometry_symbol_arc_body.py",
                "tests/test_schematic_geometry_pin_proximity.py",
                "tests/test_schematic_geometry_wire_topology.py",
                "tests/test_schematic_geometry_hierarchy.py",
                "tests/test_schematic_geometry_native_text.py",
                "tests/test_schematic_geometry_native_wire_body.py",
                "tests/test_schematic_geometry_native_symbol_body.py",
                "tests/test_schematic_geometry_native_pin_connectivity.py",
                "tests/test_schematic_geometry_native_wire_topology.py",
                "tests/test_design_lint_clock_series_trial.py",
                "tests/test_design_lint_mcp_parity_schematic_connectivity.py",
                "tests/test_design_lint_mcp_parity_schematic_geometry.py",
                "tests/test_design_lint_mcp_parity_schematic_hierarchy.py",
            }
        ),
        "component_lint": COMPONENT_LINT_TEST_MODULES,
        "connector_lint": CONNECTOR_LINT_TEST_MODULES,
        "interface_lint": INTERFACE_LINT_TEST_MODULES,
        "power_lint": frozenset(
            {
                "tests/test_design_lint_control_input_arrays.py",
                "tests/test_connector_unconnected_power_output.py",
                "tests/test_design_lint_connector_power_pins.py",
                "tests/test_design_lint_connector_named_power_input_peers.py",
                "tests/test_connector_footprint_power_input.py",
                "tests/test_connector_footprint_power_output.py",
                "tests/test_design_lint_connector_named_power_output_peers.py",
                "tests/test_design_lint_mcp_parity_connector_named_power_peers.py",
                "tests/test_connector_named_power_input_native_fixture_lane.py",
                "tests/test_connector_footprint_named_power_input_native_fixture_lane.py",
                "tests/test_connector_footprint_named_power_input_all_open.py",
                "tests/test_connector_footprint_named_power_input_all_open_native_fixture_lane.py",
                "tests/test_connector_footprint_named_power_output_all_open.py",
                "tests/test_connector_footprint_named_power_output_all_open_native_fixture_lane.py",
                "tests/test_connector_footprint_named_power_output_divergence.py",
                "tests/test_connector_footprint_named_power_output_native_fixture_lane.py",
                "tests/test_connector_footprint_peer_parity.py",
                "tests/test_connector_footprint_same_voltage_power_input_parity.py",
                "tests/test_connector_named_power_output_native_fixture_lane.py",
                "tests/test_design_lint_mcp_parity_connector_power_output.py",
                "tests/test_component_unconnected_power_output.py",
                "tests/test_component_power_input_native_fixture_lane.py",
                "tests/test_design_lint_mcp_parity_unconnected_power_output.py",
                "tests/test_component_power_ratings.py",
                "tests/test_component_rating_native_fixture_lane.py",
                "tests/test_component_peer_power_fixture_lane.py",
                "tests/test_peer_power_assignment_symbol_groups.py",
                "tests/test_peer_power_assignment_part_id_groups.py",
                "tests/test_peer_power_assignment_cli_mcp.py",
                "tests/test_peer_power_assignment_native.py",
                "tests/test_component_named_peer_power_input_divergence.py",
                "tests/test_component_named_peer_power_input_all_open.py",
                "tests/test_component_named_peer_power_input_all_open_native.py",
                "tests/test_design_lint_determinism_component_peers.py",
                "tests/test_design_lint_determinism_power_input_peers.py",
                "tests/test_ci_hosted_component_peer_power.py",
                "tests/test_net_dc_reference_native_fixture_lane.py",
                "tests/test_design_lint_determinism_interfaces.py",
                "tests/test_design_lint_determinism_power_connectivity.py",
                "tests/test_design_lint_determinism_regulator.py",
                "tests/test_design_lint_mcp_parity_analog.py",
                "tests/test_design_lint_mcp_parity_components.py",
                "tests/test_design_lint_mcp_parity_peer_pins.py",
                "tests/test_design_lint_mcp_parity_power_input.py",
                "tests/test_connector_named_power_pin_fixture_lane.py",
                "tests/test_design_lint_mcp_parity_power_paths.py",
                "tests/test_design_lint_mcp_parity_protection.py",
                "tests/test_peer_power_output.py",
                "tests/test_hosted_power_path_requirements.py",
                "tests/test_power_path_fixture_lane.py",
                "tests/test_power_path_native_fixture_lane.py",
                "tests/test_power_paths.py",
                "tests/test_power_input_source_paths.py",
                "tests/test_power_input_source_anchors.py",
                "tests/test_power_input_policy.py",
                "tests/test_power_sequence_fixture_lane.py",
                "tests/test_power_sequence_native_fixture_lane.py",
                "tests/test_power_sequence_cycles.py",
                "tests/test_ic_rail_capacitor_native_fixture_lane.py",
                "tests/test_power_sequences.py",
                "tests/test_regulator_feedback.py",
                "tests/test_regulator_feedback_native_fixture.py",
                "tests/test_two_pin_fuses.py",
                "tests/test_two_pin_switches.py",
            }
        ),
        "evidence_lint": frozenset(
            {
                "tests/test_connector_fixture_lane_evidence.py",
                "tests/test_design_lint_connectivity_reconciliation.py",
                "tests/test_design_lint_connectivity_snapshot_inspection.py",
                "tests/test_design_lint_mcp_parity_reconciliation.py",
                "tests/test_contract_coach_capture.py",
                "tests/test_contract_coach_evidence.py",
                "tests/test_empty_netlist_evidence_native_fixture_lane.py",
                "tests/test_electrical_component_evidence.py",
                "tests/test_electrical_connector_evidence.py",
                "tests/test_electrical_pcb_return_evidence.py",
                "tests/test_electrical_test_access_evidence.py",
                "tests/test_electrical_test_access_parity.py",
            }
        ),
        "pcb_lint": PCB_LINT_TEST_MODULES,
        "return_path_lint": RETURN_PATH_LINT_TEST_MODULES,
        "parity_lint": frozenset(
            {
                "tests/test_design_lint_mcp_parity_connector_named_power_peers.py",
                "tests/test_design_lint_mcp_parity_peer_pin_assignment_outlier.py",
                "tests/test_connector_footprint_peer_parity.py",
                "tests/test_connector_footprint_peer_metadata_open.py",
                "tests/test_design_lint_mcp_parity_peer_pins.py",
                "tests/test_design_lint_mcp_parity_two_pin_varistors.py",
                "tests/test_design_lint_mcp_parity_two_pin_speakers.py",
                "tests/test_design_lint_mcp_parity_unconnected_power_output.py",
                "tests/test_design_lint_i2c_parity.py",
                "tests/test_design_lint_serial_parity.py",
                "tests/test_electrical_connector_return_parity.py",
                "tests/test_electrical_control_input_parity.py",
                "tests/test_electrical_power_connectivity_parity.py",
                "tests/test_electrical_rs485_parity.py",
                "tests/test_electrical_simulator_parity.py",
                "tests/test_electrical_test_access_parity.py",
                "tests/test_design_lint_mcp_parity_connector_returns.py",
                "tests/test_connector_peer_unanchored_scope.py",
                "tests/test_design_lint_mcp_parity_reconciliation.py",
                "tests/test_electrical_digital_peer_voltage_parity.py",
                "tests/test_electrical_component_rating_parity.py",
                "tests/test_electrical_connector_rating_parity.py",
                "tests/test_electrical_serial_peer_parity.py",
                "tests/test_electrical_parity.py",
                "tests/test_electrical_i2c_parity.py",
                "tests/test_electrical_usb_c_parity.py",
                "tests/test_design_lint_mcp_parity_usb_reference.py",
                "tests/test_design_lint_mcp_parity_usb_c_sbu_unconnected.py",
                "tests/test_design_lint_mcp_parity_i3c_unconnected.py",
                "tests/test_pcb_component_inventory_mcp_parity.py",
                "tests/test_pcb_keepouts_mcp_parity.py",
                "tests/test_pcb_rf_antenna_mcp_parity.py",
                "tests/test_pcb_touch_pad_clearance_mcp_parity.py",
                "tests/test_pcb_signal_path_mcp_parity.py",
                "tests/test_design_lint_mcp_parity_pcb_dru_rule_review.py",
                "tests/test_design_lint_mcp_parity_pcb_dru_severity_exclusion.py",
                "tests/test_design_lint_mcp_parity_pcb_drc_global_severity_review.py",
                "tests/test_design_lint_mcp_parity_pcb_drc_global_warning_review.py",
                "tests/test_design_lint_mcp_parity_pcb_drc_dfm_warning_review.py",
                "tests/test_design_lint_mcp_parity_pcb_drc_dfm_ignored_review.py",
                "tests/test_design_lint_mcp_parity_pcb_signal_integrity_drc_severity.py",
                "tests/test_design_lint_mcp_parity_pcb_miscellaneous_drc_severity.py",
                "tests/test_design_lint_mcp_parity_pcb_warning_default_drc_ignored.py",
                "tests/test_design_lint_mcp_parity_oscillator_output_paths.py",
                "tests/test_design_lint_mcp_parity_pcb_drc_exclusions.py",
            }
        ),
    }
)

_CORE_DESIGN_LINT_MODULES = frozenset(
    {
        "tests/test_design_lint_catalog.py",
        "tests/test_design_lint_determinism.py",
        "tests/test_electrical.py",
        "tests/test_empty_netlist_evidence_native_fixture_lane.py",
    }
)

_DESIGN_LINT_MODULES = _CORE_DESIGN_LINT_MODULES.union(
    *(modules for modules in _LINT_AREA_MODULES.values())
)


def design_lint_markers_for_path(path: str) -> tuple[str, ...]:
    """Return lint-scope markers assigned to one test module path."""
    markers: list[str] = []
    if path in _DESIGN_LINT_MODULES:
        markers.append("design_lint")
    markers.extend(marker for marker, paths in _LINT_AREA_MODULES.items() if path in paths)
    return tuple(markers)


def _test_reference(reference: str) -> tuple[str, str | None, str] | None:
    """Split a catalogued test reference into module, class, and function."""
    parts = reference.split(".")
    if len(parts) < 3 or parts[0] != "tests":
        return None
    module = ".".join(parts[:2])
    test_class = ".".join(parts[2:-1]) or None
    return module, test_class, parts[-1]


def _catalogued_test_rule_ids() -> dict[tuple[str, str | None, str], tuple[str, ...]]:
    references: dict[tuple[str, str | None, str], set[str]] = defaultdict(set)
    for rule in rule_catalog().rules:
        if rule.status != "active":
            continue
        fixture_references = (
            *rule.fault_fixtures,
            *rule.valid_control_fixtures,
            *rule.metamorphic_fixtures,
        )
        for reference in fixture_references:
            test_reference = _test_reference(reference)
            if test_reference is not None:
                references[test_reference].add(rule.rule_id)
    return {key: tuple(sorted(rule_ids)) for key, rule_ids in references.items()}


_RULE_IDS_BY_TEST = _catalogued_test_rule_ids()


def design_lint_rule_ids_for_test(
    module: str,
    test_class: str | None,
    function: str,
) -> tuple[str, ...]:
    """Return active rule IDs whose catalog names this pytest test."""
    exact = _RULE_IDS_BY_TEST.get((module, test_class, function))
    if exact is not None:
        return exact
    if test_class is not None:
        return _RULE_IDS_BY_TEST.get((module, None, function), ())
    return ()
