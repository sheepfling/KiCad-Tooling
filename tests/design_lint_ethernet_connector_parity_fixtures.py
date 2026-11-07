"""Named CLI/MCP parity fixtures for Ethernet connector review rules."""

from types import MappingProxyType


def _refs(owner: str, *tests: str) -> tuple[str, ...]:
    return tuple(f"{owner}.{name}" for name in tests)


ETHERNET_CONNECTOR_PARITY_FIXTURES = MappingProxyType(
    {
        rule_id: MappingProxyType(
            {
                "fault_fixtures": _refs(module, function),
            }
        )
        for rule_id, module, function in (
            (
                "bus.ethernet_generic_connector_pair_review",
                "tests.test_design_lint_mcp_parity_ethernet_generic_connector",
                "test_ethernet_generic_connector_review_cli_mcp_parity",
            ),
            (
                "bus.ethernet_management_generic_connector_pair_review",
                "tests.test_design_lint_mcp_parity_ethernet_management_generic_connector",
                "test_ethernet_management_generic_connector_review_cli_mcp_parity",
            ),
        )
    }
)
