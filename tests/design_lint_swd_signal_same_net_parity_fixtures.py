"""Named CLI/MCP parity reference for the SWD signal-pair heuristic."""

from types import MappingProxyType

SWD_SIGNAL_SAME_NET_PARITY_FIXTURES = MappingProxyType(
    {
        "bus.swdio_swclk_same_net": MappingProxyType(
            {
                "fault_fixtures": (
                    "tests.test_design_lint_mcp_parity_swd_signal_same_net."
                    + "test_swd_signal_same_net_cli_mcp_parity",
                ),
            }
        ),
    }
)
