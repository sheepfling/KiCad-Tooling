"""Focused selectors for interface lint regressions."""

from __future__ import annotations

INTERFACE_RULE_NODE_CASES = (
    (
        "bus.i2s_data_outputs_share_net",
        (
            "tests/test_i2s_data_output_sharing.py::"
            "test_multiple_fitted_i2s_data_outputs_form_a_configurable_review_candidate"
        ),
    ),
    (
        "bus.can_rx_outputs_share_net",
        (
            "tests/test_can_rx_output_sharing.py::"
            "test_multiple_fitted_can_receiver_outputs_on_one_net_are_reviewed"
        ),
    ),
)
