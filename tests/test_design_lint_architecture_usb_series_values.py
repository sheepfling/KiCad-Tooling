"""Keep USB series-value regressions focused and within the review size limit."""

from __future__ import annotations

import pytest

from tests.lint_architecture_support import TESTS, THEME_SUITE_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

USB_SERIES_VALUE_SUITES = (
    "test_usb_unmapped_series_resistor_values.py",
    "test_usb_unmapped_series_resistor_values_native.py",
    "test_design_lint_mcp_parity_usb_series_resistor_values.py",
)


def test_usb_series_value_suites_stay_below_review_limit() -> None:
    sizes = {name: line_count(TESTS / name) for name in USB_SERIES_VALUE_SUITES}

    assert all(size < THEME_SUITE_MAX_LINES for size in sizes.values()), sizes
