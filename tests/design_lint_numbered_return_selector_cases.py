"""Focused pytest nodes for the numbered-return rule selector."""

from __future__ import annotations

NUMBERED_RETURN_RULE_NODE_CASES = (
    (
        "net.numbered_returns",
        "tests/test_numbered_interface_returns.py::test_usb_and_serial_port_returns_are_grouped_by_protocol_stem",
    ),
    (
        "net.numbered_returns",
        "tests/test_protocol_return_name_groups.py::test_compact_can_i2c_and_spi_return_families_are_reviewed_separately",
    ),
    (
        "net.numbered_returns",
        "tests/test_protocol_return_name_groups.py::test_generic_numbered_identifier_prefixes_are_reviewed",
    ),
    (
        "net.numbered_returns",
        "tests/test_protocol_return_name_groups.py::test_delimited_ascii_identifier_prefixes_are_reviewed",
    ),
    (
        "net.numbered_returns",
        "tests/test_protocol_return_name_groups.py::test_base_and_numbered_return_sibling_are_reviewed",
    ),
    (
        "net.numbered_returns",
        "tests/test_protocol_return_name_groups.py::test_mixed_base_and_numbered_return_unlike_stem_is_a_valid_control",
    ),
    (
        "net.numbered_returns",
        "tests/test_protocol_return_name_groups.py::test_mixed_base_return_evidence_is_stable_under_mapping_reordering",
    ),
    (
        "net.numbered_returns",
        "tests/test_design_lint_mcp_parity_return_labels.py::test_ret_return_names_match_cli_and_mcp",
    ),
    (
        "net.numbered_returns",
        "tests/test_numbered_return_native_fixture_lane.py::test_native_ret_return_label_fault_and_control_are_focused_and_repeatable",
    ),
)
