"""Expected markers for focused components lint suites."""

from types import MappingProxyType

PYTEST_NATIVE_LINT_SUITES = MappingProxyType(
    {
        "test_design_lint_mcp_parity_mosfet_gate.py": frozenset(
            {"component_lint", "parity_lint", "slow"}
        ),
        "test_design_lint_decoupling.py": frozenset({"component_lint", "power_lint"}),
        "test_design_lint_dc_reference.py": frozenset({"power_lint"}),
        "test_design_lint_determinism_power_connectivity.py": frozenset({"power_lint"}),
        "test_electrical_power_connectivity.py": frozenset({"power_lint"}),
        "test_regulator_feedback.py": frozenset({"power_lint"}),
        "test_regulator_feedback_native_fixture.py": frozenset(
            {"native_kicad", "power_lint", "slow"}
        ),
        "test_power_sequences.py": frozenset({"power_lint"}),
        "test_power_paths.py": frozenset({"power_lint"}),
        "test_power_sequence_fixture_lane.py": frozenset({"power_lint"}),
        "test_power_sequence_native_fixture_lane.py": frozenset({"power_lint"}),
        "test_electrical_component_evidence.py": frozenset({"component_lint", "evidence_lint"}),
        "test_mosfet_stress.py": frozenset({"component_lint"}),
        "test_mosfet_gate_connectivity.py": frozenset({"component_lint"}),
        "test_mosfet_gate_source_bias.py": frozenset({"component_lint"}),
        "test_mosfet_gate_direct_drive.py": frozenset({"component_lint"}),
        "test_mosfet_gate_native_fixture.py": frozenset({"component_lint", "native_kicad", "slow"}),
        "test_polarized_capacitor_native_fixture.py": frozenset(
            {"component_lint", "native_kicad", "slow"}
        ),
        "test_diode_rail_orientation_native_fixture.py": frozenset(
            {"component_lint", "native_kicad", "slow"}
        ),
        "test_mosfet_terminal_order_native_fixture.py": frozenset(
            {"component_lint", "native_kicad", "slow"}
        ),
        "test_mosfet_drain_source_same_net.py": frozenset({"component_lint"}),
        "test_mosfet_gate_source_same_net.py": frozenset({"component_lint"}),
        "test_mosfet_gate_drain_same_net.py": frozenset({"component_lint"}),
        "test_mosfet_drain_source_same_net_native_fixture.py": frozenset(
            {"component_lint", "native_kicad", "slow"}
        ),
        "test_design_lint_determinism_mosfet_drain_source.py": frozenset(
            {"component_lint", "slow"}
        ),
        "test_bjt_terminal_order_native_fixture.py": frozenset(
            {"component_lint", "native_kicad", "slow"}
        ),
        "test_bjt_base_emitter_same_net.py": frozenset({"component_lint"}),
        "test_bjt_base_collector_same_net.py": frozenset({"component_lint"}),
        "test_bjt_base_collector_same_net_native_fixture.py": frozenset(
            {"component_lint", "native_kicad", "slow"}
        ),
        "test_bjt_base_drive_native_fixture.py": frozenset(
            {"component_lint", "native_kicad", "slow"}
        ),
        "test_bjt_base_drive.py": frozenset({"component_lint"}),
        "test_bjt_base_bias.py": frozenset({"component_lint"}),
        "test_design_lint_determinism_bjt_base_bias.py": frozenset({"component_lint", "slow"}),
        "test_bjt_base_bias_native_fixture.py": frozenset(
            {"component_lint", "native_kicad", "slow"}
        ),
        "test_design_lint_led_topology.py": frozenset({"component_lint", "power_lint"}),
        "test_component_peer_pin_all_open.py": frozenset({"component_lint"}),
        "test_component_peer_pin_mixed_open.py": frozenset({"component_lint"}),
        "test_component_peer_pin_assignment_outlier.py": frozenset({"component_lint"}),
        "test_component_peer_pin_assignment_native_fixture_lane.py": frozenset({"component_lint"}),
        "test_component_named_peer_power_input_all_open.py": frozenset(
            {"component_lint", "power_lint"}
        ),
        "test_component_named_peer_power_input_all_open_native.py": frozenset(
            {"component_lint", "power_lint"}
        ),
        "test_design_lint_determinism_components.py": frozenset(
            {"component_lint", "power_lint", "return_path_lint"}
        ),
        "test_design_lint_mcp_parity_peer_pin_assignment_outlier.py": frozenset(
            {"component_lint", "parity_lint"}
        ),
    }
)
