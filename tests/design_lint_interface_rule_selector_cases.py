"""Focused selectors for interface lint regressions."""

from __future__ import annotations

INTERFACE_RULE_NODE_CASES = (
    (
        "bus.can_rx_outputs_share_net",
        (
            "tests/test_can_rx_output_sharing.py::"
            "test_multiple_fitted_can_receiver_outputs_on_one_net_are_reviewed"
        ),
    ),
)
