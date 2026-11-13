"""Catalog parity references for omitted signal-path rule coverage."""

from __future__ import annotations

from types import MappingProxyType

from tests.design_lint_fixture_ref_support import _refs

PCB_SIGNAL_PATH_UNMAPPED_PARITY_FIXTURES = MappingProxyType(
    {
        "pcb.signal_path_unmapped_native_rule": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_signal_path_unmapped",
                    "test_unmapped_exact_length_scope_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_signal_path_unmapped",
                    "test_unmapped_exact_length_scope_matches_cli_and_mcp",
                ),
            }
        )
    }
)
