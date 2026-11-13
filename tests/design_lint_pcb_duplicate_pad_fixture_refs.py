"""CLI/MCP parity fixture references for duplicate PCB pad net conflicts."""

from __future__ import annotations

from types import MappingProxyType


def _refs(owner: str, test: str) -> tuple[str, ...]:
    return (f"{owner}.{test}",)


PCB_DUPLICATE_PAD_PARITY_FIXTURES = MappingProxyType(
    {
        "pcb.duplicate_pad_net_conflict": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_duplicate_pad_net_conflict",
                    "test_duplicate_pad_net_conflict_matches_between_cli_and_mcp",
                ),
            }
        )
    }
)
