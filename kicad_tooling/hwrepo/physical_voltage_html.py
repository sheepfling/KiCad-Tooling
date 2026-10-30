"""Escaped voltage envelope plot and condition review for saved test data."""

from __future__ import annotations

from decimal import Decimal
from html import escape

from .physical_voltage_models import PhysicalVoltageReviewReport


def _chart(
    report: PhysicalVoltageReviewReport,
    times: tuple[Decimal, ...],
    values: tuple[Decimal, ...],
) -> str:
    if not times or not values:
        return '<p class="muted">No verified retained samples are available to plot.</p>'
    limit = (
        report.requirement.limit
        if report.requirement is not None and report.status in {"PASS", "FAIL"}
        else None
    )
    bounds = [*values]
    if limit is not None:
        bounds.extend(value for value in (limit.minimum_v, limit.maximum_v) if value is not None)
    minimum, maximum = min(bounds), max(bounds)
    span = maximum - minimum or Decimal(1)
    padding = span * Decimal("0.08")
    floor, ceiling = minimum - padding, maximum + padding
    time_span = times[-1] - times[0]
    unit = escape(report.measured_unit or "unknown unit")

    def x(value: Decimal) -> float:
        return 70 + 790 * float((value - times[0]) / time_span)

    def y(value: Decimal) -> float:
        return 280 - 235 * float((value - floor) / (ceiling - floor))

    marks: list[str] = []
    if len(values) <= 2000:
        points = " ".join(
            f"{x(time):.2f},{y(value):.2f}" for time, value in zip(times, values, strict=True)
        )
        marks.append(
            f'<polyline points="{points}" fill="none" stroke="#186a8a" stroke-width="1.7"/>'
        )
    else:
        bucket = (len(values) + 899) // 900
        for start in range(0, len(values), bucket):
            section = values[start : start + bucket]
            center = x(times[start + len(section) // 2])
            marks.append(
                f'<line x1="{center:.2f}" x2="{center:.2f}" y1="{y(min(section)):.2f}" '
                f'y2="{y(max(section)):.2f}" stroke="#186a8a" stroke-width="1.4"/>'
            )
    if limit is not None:
        for label, value in (("Minimum", limit.minimum_v), ("Maximum", limit.maximum_v)):
            if value is not None:
                position = y(value)
                marks.append(
                    f'<line x1="70" x2="860" y1="{position:.2f}" y2="{position:.2f}" '
                    'stroke="#ad4c37" stroke-width="1.5" stroke-dasharray="7 5"/>'
                    f'<text x="75" y="{position - 5:.2f}" fill="#873a2b" font-size="12">'
                    f"{label}: {escape(str(value))} V</text>"
                )
    return (
        '<svg role="img" aria-label="Measured voltage and authored minimum and maximum lines" '
        'viewBox="0 0 910 330" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="0" y="0" width="910" height="330" fill="#fff"/>'
        '<path d="M70 35 V280 H860" fill="none" stroke="#657785"/>'
        + "".join(marks)
        + f'<text x="68" y="305" font-size="12">{escape(str(times[0]))} s</text>'
        + f'<text x="860" y="305" text-anchor="end" font-size="12">{escape(str(times[-1]))} s</text>'
        + f'<text x="10" y="44" font-size="12">{escape(str(ceiling))} {unit}</text>'
        + f'<text x="10" y="280" font-size="12">{escape(str(floor))} {unit}</text>'
        + "</svg>"
    )


def render_physical_voltage(
    report: PhysicalVoltageReviewReport,
    times: tuple[Decimal, ...],
    values: tuple[Decimal, ...],
    retained: bool,
) -> str:
    capture = report.capture
    requirement = report.requirement
    measured_links = (
        '<a href="source.csv">Retained source CSV</a> · '
        '<a href="data.csv">Full precision normalized data</a> · '
        '<a href="plot.svg">Original measured-series plot</a>'
        if retained
        else "Retained measurement artifacts are missing or changed"
    )
    condition_keys = sorted(
        set(capture.conditions)
        | (set(requirement.conditions) if requirement is not None else set())
    )
    conditions = "".join(
        f"<tr><th>{escape(key)}</th><td>{escape(capture.conditions.get(key, '—'))}</td>"
        f"<td>{escape(requirement.conditions.get(key, '—') if requirement else '—')}</td></tr>"
        for key in condition_keys
    )
    limits = (
        f"{escape(str(requirement.limit.minimum_v)) if requirement.limit.minimum_v is not None else 'none'}"
        f" to {escape(str(requirement.limit.maximum_v)) if requirement.limit.maximum_v is not None else 'none'} V"
        if requirement is not None
        and requirement.limit is not None
        and report.status in {"PASS", "FAIL"}
        else "No applicable authored limit"
    )
    issues = (
        "".join(f"<li>{escape(issue)}</li>" for issue in report.issues) or "<li>None reported.</li>"
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voltage test review · {escape(capture.test_id)}</title>
<style>:root{{font:15px/1.5 system-ui;color:#203446;background:#f3f6f8}}*{{box-sizing:border-box}}
body{{margin:0}}main{{max-width:1120px;margin:auto;padding:36px 20px 65px}}section{{background:white;
border:1px solid #d9e2e8;border-radius:12px;padding:20px;margin:18px 0}}h1{{font-size:2.2rem}}
.notice{{background:#fff2d9;border-left:4px solid #a56c27;padding:14px 17px;border-radius:6px}}
.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;
vertical-align:top;border-bottom:1px solid #e2e8ed}}svg{{width:100%;height:auto;display:block}}
code{{font:12px ui-monospace,monospace;overflow-wrap:anywhere}}p,li,td{{overflow-wrap:anywhere}}
a{{color:#116078}}a:focus-visible{{outline:3px solid #218fa5}}.muted{{color:#607587}}</style><main>
<header><h1>Voltage test review · {escape(capture.test_id)}</h1>
<p><strong>{escape(report.status)}</strong> · {report.samples} retained sample(s) ·
{escape(capture.channel)} (imported {escape(report.measured_unit or "unknown")}; capture declares {
        escape(capture.unit)
    })</p>
<p class="notice">This compares recorded data with an explicitly authored voltage envelope.
The capture context and origin are project-authored claims; this view does not verify the instrument,
physical origin, test procedure, electrical safety, or release readiness.</p></header>
<section><h2>Voltage over time</h2>{_chart(report, times, values)}
<p>Observed minimum: <strong>{
        escape(str(report.observed_min)) if report.observed_min is not None else "unavailable"
    }</strong> {escape(report.measured_unit or "")} ·
maximum: <strong>{
        escape(str(report.observed_max)) if report.observed_max is not None else "unavailable"
    }</strong> {escape(report.measured_unit or "")}</p>
<p>Authored envelope: <strong>{limits}</strong> · out-of-limit samples:
<strong>{report.violation_count}</strong></p><p>{measured_links}</p></section>
<section><h2>Source and capture</h2><p>Project source: <code>{escape(capture.source_csv)}</code>
· SHA-256 <code>{report.source_sha256}</code> · current bytes: <strong>{
        "MATCH" if report.source_current else "STALE"
    }</strong></p>
<p>Captured at: {escape(capture.captured_at)} · declared origin: {escape(capture.recorded_origin)}
· instrument: {escape(capture.instrument)}</p>
<p>Selected receipt: <code>{escape(report.measured_receipt)}</code> · SHA-256
<code>{report.measured_receipt_sha256}</code></p>
<p><a href="capture.json">Exact capture context</a> · requirement:
{escape(report.requirement_state)}</p></section>
<section><h2>Conditions</h2><div class="scroll"><table><thead><tr><th>Condition</th>
<th>Capture</th><th>Requirement</th></tr></thead><tbody>{conditions}</tbody></table></div>
<p>Requirement basis: {escape(requirement.basis) if requirement else "not available"}</p>
{
        (
            '<p><a href="requirement.json">Exact selected requirement file</a></p>'
            if report.requirement_sha256
            else ""
        )
    }</section>
<section><h2>Review issues</h2><ul>{issues}</ul>
{
        (
            "<p>First out-of-limit sample: index "
            + str(report.first_violation.sample_index)
            + ", time "
            + escape(str(report.first_violation.time_seconds))
            + " s, value "
            + escape(str(report.first_violation.value_v))
            + " V.</p>"
            if report.first_violation
            else ""
        )
    }</section>
<p><a href="physical-voltage.json">Structured review receipt</a></p></main></html>"""
