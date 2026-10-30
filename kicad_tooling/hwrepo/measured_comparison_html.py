"""Bounded offline overlay for two explicitly aligned measured traces."""

from __future__ import annotations

import json
import math
from decimal import Decimal
from html import escape

from .measured_comparison_models import MeasuredComparisonReport

MAX_DISPLAY_POINTS = 4002


def display_indices(values: tuple[Decimal, ...]) -> tuple[int, ...]:
    """Retain endpoints and ordered extrema from bounded buckets for display."""
    if len(values) <= MAX_DISPLAY_POINTS:
        return tuple(range(len(values)))
    interior = len(values) - 2
    buckets = (MAX_DISPLAY_POINTS - 2) // 2
    step = math.ceil(interior / buckets)
    selected = {0, len(values) - 1}
    for start in range(1, len(values) - 1, step):
        stop = min(start + step, len(values) - 1)
        selected.add(min(range(start, stop), key=values.__getitem__))
        selected.add(max(range(start, stop), key=values.__getitem__))
    return tuple(sorted(selected))


def _plot_points(
    times: tuple[Decimal, ...],
    values: tuple[Decimal, ...],
    indices: tuple[int, ...],
    origin: Decimal,
) -> tuple[tuple[float, float], ...]:
    points = tuple((float(times[index] - origin), float(values[index])) for index in indices)
    if any(not math.isfinite(x) or not math.isfinite(y) for x, y in points):
        raise ValueError("Selected data exceeds finite display coordinates")
    if any(points[index][0] <= points[index - 1][0] for index in range(1, len(points))):
        raise ValueError("Selected time spacing cannot be represented in the display")
    return points


