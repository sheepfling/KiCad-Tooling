"""Offline schematic and PCB finding explorer for a verified review snapshot."""

from __future__ import annotations

from html import escape
from pathlib import PurePosixPath

from .findings_view_models import FindingsViewReport, ReviewDrawing

STYLE = """
:root{font-family:system-ui,sans-serif;color:#203044;background:#f3f6f7;line-height:1.5}
*{box-sizing:border-box}body{margin:0}main{max-width:1500px;margin:auto;padding:2rem}
h1{margin-bottom:.25rem}h2{margin-top:0}section{background:white;border:1px solid #d7e0e3;
border-radius:12px;margin:1rem 0;padding:1.25rem}.muted{color:#536775}.warning{background:#fff4df}
.drawing{position:relative;width:100%;background:#fff}.drawing img{display:block;width:100%;height:auto}
.canvas-scroll{overflow:auto;max-height:75vh;border:1px solid #d7e0e3}.zoom-controls{display:flex;
gap:.5rem;align-items:center;flex-wrap:wrap;margin:.5rem 0}.zoom-controls button{font:inherit;padding:.35rem .65rem}
.drawing svg{position:absolute;inset:0;width:100%;height:100%}.drawing a{pointer-events:all}
.drawing circle{fill:#d8383e;fill-opacity:.38;stroke:#b31a27;stroke-width:.6;vector-effect:non-scaling-stroke}
.drawing a:focus circle,.drawing a:hover circle{fill:#f5b633;fill-opacity:.8;stroke:#222;stroke-width:2}
.filters{display:flex;gap:1rem;align-items:center;flex-wrap:wrap}input,select{font:inherit;padding:.45rem}
.finding{border-top:1px solid #dde5e7;padding:1rem 0;scroll-margin:1rem}.finding:target{background:#fff5d5}
.finding p{margin:.25rem 0}.badge{font-size:.8rem;font-weight:700;letter-spacing:.04em}
a{color:#075d76}code{overflow-wrap:anywhere}.hidden,[hidden]{display:none!important}
"""

SCRIPT = """
const search = document.getElementById('finding-search');
const origin = document.getElementById('finding-origin');
function filterFindings() {
  const query = search.value.toLowerCase();
  let shown = 0;
  document.querySelectorAll('.finding').forEach(row => {
    const visible = row.textContent.toLowerCase().includes(query) &&
      (origin.value === 'ALL' || row.dataset.origin === origin.value);
    row.hidden = !visible;
    shown += visible ? 1 : 0;
  });
  document.getElementById('finding-count').textContent = shown + ' finding(s) shown';
}
search.addEventListener('input', filterFindings);
origin.addEventListener('change', filterFindings);
document.querySelectorAll('.drawing svg a').forEach(marker => {
  marker.addEventListener('click', () => {
    const target = document.getElementById(marker.getAttribute('href').slice(1));
    if (target && target.hidden) {
      search.value = '';
      origin.value = 'ALL';
      filterFindings();
    }
  });
});
const zoomLevels = [100, 150, 200, 300, 400];
document.querySelectorAll('[data-zoom]').forEach(button => {
  button.addEventListener('click', () => {
    const drawing = document.getElementById(button.dataset.target);
    const status = document.getElementById(button.dataset.target + '-status');
    let index = zoomLevels.indexOf(Number(drawing.dataset.zoomLevel || 100));
    if (button.dataset.zoom === 'in') index = Math.min(index + 1, zoomLevels.length - 1);
    else if (button.dataset.zoom === 'out') index = Math.max(index - 1, 0);
    else index = 0;
    drawing.dataset.zoomLevel = String(zoomLevels[index]);
    drawing.style.width = zoomLevels[index] + '%';
    status.textContent = zoomLevels[index] + '%';
  });
});
filterFindings();
"""


def _drawing(report: FindingsViewReport, drawing: ReviewDrawing) -> str:
    circles: list[str] = []
    for number, finding in enumerate(report.findings, 1):
        for point_number, marker in enumerate(finding.markers, 1):
            if marker.drawing != drawing.kind:
                continue
            label = escape(f"{number}: {finding.title}")
            circles.append(
                f'<a id="marker-{number}-{point_number}" href="#finding-{number}" '
                f'aria-label="{label}"><title>{label}</title>'
                f'<circle cx="{marker.x_mm:.6f}" cy="{marker.y_mm:.6f}" r="1.8"/></a>'
            )
    title = "Schematic" if drawing.kind == "schematic" else "PCB"
    display_title = escape(f"{title} · {PurePosixPath(drawing.source_artifact).name}")
    canvas_id = escape(f"canvas-{drawing.file}", quote=True)
    overlay = (
        f'<svg viewBox="0 0 {drawing.width_mm:.6f} {drawing.height_mm:.6f}" '
        f'aria-label="{title} finding markers">{"".join(circles)}</svg>'
        if drawing.mapping_supported
        else ""
    )
    note = (
        "Select a marker to see its finding."
        if drawing.mapping_supported
        else "Coordinate mapping is unavailable for this SVG; findings remain listed below."
    )
    return (
        f'<section id="drawing-{escape(drawing.file, quote=True)}"><h2>{display_title}</h2>'
        f'<p class="muted">{note}</p>'
        f'<div class="zoom-controls" aria-label="{title} zoom controls">'
        f'<button type="button" data-zoom="out" data-target="{canvas_id}">Zoom out</button>'
        f'<button type="button" data-zoom="in" data-target="{canvas_id}">Zoom in</button>'
        f'<button type="button" data-zoom="reset" data-target="{canvas_id}">Fit width</button>'
        f'<span id="{canvas_id}-status" aria-live="polite">100%</span></div>'
        f'<div class="canvas-scroll"><div class="drawing" id="{canvas_id}">'
        f'<img src="{escape(drawing.file, quote=True)}" '
        f'alt="{title} exported from the retained KiCad run">{overlay}</div></div></section>'
    )


