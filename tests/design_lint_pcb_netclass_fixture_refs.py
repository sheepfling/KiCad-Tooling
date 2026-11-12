"""CLI/MCP parity fixtures for conflicting PCB netclass settings."""

from types import MappingProxyType

PCB_NETCLASS_PARITY_FIXTURES = MappingProxyType(
    {
        "pcb.drc_conflicting_netclass_definitions": MappingProxyType(
            {
                "fault_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_conflicting_netclass_definitions"
                        ".test_conflicting_netclass_review_matches_between_cli_and_mcp"
                    ),
                ),
            }
        ),
    }
)
