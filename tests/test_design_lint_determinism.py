"""Keep the cross-process report inventory pinned by the hash-seed probe."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow]

EXPECTED_REPORT_COUNT = 140


def test_hashseed_probe_report_inventory_is_complete() -> None:
    reports = hashseed_probe_reports()

    assert len(reports) == EXPECTED_REPORT_COUNT
