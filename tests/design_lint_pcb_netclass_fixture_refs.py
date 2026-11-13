"""CLI/MCP parity fixtures for conflicting PCB netclass settings."""

from types import MappingProxyType

PCB_NETCLASS_PARITY_FIXTURES = MappingProxyType(
    {
        "pcb.drc_netclass_pattern_unmatched": MappingProxyType(
            {
                "fault_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_netclass_pattern_unmatched"
                        ".test_netclass_pattern_review_matches_between_cli_and_mcp"
                    ),
                ),
                "valid_control_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_netclass_pattern_unmatched"
                        ".test_netclass_pattern_review_matches_between_cli_and_mcp"
                    ),
                ),
            }
        ),
        "pcb.drc_exact_netclass_scope_unmatched": MappingProxyType(
            {
                "fault_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_exact_netclass_scope"
                        ".test_unmatched_exact_netclass_scope_matches_between_cli_and_mcp"
                    ),
                ),
                "valid_control_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_exact_netclass_scope"
                        ".test_unmatched_exact_netclass_scope_matches_between_cli_and_mcp"
                    ),
                ),
            }
        ),
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
        "pcb.drc_unresolved_netclass_assignment": MappingProxyType(
            {
                "fault_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_unresolved_netclass_assignment"
                        ".test_unresolved_netclass_assignment_matches_between_cli_and_mcp"
                    ),
                ),
                "valid_control_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_unresolved_netclass_assignment"
                        ".test_unresolved_netclass_assignment_matches_between_cli_and_mcp"
                    ),
                ),
            }
        ),
        "pcb.drc_malformed_netclass_assignment": MappingProxyType(
            {
                "fault_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_malformed_netclass_assignment"
                        ".test_malformed_netclass_assignment_matches_between_cli_and_mcp"
                    ),
                ),
                "valid_control_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_malformed_netclass_assignment"
                        ".test_malformed_netclass_assignment_matches_between_cli_and_mcp"
                    ),
                ),
            }
        ),
        "pcb.drc_malformed_netclass_inventory": MappingProxyType(
            {
                "fault_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_malformed_netclass_inventory"
                        ".test_malformed_netclass_inventory_matches_between_cli_and_mcp"
                    ),
                ),
                "valid_control_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_malformed_netclass_inventory"
                        ".test_malformed_netclass_inventory_matches_between_cli_and_mcp"
                    ),
                ),
            }
        ),
        "pcb.drc_malformed_netclass_numeric_constraints": MappingProxyType(
            {
                "fault_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_malformed_netclass_numeric_constraints"
                        ".test_malformed_netclass_numeric_constraint_matches_between_cli_and_mcp"
                    ),
                ),
                "valid_control_fixtures": (
                    (
                        "tests.test_design_lint_mcp_parity_pcb_drc_malformed_netclass_numeric_constraints"
                        ".test_malformed_netclass_numeric_constraint_matches_between_cli_and_mcp"
                    ),
                ),
            }
        ),
    }
)
