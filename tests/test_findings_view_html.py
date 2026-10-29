"""Findings explorer markup escapes evidence and keeps filtered markers navigable."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from kicad_tooling.hwrepo.findings_view_html import SCRIPT, render_findings_view
from kicad_tooling.hwrepo.findings_view_models import (
    FindingMarker,
    FindingsViewReport,
    ReviewFinding,
)


def test_finding_text_is_escaped() -> None:
    report = FindingsViewReport(
        project_id="demo",
        native_status="FAIL",
        lint_status="NOT_SUPPLIED",
        native_summary="build/native/summary.json",
        native_summary_sha256="0" * 64,
        source_hashes={},
        output_directory="build/findings-view/demo",
        findings=(
            ReviewFinding(
                origin="DRC",
                rule="clearance",
                severity="error",
                title="<script>alert('bad')</script>",
                description="<img src=x onerror=bad()>",
                markers=(FindingMarker(drawing="pcb", x_mm=1.0, y_mm=2.0),),
            ),
        ),
    )
    html = render_findings_view(report)
    assert "&lt;script&gt;alert(&#x27;bad&#x27;)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=bad()&gt;" in html
    assert "<img src=x onerror=bad()>" not in html


def test_filter_and_marker_restore_their_target() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to exercise the browser script")
    code = """
const assert = require('node:assert/strict');
const vm = require('node:vm');
const input = value => ({value, listeners:{}, addEventListener(k, f) {this.listeners[k] = f;}});
const search = input(''), origin = input('ALL'), count = {textContent:''};
const rows = [
  {id:'finding-1', dataset:{origin:'ERC'}, textContent:'pin ERC', hidden:false},
  {id:'finding-2', dataset:{origin:'DRC'}, textContent:'pad DRC', hidden:false}
];
const marker = {listeners:{}, addEventListener(k,f){this.listeners[k]=f;},
  getAttribute(){return '#finding-2';}};
const canvas = {dataset:{}, style:{}};
const zoomStatus = {textContent:'100%'};
const zoom = {dataset:{zoom:'in', target:'canvas-pcb.svg'}, listeners:{},
  addEventListener(k,f){this.listeners[k]=f;}};
const document = {
  getElementById(id){return ({'finding-search':search, 'finding-origin':origin,
    'finding-count':count, 'finding-1':rows[0], 'finding-2':rows[1],
    'canvas-pcb.svg':canvas, 'canvas-pcb.svg-status':zoomStatus})[id];},
  querySelectorAll(query){return query === '.finding' ? rows :
    query === '.drawing svg a' ? [marker] : [zoom];}
};
vm.runInNewContext(SCRIPT, {document});
origin.value = 'ERC'; origin.listeners.change();
assert.equal(rows[1].hidden, true);
assert.equal(count.textContent, '1 finding(s) shown');
marker.listeners.click();
assert.equal(origin.value, 'ALL');
assert.equal(rows[1].hidden, false);
zoom.listeners.click();
assert.equal(canvas.style.width, '150%');
assert.equal(zoomStatus.textContent, '150%');
zoom.dataset.zoom = 'reset'; zoom.listeners.click();
assert.equal(canvas.style.width, '100%');
search.value = 'missing'; search.listeners.input();
assert.equal(count.textContent, '0 finding(s) shown');
""".replace("SCRIPT", json.dumps(SCRIPT))
    result = subprocess.run([node, "-e", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
