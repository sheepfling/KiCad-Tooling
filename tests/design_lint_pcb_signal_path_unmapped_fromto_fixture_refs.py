"""Catalog parity fixture references for omitted exact fromTo rules."""

from __future__ import annotations

from types import MappingProxyType

from tests.design_lint_fixture_ref_support import _refs

PCB_SIGNAL_PATH_UNMAPPED_FROM_TO_PARITY_FIXTURES = MappingProxyType(
    {
        "pcb.signal_path_unmapped_from_to_length_rule": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_signal_path_unmapped_fromto",
                    "test_unmapped_exact_from_to_length_scope_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_signal_path_unmapped_fromto",
                    "test_unmapped_exact_from_to_length_scope_matches_cli_and_mcp",
                ),
            }
        )
    }
)
