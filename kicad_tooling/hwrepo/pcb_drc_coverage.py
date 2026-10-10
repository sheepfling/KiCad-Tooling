"""Compatibility facade for PCB DRC requirement coverage."""

from __future__ import annotations

from .pcb_drc_rule_coverage import compare_native_rules, compare_native_signal_path_rules
from .pcb_drc_rule_parser import NativePcbDrcFixtureReport, read_native_pcb_drc_fixture_report
from .pcb_drc_source_scan import scan_source_bound_rule_map, scan_source_bound_signal_path_map

__all__ = [
    "NativePcbDrcFixtureReport",
    "compare_native_rules",
    "compare_native_signal_path_rules",
    "read_native_pcb_drc_fixture_report",
    "scan_source_bound_rule_map",
    "scan_source_bound_signal_path_map",
]
