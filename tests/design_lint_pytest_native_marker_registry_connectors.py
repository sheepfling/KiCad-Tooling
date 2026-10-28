"""Expected markers for focused connectors lint suites."""

from types import MappingProxyType

PYTEST_NATIVE_LINT_SUITES = MappingProxyType(
    {
        "test_connector_supply_scope.py": frozenset({"connector_lint"}),
        "test_design_lint_policy.py": frozenset({"connector_lint", "return_path_lint"}),
        "test_electrical_connector_evidence.py": frozenset({"connector_lint", "evidence_lint"}),
        "test_electrical_connector_return_parity.py": frozenset(
            {"connector_lint", "parity_lint", "return_path_lint"}
        ),
        "test_pin_connectivity_acceptance.py": frozenset({"connector_lint"}),
        "test_connector_peer_pin_all_open.py": frozenset({"connector_lint"}),
        "test_design_lint_determinism_connector_all_open.py": frozenset({"connector_lint"}),
        "test_design_lint_connector_power_pins.py": frozenset({"connector_lint", "power_lint"}),
        "test_design_lint_connector_named_power_input_peers.py": frozenset(
            {"connector_lint", "power_lint"}
        ),
        "test_design_lint_connector_named_power_input_divergence.py": frozenset(
            {"connector_lint", "power_lint"}
        ),
        "test_design_lint_connector_named_power_output_peers.py": frozenset(
            {"connector_lint", "power_lint"}
        ),
        "test_design_lint_connector_named_power_output_divergence.py": frozenset(
            {"connector_lint", "power_lint"}
        ),
        "test_design_lint_mcp_parity_connector_named_power_peers.py": frozenset(
            {"connector_lint", "parity_lint", "power_lint"}
        ),
        "test_connector_named_power_input_native_fixture_lane.py": frozenset(
            {"connector_lint", "power_lint"}
        ),
        "test_connector_named_power_output_native_fixture_lane.py": frozenset(
            {"connector_lint", "power_lint"}
        ),
        "test_native_db9_return_contracts.py": frozenset({"connector_lint", "return_path_lint"}),
        "test_design_lint_determinism_component_peers.py": frozenset(
            {"component_lint", "connector_lint", "power_lint"}
        ),
    }
)
