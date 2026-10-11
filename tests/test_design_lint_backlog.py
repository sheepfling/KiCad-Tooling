"""Keep the documented implemented-rule backlog aligned with the live catalog."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

BACKLOG = Path(__file__).resolve().parents[1] / "docs" / "DESIGN_LINT_BACKLOG.md"
SUMMARY = "The following "
BASELINE_END = "\nThis baseline catches"


@pytest.mark.design_lint
def test_backlog_baseline_lists_every_active_rule_once() -> None:
    text = BACKLOG.read_text(encoding="utf-8")
    summary = re.search(
        r"^The following (\d+) rules are implemented with synthetic regression coverage\.$",
        text,
        re.MULTILINE,
    )
    assert summary is not None, f"Missing implemented-rule summary beginning {SUMMARY!r}"
    end = text.find(BASELINE_END, summary.end())
    assert end >= 0, "Could not locate the end of the implemented-rule inventory"

    listed = re.findall(r"^- `([^`]+)`$", text[summary.end() : end], re.MULTILINE)
    active = {entry.rule_id for entry in rule_catalog().rules if entry.status == "active"}

    assert int(summary.group(1)) == len(active), (
        "Backlog rule count differs from the active catalog"
    )
    assert len(listed) == len(set(listed)), "Backlog inventory contains duplicate rule IDs"
    assert set(listed) == active, (
        f"Backlog inventory differs from the active catalog: "
        f"missing={sorted(active - set(listed))}, "
        f"stale={sorted(set(listed) - active)}"
    )
