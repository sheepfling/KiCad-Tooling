"""Keep the cross-process report inventory pinned by the hash-seed probe."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow]

EXPECTED_REPORT_COUNT = 233


def test_hashseed_probe_report_inventory_is_complete() -> None:
    reports = hashseed_probe_reports()

    assert len(reports) == EXPECTED_REPORT_COUNT


@pytest.mark.catalog_lint
def test_backlog_documents_the_current_hashseed_report_inventory() -> None:
    backlog = (Path(__file__).parents[1] / "docs" / "DESIGN_LINT_BACKLOG.md").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"#### LINT-080 — Cross-process hash-seed determinism for lint reports\n"
        r"(?P<section>.*?)(?=\n#### LINT-|\Z)",
        backlog,
        flags=re.DOTALL,
    )
    assert match is not None, "Backlog must retain the LINT-080 record"
    inventory = re.search(r"complete (\d+)-report inventory gate", match.group("section"))
    assert inventory is not None, "LINT-080 must publish its complete report count"
    assert int(inventory.group(1)) == EXPECTED_REPORT_COUNT