def render_measured_comparison(
    report: MeasuredComparisonReport,
    before_times: tuple[Decimal, ...],
    before_values: tuple[Decimal, ...],
    before_indices: tuple[int, ...],
    after_times: tuple[Decimal, ...],
    after_values: tuple[Decimal, ...],
    after_indices: tuple[int, ...],
) -> str:
    origin = min(before_times[0], after_times[0])
    first = _plot_points(before_times, before_values, before_indices, origin)
    second = _plot_points(after_times, after_values, after_indices, origin)
    all_points = (*first, *second)
    x_min = min(x for x, _ in all_points)
    x_max = max(x for x, _ in all_points)
    y_min = min(y for _, y in all_points)
    y_max = max(y for _, y in all_points)
    if x_max <= x_min or not math.isfinite(x_max - x_min):
        raise ValueError("Selected traces have no displayable time span")
    if y_max == y_min:
        margin = max(abs(y_min) * 0.05, 1.0)
        y_min -= margin
        y_max += margin
    if not math.isfinite(y_max - y_min):
        raise ValueError("Selected values exceed the display range")
    width, height = 1000.0, 400.0
    left, right, top, bottom = 72.0, 20.0, 22.0, 60.0

    def project(points: tuple[tuple[float, float], ...]) -> str:
        return " ".join(
            f"{'M' if index == 0 else 'L'}"
            f"{left + (x - x_min) / (x_max - x_min) * (width - left - right):.3f},"
            f"{height - bottom - (y - y_min) / (y_max - y_min) * (height - top - bottom):.3f}"
            for index, (x, y) in enumerate(points)
        )

    baseline = project(first)
    candidate = project(second)
    x_grid = "".join(
        f'<line x1="{left + fraction * (width - left - right):.1f}" y1="{top}" '
        f'x2="{left + fraction * (width - left - right):.1f}" y2="{height - bottom}"/>'
        f'<text x="{left + fraction * (width - left - right):.1f}" y="{height - 31}" '
        f'text-anchor="middle">{x_min + fraction * (x_max - x_min):.6g}</text>'
        for fraction in (0, 0.25, 0.5, 0.75, 1)
    )
    y_grid = "".join(
        f'<line x1="{left}" y1="{height - bottom - fraction * (height - top - bottom):.1f}" '
        f'x2="{width - right}" y2="{height - bottom - fraction * (height - top - bottom):.1f}"/>'
        f'<text x="{left - 8}" y="{height - bottom - fraction * (height - top - bottom) + 4:.1f}" '
        f'text-anchor="end">{y_min + fraction * (y_max - y_min):.6g}</text>'
        for fraction in (0, 0.25, 0.5, 0.75, 1)
    )
    # Only finite numeric pairs enter the script. Keep source labels in escaped HTML.
    points_json = json.dumps({"baseline": first, "candidate": second}, separators=(",", ":"))
    axis = "Elapsed time (s)" if report.alignment == "elapsed" else "Absolute time (s)"
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Measured run comparison</title><style>
body{{font:15px/1.5 system-ui;color:#203044;background:#f3f6f8;margin:0}}
main{{max-width:1250px;margin:auto;padding:1.5rem}}section{{background:white;padding:1rem;
border-radius:.6rem;margin:1rem 0}}svg{{display:block;width:100%;height:auto;background:#fff}}
.grid line{{stroke:#d8e1e8}}.grid text{{font:12px system-ui;fill:#52677a}}
.baseline{{stroke:#176fbb}}.candidate{{stroke:#cb5a32}}.trace{{fill:none;stroke-width:2;
vector-effect:non-scaling-stroke}}a{{color:#075d76}}.muted{{color:#52677a}}
label{{margin-right:1.4rem}}code{{overflow-wrap:anywhere}}table{{border-collapse:collapse;width:100%}}
th,td{{border-bottom:1px solid #dce4e9;padding:.5rem;text-align:left;vertical-align:top}}
</style><main><h1>Measured run comparison · {escape(report.project_id)}</h1>
<p>Channel <strong>{escape(report.channel)}</strong> · <span id="unit">{escape(report.unit)}</span> ·
{escape(report.alignment)} alignment · {report.overlap.lower()} time windows ·
{report.source_status.lower()} source state.</p>
<p class="muted">The overlay shows retained measurements only. It does not interpolate,
assert matching conditions, or apply acceptance limits. Time labels are seconds
relative to the left axis origin ({escape(str(origin))}).</p>
<section><h2>Overlay</h2>
<p><label><input id="show-baseline" type="checkbox" checked> Baseline</label>
<label><input id="show-candidate" type="checkbox" checked> Candidate</label></p>
<svg id="chart" viewBox="0 0 1000 400" role="img"
aria-label="Overlay of baseline and candidate {escape(report.channel)} measurements">
<g class="grid">{x_grid}{y_grid}</g>
<path id="baseline" class="trace baseline" d="{baseline}"/>
<path id="candidate" class="trace candidate" d="{candidate}"/>
<text x="500" y="390" text-anchor="middle">{axis}</text>
<text x="18" y="200" transform="rotate(-90 18 200)" text-anchor="middle">{escape(report.unit)}</text>
</svg><p id="hover" aria-live="polite">Move over the plot to inspect nearest displayed points.</p>
<p class="muted">Display retains endpoints and extrema: {report.display_points_baseline}
of {report.baseline.samples} baseline samples; {report.display_points_candidate}
of {report.candidate.samples} candidate samples. Download the full original CSVs below.</p>
</section><section><h2>Selected evidence</h2><table><thead><tr><th>Run</th>
<th>Source</th><th>Samples</th><th>Source state</th><th>Retained CSV</th></tr></thead><tbody>
<tr><th>Baseline</th><td><code>{escape(report.baseline.source)}</code><br>
SHA-256 <code>{report.baseline.source_sha256}</code></td><td>{report.baseline.samples}</td>
<td>{report.baseline.source_state}</td><td><a href="baseline-source.csv">Original CSV</a></td></tr>
<tr><th>Candidate</th><td><code>{escape(report.candidate.source)}</code><br>
SHA-256 <code>{report.candidate.source_sha256}</code></td><td>{report.candidate.samples}</td>
<td>{report.candidate.source_state}</td><td><a href="candidate-source.csv">Original CSV</a></td></tr>
</tbody></table><p><a href="comparison.json">Structured comparison</a></p></section>
<script>const points={points_json};const chart=document.getElementById('chart');
const unit=document.getElementById('unit').textContent;
for(const name of ['baseline','candidate']){{document.getElementById('show-'+name)
.addEventListener('change',event=>{{document.getElementById(name).style.display=
event.target.checked?'':'none';}});}}
function nearest(items,x){{let lo=0,hi=items.length-1;while(lo<hi){{const mid=(lo+hi)>>1;
if(items[mid][0]<x)lo=mid+1;else hi=mid;}}if(lo>0&&Math.abs(items[lo-1][0]-x)
<Math.abs(items[lo][0]-x))lo--;return items[lo];}}
chart.addEventListener('pointermove',event=>{{const rect=chart.getBoundingClientRect();
const px=(event.clientX-rect.left)/rect.width*1000;
const x={x_min}+Math.max(0,Math.min(1,(px-72)/908))*{x_max - x_min};
const labels=[];for(const name of ['baseline','candidate']){{if(document.getElementById(name).style.display==='none')
continue;const item=nearest(points[name],x);labels.push(name+': '+item[1]+' '+unit+' at '+
item[0]+' s from axis origin');}}document.getElementById('hover').textContent=
'Nearest displayed points — '+labels.join(' · ');}});
chart.addEventListener('pointerleave',()=>{{document.getElementById('hover').textContent=
'Move over the plot to inspect nearest displayed points.';}});</script></main></html>"""
