"""Parity fixture references for differential-pair PCB lint rules."""

from __future__ import annotations

from types import MappingProxyType

from tests.design_lint_fixture_ref_support import _refs

PCB_DIFFERENTIAL_PAIR_PARITY_FIXTURES = MappingProxyType(
    {
        "pcb.differential_pair_unmapped_native_rule": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_pairs",
                    "test_pcb_differential_pair_rule_coverage_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_pairs",
                    "test_pcb_differential_pair_rule_coverage_parity",
                ),
            }
        ),
        "pcb.differential_pair_reference_plane_scope_missing": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_pairs",
                    "test_pcb_differential_pair_rule_coverage_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_pcb_pairs",
                    "test_pcb_differential_pair_rule_coverage_parity",
                ),
            }
        ),
    }
)
