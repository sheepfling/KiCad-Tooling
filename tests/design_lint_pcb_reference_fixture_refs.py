"""CLI/MCP parity fixture references for exact PCB reference scope."""

from types import MappingProxyType

PCB_REFERENCE_PARITY_FIXTURES = MappingProxyType(
    {
        "pcb.drc_exact_reference_scope_unmatched": MappingProxyType(
            {
                "fault_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_exact_reference_scope"
                        ".test_unmatched_exact_reference_scope_matches_between_cli_and_mcp"
                    ),
                ),
                "valid_control_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_exact_reference_scope"
                        ".test_unmatched_exact_reference_scope_matches_between_cli_and_mcp"
                    ),
                ),
            }
        ),
        "pcb.drc_exact_reference_pad_scope_unmatched": MappingProxyType(
            {
                "fault_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_exact_reference_pad_scope"
                        ".test_unmatched_exact_reference_pad_scope_matches_between_cli_and_mcp"
                    ),
                ),
                "valid_control_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_exact_reference_pad_scope"
                        ".test_unmatched_exact_reference_pad_scope_matches_between_cli_and_mcp"
                    ),
                ),
            }
        ),
    }
)
