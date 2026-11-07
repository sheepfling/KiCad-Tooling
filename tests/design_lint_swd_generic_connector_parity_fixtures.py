"""Named CLI/MCP parity fixtures for the SWD generic connector review rule."""

from types import MappingProxyType


def _ref(module: str, function: str) -> str:
    return f"{module}.{function}"


SWD_GENERIC_CONNECTOR_PARITY_FIXTURES = MappingProxyType(
    {
        "connector.swd_pair_without_return_review": MappingProxyType(
            {
                "fault_fixtures": (
                    _ref(
                        "tests.test_design_lint_mcp_parity_swd_generic_connector",
                        "test_swd_connector_return_review_cli_mcp_parity",
                    ),
                ),
                "valid_control_fixtures": (
                    _ref(
                        "tests.test_design_lint_mcp_parity_swd_generic_connector",
                        "test_swd_connector_return_control_cli_mcp_parity",
                    ),
                ),
            }
        ),
        "bus.swd_generic_connector_pair_review": MappingProxyType(
            {
                "fault_fixtures": (
                    _ref(
                        "tests.test_design_lint_mcp_parity_swd_generic_connector",
                        "test_swd_generic_connector_review_cli_mcp_parity",
                    ),
                ),
            }
        ),
    }
)
