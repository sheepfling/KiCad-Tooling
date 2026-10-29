"""Component review filtering preserves purchasing and finding distinctions."""

from __future__ import annotations

import json
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

from kicad_tooling.hwrepo.models import (
    PartRecord,
    PartsCatalog,
    PartStatus,
    PurchasingComponent,
    PurchasingFinding,
    PurchasingPreferences,
    PurchasingReport,
)
from kicad_tooling.hwrepo.parts_view import SCRIPT, render_html
from kicad_tooling.hwrepo.purchasing import plan


class ChecklistParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, str]] = []
        self.inside_table = False
        self.row: dict[str, str] | None = None
        self.labels: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "label" and attributes.get("for"):
            self.labels.append(attributes["for"] or "")
        if tag == "table" and attributes.get("id") == "components":
            self.inside_table = True
        if tag == "tr" and self.inside_table and "data-grouping" in attributes:
            self.row = {
                "grouping": attributes["data-grouping"] or "",
                "issue": attributes["data-issue"] or "",
                "text": "",
                "links": "",
            }
        if tag == "a" and self.row is not None:
            self.row["links"] += attributes.get("href") or ""

    def handle_data(self, data: str) -> None:
        if self.row is not None:
            self.row["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if tag == "table" and self.inside_table:
            self.inside_table = False


def review(*, global_finding: bool = False, duplicates: bool = False) -> str:
    part = PartRecord(
        id="resistor",
        revision="A",
        description="Resistor",
        part_class="resistor",
        unit="each",
        manufacturer="Yageo",
        mpn="ABC1",
        datasheet_url="https://example.test/part",
        lifecycle="active",
        status=PartStatus.APPROVED,
    )
    components = tuple(
        PurchasingComponent(
            reference=reference,
            value="1k",
            footprint="R:0603",
            part_id=part_id,
            dnp=dnp,
        )
        for reference, part_id, dnp in (
            ("R1", "resistor", False),
            ("R2", None, False),
            ("R3", "resistor", True),
            ("R4", "resistor", False),
            ("R5", "resistor", True),
        )
    )
    if duplicates:
        components += (
            components[0].model_copy(update={"dnp": True}),
            components[1].model_copy(update={"part_id": "resistor"}),
        )
    purchase_plan = plan(
        components,
        PartsCatalog(schema_version="1", parts=(part,)),
        PurchasingPreferences(),
        ("resistor",),
    )
    # Findings can affect an existing group or an excluded reference independently.
    findings = purchase_plan.findings + (
        PurchasingFinding(
            code="GROUP_ISSUE", references=("R1",), message="Group issue", action="Review"
        ),
        PurchasingFinding(
            code="EXCLUDED_ISSUE", references=("R3",), message="Excluded issue", action="Review"
        ),
    )
    if global_finding:
        findings += (PurchasingFinding(code="GLOBAL", message="Global issue", action="Review"),)
    purchase_plan = purchase_plan.model_copy(update={"findings": findings})
    return render_html(
        PurchasingReport(
            project_id="example",
            status="NEEDS_PARTS",
            plan=purchase_plan,
            receipt_dir="build/parts",
        )
    )


def parse_review(*, global_finding: bool = False, duplicates: bool = False) -> ChecklistParser:
    parser = ChecklistParser()
    parser.feed(review(global_finding=global_finding, duplicates=duplicates))
    return parser


def test_checklist_grouping_and_findings_are_independent() -> None:
    parser = parse_review()
    assert "grouping" in parser.labels
    assert [(row["grouping"], row["issue"]) for row in parser.rows] == [
        ("grouped", "yes"),
        ("ungrouped", "yes"),
        ("excluded", "yes"),
        ("grouped", "no"),
        ("excluded", "no"),
    ]
    assert "Excluded from purchasing" in parser.rows[2]["text"]
    assert "Excluded issue" in parser.rows[2]["text"]
    global_rows = parse_review(global_finding=True).rows
    assert global_rows[3]["issue"] == "yes"
    assert "Resolve catalog / preferences above" in global_rows[3]["text"]
    assert global_rows[4]["issue"] == "no"


def test_duplicate_references_are_not_assigned_a_purchase_group() -> None:
    rows = parse_review(duplicates=True).rows
    r1 = [row for row in rows if row["text"].startswith("R1")]
    r2 = [row for row in rows if row["text"].startswith("R2")]
    assert [row["grouping"] for row in r1] == ["ambiguous", "excluded"]
    assert [row["grouping"] for row in r2] == ["ambiguous", "ambiguous"]
    for row in r1 + r2:
        assert row["issue"] == "yes"
        assert "Component reference appears more than once" in row["text"]
        assert row["links"] == ""
    assert "purchasing group membership is ambiguous" in r1[0]["text"]
    assert "Excluded from purchasing" in r1[1]["text"]


def test_filter_script_combines_search_group_and_findings() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to exercise the browser script")
    rows = parse_review().rows
    script = """
const assert = require('node:assert/strict');
const vm = require('node:vm');
const rows = ROWS.map(row => ({dataset: {grouping: row.grouping, issue: row.issue},
                               textContent: row.text, hidden: false}));
const makeInput = (value) => ({value, checked: false, listeners: {},
  addEventListener(type, listener) { this.listeners[type] = listener; }});
const elements = {search: makeInput(''), grouping: makeInput('all'),
  'issues-only': makeInput(''), 'row-count': {textContent: ''}};
const document = {getElementById: id => elements[id], querySelectorAll: () => rows};
vm.runInNewContext(SCRIPT, {document});
const visible = () => rows.filter(row => !row.hidden).map(row => row.textContent.slice(0, 2));
assert.deepEqual(visible(), ['R1', 'R2', 'R3', 'R4', 'R5']);
elements.grouping.value = 'grouped'; elements.grouping.listeners.change();
assert.deepEqual(visible(), ['R1', 'R4']);
elements['issues-only'].checked = true; elements['issues-only'].listeners.change();
assert.deepEqual(visible(), ['R1']);
elements.grouping.value = 'excluded'; elements.grouping.listeners.change();
assert.deepEqual(visible(), ['R3']);
elements.search.value = 'not-found'; elements.search.listeners.input();
assert.deepEqual(visible(), []);
assert.equal(elements['row-count'].textContent, 'No components match the current filters.');
elements.search.value = 'r2'; elements.grouping.value = 'ungrouped';
elements.search.listeners.input();
assert.deepEqual(visible(), ['R2']);
""".replace("ROWS", json.dumps(rows)).replace("SCRIPT", json.dumps(SCRIPT))
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
