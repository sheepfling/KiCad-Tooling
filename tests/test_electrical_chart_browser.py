"""Opt-in browser check for the self-contained waveform controls."""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.electrical_chart_interactive import (
    InteractiveTrace,
    render_interactive_chart,
)

pytestmark = pytest.mark.slow


def test_offline_waveform_cursor_trace_and_unit_controls(tmp_path: Path) -> None:
    browser_name = os.environ.get("KICAD_VIEWER_BROWSER")
    if not browser_name:
        pytest.skip("Set KICAD_VIEWER_BROWSER to a Chrome-family browser executable")
    browser = Path(browser_name)
    assert browser.is_file()
    traces = (
        InteractiveTrace(
            "baseline",
            "Baseline",
            "dB",
            (1.0, 10.0, 100.0),
            (0.0, -1.0, -3.0),
            (0.0, -30.0, -45.0),
            1.0,
            100.0,
            "min",
            -3.0,
            0.0,
        ),
        InteractiveTrace(
            "candidate",
            "Candidate",
            "dB",
            (1.0, 10.0, 100.0),
            (0.0, -0.5, -2.0),
            (0.0, -20.0, -40.0),
            1.0,
            100.0,
            "min",
            -3.0,
            0.0,
        ),
        InteractiveTrace(
            "current",
            "Current",
            "A",
            (1.0, 10.0, 100.0),
            (0.1, 0.2, 0.3),
            None,
            1.0,
            100.0,
            "max",
            None,
            0.5,
        ),
    )
    page = render_interactive_chart(
        "Offline AC probe", "frequency", traces, (("Source", "saved ngspice"),), ()
    )
    probe = """<script>try {
const chart=document.getElementById('value-plot'),box=chart.getBoundingClientRect();
const paths=()=>chart.querySelectorAll('path').length;
const initial={valuePaths:paths(),phasePaths:document.getElementById('phase-plot').querySelectorAll('path').length};
chart.dispatchEvent(new PointerEvent('pointermove',{clientX:box.left+box.width/2,bubbles:true}));
const cursor=document.getElementById('cursor-readout').textContent;
const linkedCursor=document.getElementById('phase-plot').querySelectorAll('line[stroke="#333"]').length;
chart.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
const keyboard=document.getElementById('cursor-readout').textContent;
const labels=()=>Array.from(chart.querySelectorAll('text[y="305"]')).map(item=>item.textContent);
const originalLabels=labels();chart.setPointerCapture=()=>{};
chart.dispatchEvent(new PointerEvent('pointerdown',{clientX:box.left+box.width*.3,pointerId:1,bubbles:true}));
chart.dispatchEvent(new PointerEvent('pointerup',{clientX:box.left+box.width*.7,pointerId:1,bubbles:true}));
const zoomLabels=labels();document.getElementById('reset').click();
const resetLabels=labels();
document.querySelectorAll('#trace-controls input')[1].click();
const afterToggle=paths();
const unit=document.getElementById('unit');unit.value='A';unit.dispatchEvent(new Event('change'));
const phaseHidden=document.getElementById('phase-section').hidden;
const afterUnit=paths();
document.querySelector('#trace-controls input').click();
const emptyState=document.getElementById('trace-info').textContent;
document.getElementById('reset').click();
const result={initial,cursor,keyboard,linkedCursor,originalLabels,zoomLabels,resetLabels,
afterToggle,phaseHidden,afterUnit,emptyState,
resources:performance.getEntriesByType('resource').map(item=>item.name)};
const output=document.createElement('pre');output.id='waveform-probe-result';output.textContent=JSON.stringify(result);
document.body.append(output);
} catch(error) {const output=document.createElement('pre');output.id='waveform-probe-result';
output.textContent=JSON.stringify({error:String(error)});document.body.append(output);}
</script>"""
    path = tmp_path / "probe.html"
    path.write_text(page.replace("</main>", probe + "</main>"), encoding="utf-8")
    completed = subprocess.run(
        (
            str(browser),
            "--headless=new",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-extensions",
            f"--user-data-dir={tmp_path / 'browser-profile'}",
            "--dump-dom",
            path.as_uri(),
        ),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-1200:]
    match = re.search(r'<pre id="waveform-probe-result">(.*?)</pre>', completed.stdout)
    assert match is not None, completed.stdout[-1200:]
    result = json.loads(html.unescape(match.group(1)))
    assert result["initial"] == {"valuePaths": 2, "phasePaths": 2}
    assert "Nearest displayed samples" in result["cursor"] and "°" in result["cursor"]
    assert result["keyboard"] != result["cursor"]
    assert result["linkedCursor"] == 1
    assert result["zoomLabels"] != result["originalLabels"]
    assert result["resetLabels"] == result["originalLabels"]
    assert result["afterToggle"] == 1
    assert result["phaseHidden"] and result["afterUnit"] == 1
    assert result["emptyState"] == "Select a trace to plot."
    assert not result["resources"]
