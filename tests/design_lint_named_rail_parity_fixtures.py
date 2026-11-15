"""Parity references for protocol-specific named-rail rules."""

from __future__ import annotations

from types import MappingProxyType

from tests.design_lint_fixture_ref_support import _refs

NAMED_RAIL_PARITY_FIXTURES = MappingProxyType(
    {
        "bus.jtag_signal_on_named_rail": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_jtag_signal_named_rail",
                    "test_jtag_signal_named_rail_cli_mcp_parity",
                ),
            }
        ),
        "bus.swd_signal_on_named_rail": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_swd_signal_named_rail",
                    "test_swd_signal_named_rail_cli_mcp_parity",
                ),
            }
        ),
    }
)