def render_findings_view(report: FindingsViewReport) -> str:
    """Escape all project and finding text; avoid scripts in the supplied SVGs."""
    mapped = sum(
        bool(finding.markers) and not finding.unmapped_reason for finding in report.findings
    )
    partial = sum(
        bool(finding.markers) and bool(finding.unmapped_reason) for finding in report.findings
    )
    unmapped = sum(not finding.markers for finding in report.findings)
    mapped_rows: list[str] = []
    unmapped_rows: list[str] = []
    for number, finding in enumerate(report.findings, 1):
        links = " ".join(
            f'<a href="#marker-{number}-{index}">{escape(marker.drawing)} '
            f"{marker.x_mm:g}, {marker.y_mm:g} mm</a>"
            for index, marker in enumerate(finding.markers, 1)
        )
        missing = (
            f'<p class="muted">Unmapped: {escape(finding.unmapped_reason)}</p>'
            if finding.unmapped_reason
            else ""
        )
        details = "".join(
            f"<dt>{escape(name)}</dt><dd>{escape('; '.join(values))}</dd>"
            for name, values in sorted(finding.evidence.items())
        )
        if finding.fingerprint:
            details += f"<dt>Fingerprint</dt><dd><code>{finding.fingerprint}</code></dd>"
        evidence = (
            f"<details><summary>Finding evidence</summary><dl>{details}</dl></details>"
            if details
            else ""
        )
        row = (
            f'<article class="finding" id="finding-{number}" data-origin="{finding.origin}">'
            f'<span class="badge">{finding.origin} · {escape(finding.severity)}</span>'
            f"<h3>{number}. {escape(finding.title)}</h3><p><code>{escape(finding.rule)}</code></p>"
            f"<p>{escape(finding.description)}</p><p>{links}</p>{missing}{evidence}</article>"
        )
        (unmapped_rows if finding.unmapped_reason or not finding.markers else mapped_rows).append(
            row
        )
    notes = "".join(f"<li>{escape(issue)}</li>" for issue in report.issues)
    drawings = "".join(_drawing(report, drawing) for drawing in report.drawings)
    lint_evidence = (
        f"<p>Design-lint snapshot: <code>{escape(report.lint_report)}</code> "
        f"(SHA-256: <code>{report.lint_report_sha256}</code>)</p>"
        if report.lint_report
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Findings review · {escape(report.project_id)}</title><style>{STYLE}</style></head>
<body><main><header><p class="badge">SOURCE-BOUND REVIEW</p><h1>{escape(report.project_id)} findings</h1>
<p>Native checks: <strong>{report.native_status}</strong> · Design lint: <strong>{report.lint_status}</strong></p>
<p>{len(report.findings)} findings · {mapped} mapped · {partial} partially mapped · {unmapped} unmapped</p>
<p>Snapshot of saved evidence. Markers indicate reported locations, not approval or automatic fixes.</p></header>
<section class="warning"><h2>Coverage and limitations</h2><ul>{notes}</ul></section>
{drawings}
<section><h2>Findings</h2><div class="filters"><label for="finding-search">Search</label>
<input id="finding-search" type="search"><label for="finding-origin">Source</label>
<select id="finding-origin"><option value="ALL">All</option><option value="ERC">ERC</option>
<option value="DRC">DRC</option><option value="DESIGN_LINT">Design lint</option></select></div>
<p id="finding-count" aria-live="polite"></p>
<h3>Mapped findings</h3>{"".join(mapped_rows) or "<p>No fully mapped findings.</p>"}
<h3>Unmapped or partially mapped findings</h3>{"".join(unmapped_rows) or "<p>None in the supplied evidence.</p>"}</section>
<section><h2>Evidence</h2><p>Native summary: <code>{escape(report.native_summary)}</code></p>
<p>SHA-256: <code>{report.native_summary_sha256}</code></p>{lint_evidence}<p><a href="review.json">Structured review and hashes</a></p></section>
</main><script>{SCRIPT}</script></body></html>"""
