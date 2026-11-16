"""CLI/MCP parity fixture references for placed Reference field review."""

from types import MappingProxyType

from tests.design_lint_fixture_ref_support import _refs

PLACED_REFERENCE_PARITY_FIXTURES = MappingProxyType(
    {
        "schematic.conflicting_placed_reference_properties": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_schematic_conflicting_placed_reference",
                    "test_conflicting_placed_reference_review_matches_between_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_schematic_conflicting_placed_reference",
                    "test_conflicting_placed_reference_review_matches_between_cli_and_mcp",
                ),
            }
        ),
    }
)
