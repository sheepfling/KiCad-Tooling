"""Catalog parity fixture references for unmapped edge-clearance rules."""

from __future__ import annotations

from types import MappingProxyType

from tests.design_lint_fixture_ref_support import _refs

PCB_SIGNAL_PATH_UNMAPPED_EDGE_CLEARANCE_PARITY_FIXTURES = MappingProxyType(
    {
        "pcb.signal_path_unmapped_edge_clearance_rule": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_signal_path_unmapped_edge_clearance",
                    "test_unmapped_edge_clearance_scope_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_signal_path_unmapped_edge_clearance",
                    "test_unmapped_edge_clearance_scope_matches_cli_and_mcp",
                ),
            }
        )
    }
)
