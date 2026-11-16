"""CLI/MCP parity fixture references for the reserved DNP-property rule."""

from types import MappingProxyType

from tests.design_lint_fixture_ref_support import _refs

RESERVED_DNP_PROPERTY_PARITY_FIXTURES = MappingProxyType(
    {
        "schematic.reserved_dnp_property_collision": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_schematic_reserved_dnp_property",
                    "test_reserved_dnp_property_review_matches_between_cli_and_mcp",
                ),
            }
        ),
    }
)
