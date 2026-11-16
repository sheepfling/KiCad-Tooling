"""CLI/MCP parity fixture references for placed-symbol property reviews."""

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
        "schematic.conflicting_placed_datasheet_properties": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_schematic_conflicting_placed_datasheet",
                    "test_conflicting_placed_datasheet_review_matches_between_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_schematic_conflicting_placed_datasheet",
                    "test_conflicting_placed_datasheet_review_matches_between_cli_and_mcp",
                ),
            }
        ),
        "schematic.conflicting_placed_custom_properties": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_schematic_conflicting_placed_custom_properties",
                    "test_conflicting_placed_custom_property_review_matches_between_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_schematic_conflicting_placed_custom_properties",
                    "test_conflicting_placed_custom_property_review_matches_between_cli_and_mcp",
                ),
            }
        ),
    }
)
