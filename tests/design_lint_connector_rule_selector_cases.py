"""Focused connector-only entries for rule selector architecture tests."""

from __future__ import annotations

CONNECTOR_RULE_NODE_CASES = (
    (
        "connector.reviewed_peer_passive_power_input_open",
        "tests/test_connector_reviewed_peer_power_input_split.py::test_unassigned_passive_power_input_peer_contact_needs_review",
    ),
    (
        "connector.reviewed_peer_passive_power_input_open",
        "tests/test_connector_reviewed_peer_power_input_split.py::test_documented_or_unmatched_passive_peer_opens_stay_quiet",
    ),
    (
        "connector.reviewed_peer_passive_power_input_open",
        "tests/test_connector_reviewed_peer_power_input_split.py::test_passive_peer_open_candidate_is_stable_under_mapping_order",
    ),
    (
        "connector.reviewed_peer_passive_power_input_open",
        "tests/test_connector_reviewed_peer_power_input_split.py::test_reviewed_peer_passive_open_obeys_policy_and_exact_ignore",
    ),
    (
        "connector.reviewed_peer_passive_power_input_open",
        "tests/test_connector_reviewed_peer_power_input_parity.py::test_reviewed_peer_power_input_split_matches_between_cli_and_mcp",
    ),
    (
        "connector.reviewed_peer_passive_power_input_open",
        "tests/test_connector_reviewed_peer_power_input_native.py::test_native_reviewed_peer_power_input_fault_and_control_are_repeatable",
    ),
)
