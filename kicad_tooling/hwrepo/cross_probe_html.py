"""Offline component-to-drawing navigation with reversible reference markers."""

from __future__ import annotations

from html import escape

from .cross_probe_models import CrossProbeLocation, CrossProbeReport
from .findings_view_models import ReviewDrawing

_STYLE = """
body{font:1rem/1.5 system-ui,sans-serif;color:#203044;background:#f3f6f7;margin:0}
main{max-width:1450px;margin:auto;padding:1.5rem}section{background:white;border:1px solid #d7e0e3;
border-radius:.6rem;padding:1rem;margin:1rem 0}h1{margin-bottom:.2rem}a{color:#075d76}
code{overflow-wrap:anywhere}.note{background:#fff3d8;padding:.7rem}
.scroll{overflow:auto;max-height:70vh;border:1px solid #d7e0e3}.drawing{position:relative;width:100%}
.drawing img{display:block;width:100%;height:auto}.drawing svg{position:absolute;inset:0;width:100%;height:100%}
.drawing circle{fill:#167ac2;fill-opacity:.45;stroke:#003a61;stroke-width:.7;vector-effect:non-scaling-stroke}
.drawing a:hover circle,.drawing a:focus circle,.drawing a:target circle{fill:#f2a12c;fill-opacity:.9;stroke:#192931;stroke-width:2}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #e2e8eb;padding:.6rem;text-align:left;vertical-align:top}
th{background:#f7f9fa}.component:target{background:#fff3d8}.component[hidden]{display:none}
input{font:inherit;padding:.5rem;width:min(100%,30rem)}.muted{color:#506674}
"""

_SCRIPT = """
const search = document.getElementById('reference-search');
function filter() {
  const query = search.value.toLowerCase();
  let shown = 0;
  document.querySelectorAll('.component').forEach(row => {
    row.hidden = !row.textContent.toLowerCase().includes(query);
    if (!row.hidden) shown++;
  });
  document.getElementById('count').textContent = shown + ' reference(s) shown';
}
search.addEventListener('input', filter);
document.querySelectorAll('.drawing svg a').forEach(marker => {
  marker.addEventListener('click', () => {
    const row = document.querySelector(marker.getAttribute('href'));
    if (row && row.hidden) { search.value = ''; filter(); }
  });
});
filter();
"""


def _location_links(locations: tuple[CrossProbeLocation, ...], number: int, kind: str) -> str:
    if not locations:
        return '<span class="muted">No supported location</span>'
    lines: list[str] = []
    for index, location in enumerate(locations, 1):
        label = f"{location.x_mm:g}, {location.y_mm:g} mm"
        if location.sheet_path:
            label += " · " + "/".join(location.sheet_path)
        if location.side:
            label += " · " + location.side
        if location.drawing_file:
            link = f"marker-{number}-{kind}-{index}"
            lines.append(f'<a href="#{link}">{escape(label)}</a>')
        else:
            lines.append(f"{escape(label)} (source coordinate only)")
    return "<br>".join(lines)


def _drawing(report: CrossProbeReport, drawing: ReviewDrawing) -> str:
    markers: list[str] = []
    for number, entry in enumerate(report.entries, 1):
        for kind, locations in (("pcb", entry.board), ("schematic", entry.schematic)):
            for index, location in enumerate(locations, 1):
                if location.drawing_file != drawing.file:
                    continue
                identifier = f"marker-{number}-{kind}-{index}"
                label = escape(f"{entry.reference} at {location.x_mm:g}, {location.y_mm:g} mm")
                markers.append(
                    f'<a id="{identifier}" href="#component-{number}" aria-label="{label}">'
                    f'<title>{label}</title><circle cx="{location.x_mm:.6f}" '
                    f'cy="{location.y_mm:.6f}" r="1.8"/></a>'
                )
    overlay = (
        f'<svg viewBox="0 0 {drawing.width_mm:.6f} {drawing.height_mm:.6f}" '
        f'aria-label="{drawing.kind} component markers">{"".join(markers)}</svg>'
        if drawing.mapping_supported
        else ""
    )
    name = escape(drawing.file, quote=True)
    sheet = (
        " · sheet /" + "/".join(drawing.sheet_path)
        if drawing.sheet_instance_path is not None
        else ""
    )
    return (
        f"<section><h2>{escape(drawing.kind.upper())} drawing{escape(sheet)}</h2>"
        f'<p class="muted">{escape(drawing.source_artifact)}'
        + (" · markers map to exact references" if markers else " · no supported markers")
        + f'</p><div class="scroll"><div class="drawing"><img src="{name}" '
        f'alt="Retained {escape(drawing.kind)} SVG drawing">{overlay}</div></div></section>'
    )


def render_cross_probe(report: CrossProbeReport) -> str:
    """Keep unsupported references visible and make each supported link reversible."""
    rows = "".join(
        f'<tr class="component" id="component-{number}"><th>{escape(entry.reference)}</th>'
        f"<td>{escape(entry.population)}</td><td>{escape(entry.part_id or 'Unresolved')}<br>"
        f"{escape(entry.value)}<br>{escape(entry.footprint)}</td>"
        f"<td>{_location_links(entry.board, number, 'pcb')}</td>"
        f"<td>{_location_links(entry.schematic, number, 'schematic')}</td>"
        f"<td>{escape('; '.join(entry.issues))}</td></tr>"
        for number, entry in enumerate(report.entries, 1)
    )
    source_rows = "".join(
        f"<li><code>{escape(path)}</code> SHA-256 <code>{sha}</code></li>"
        for path, sha in sorted(report.source_hashes.items())
    )
    issues = "".join(f"<li>{escape(item)}</li>" for item in report.issues)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BOM and design: {escape(report.project_id)}</title><style>{_STYLE}</style></head>
<body><main><h1>BOM and design: {escape(report.project_id)}</h1>
<p class="note">Reference locations support navigation only. They do not approve a part, footprint,
assembly, electrical design, or release. Variant identity is not recorded by these receipts.</p>
<section><h2>Components</h2><label for="reference-search">Search references and parts</label>
<p><input id="reference-search" type="search" autocomplete="off"></p>
<p id="count" aria-live="polite"></p><div class="scroll"><table><thead><tr>
<th>Reference</th><th>Population</th><th>Part / value / footprint</th><th>PCB</th>
<th>Schematic</th><th>Notes</th></tr></thead><tbody>{rows}</tbody></table></div></section>
{"".join(_drawing(report, drawing) for drawing in report.drawings)}
<section><h2>Source and receipt identity</h2><p>Parts receipt: <code>{escape(report.parts_report)}</code>
SHA-256 <code>{report.parts_report_sha256}</code>.</p>
<p>Findings drawing receipt: <code>{escape(report.findings_view)}</code>
SHA-256 <code>{report.findings_view_sha256}</code>.</p><ul>{source_rows}</ul>
<p><a href="cross-probe.json">Structured navigation record</a></p></section>
<section><h2>Unmapped evidence</h2><ul>{issues}</ul></section>
</main><script>{_SCRIPT}</script></body></html>"""
