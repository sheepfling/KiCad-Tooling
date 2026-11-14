"""CLI/MCP fixture references for switching-regulator loop-map coverage."""

from types import MappingProxyType

from tests.design_lint_fixture_ref_support import _refs

SWITCHING_REGULATOR_PARITY_FIXTURES = MappingProxyType(
    {
        "pcb.switching_regulator_loop_map_coverage": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_switching_regulator_loop_map",
                    "test_switching_regulator_loop_map_fault_and_control_match_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_switching_regulator_loop_map",
                    "test_switching_regulator_loop_map_fault_and_control_match_cli_and_mcp",
                ),
            }
        )
    }
)
