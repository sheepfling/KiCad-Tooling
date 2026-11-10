"""Keep active catalog-linked backlog entries explicitly statused."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint]

_ENTRY_HEADING = re.compile(r"(?m)^#### LINT-\d+ .*?$")
_RULE_FIELD = re.compile(r"(?ms)^- \*\*Rule:\*\*(.*?)(?=^- \*\*|\Z)")
_RULE_ID = re.compile(r"`([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)`")
_STATUS_FIELD = re.compile(r"(?m)^- \*\*Status:\*\*\s*\S")


def _entries(markdown: str) -> tuple[str, ...]:
    headings = tuple(_ENTRY_HEADING.finditer(markdown))
    return tuple(
        markdown[
            heading.start() : headings[index + 1].start() if index + 1 < len(headings) else None
        ]
        for index, heading in enumerate(headings)
    )


def _linked_rule_ids(entry: str) -> frozenset[str]:
    return frozenset(
        rule_id
        for rule_field in _RULE_FIELD.findall(entry)
        for rule_id in _RULE_ID.findall(rule_field)
    )


def _missing_statuses(markdown: str, active_rule_ids: set[str]) -> tuple[str, ...]:
    missing: list[str] = []
    for entry in _entries(markdown):
        linked_active_rules = _linked_rule_ids(entry) & active_rule_ids
        if linked_active_rules and not _STATUS_FIELD.search(entry):
            heading = entry.splitlines()[0]
            missing.extend(f"{heading}: {rule_id}" for rule_id in sorted(linked_active_rules))
    return tuple(missing)


def test_rule_link_parser_ignores_rule_ids_in_explanatory_prose() -> None:
    entry = """#### LINT-999 — Example
- **Rule:** `bus.spi_generic_connector_triad_review`, default `review`.
- **Gap:** See `bus.i2c_address_collision` for the separate address check.
"""

    assert _linked_rule_ids(entry) == {"bus.spi_generic_connector_triad_review"}


def test_active_rule_status_gap_requires_an_explicit_field() -> None:
    rule_id = "bus.spi_generic_connector_triad_review"
    proposed = f"""#### LINT-999 — Example
- **Rule:** `{rule_id}`, default `review`.
- **Gap:** See `bus.i2c_address_collision` for the separate address check.
"""
    planned = proposed.replace("- **Rule:**", "- **Status:** In progress\n- **Rule:**", 1)
    prose_only = proposed.replace(
        f"- **Rule:** `{rule_id}`, default `review`.",
        "- **Purpose:** Review the connector relationship.",
        1,
    )

    assert _missing_statuses(proposed, {rule_id}) == (f"#### LINT-999 — Example: {rule_id}",)
    assert _missing_statuses(planned, {rule_id}) == ()
    assert _missing_statuses(prose_only, {rule_id}) == ()


def test_active_catalog_rule_entries_declare_backlog_status() -> None:
    catalog = rule_catalog()
    active_rule_ids = {rule.rule_id for rule in catalog.rules if rule.status == "active"}
    backlog_path = Path(__file__).resolve().parents[1] / "docs/DESIGN_LINT_BACKLOG.md"
    missing = _missing_statuses(backlog_path.read_text(encoding="utf-8"), active_rule_ids)

    assert not missing, (
        "Backlog entries linking active design-lint rules need an explicit "
        "status field; statuses distinguish implemented coverage from proposed "
        "work. Missing: " + "; ".join(missing)
    )
