"""Parity fixture references for PCB layout and route-coverage rules."""

from __future__ import annotations

from types import MappingProxyType

from tests.design_lint_fixture_ref_support import _refs

PCB_LAYOUT_PARITY_FIXTURES = MappingProxyType(
    {
        "pcb.keepout_intent_coverage": MappingProxyType(
            {
                "valid_control_fixtures": _refs(
                    "tests.test_pcb_keepouts_mcp_parity",
                    "test_disabled_keepout_coverage_matches_cli_and_mcp",
                ),
            }
        ),
        "pcb.rf_module_antenna_keepout_coverage": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_pcb_rf_antenna_mcp_parity",
                    "test_enabled_rf_antenna_fault_and_control_match_cli_and_mcp",
                ),
                "valid_control_fixtures": (
                    *_refs(
                        "tests.test_pcb_rf_antenna_mcp_parity",
                        "test_disabled_rf_antenna_coverage_matches_cli_and_mcp",
                    ),
                    *_refs(
                        "tests.test_pcb_rf_antenna_mcp_parity",
                        "test_enabled_rf_antenna_fault_and_control_match_cli_and_mcp",
                    ),
                ),
            }
        ),
        "pcb.signal_path_rule_coverage": MappingProxyType(
            {
                "valid_control_fixtures": _refs(
                    "tests.test_pcb_signal_path_mcp_parity",
                    "test_disabled_signal_path_coverage_matches_cli_and_mcp",
                ),
            }
        ),
        "pcb.differential_pair_route_skew": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_pcb_differential_pair_route_skew",
                    "test_excessive_routed_skew_is_reviewed_against_authored_bound",
                    "test_missing_member_route_is_incomplete_not_clean",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_pcb_differential_pair_route_skew",
                    "test_route_skew_at_authored_boundary_is_within_limit",
                    "test_equal_routes_are_within_zero_skew_bound",
                ),
            }
        ),
    }
)
