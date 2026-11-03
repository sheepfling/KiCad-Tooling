"""Offline one-hop netlist page with explicit observation and intent labels."""

from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

from .connectivity_view_models import ConnectivityViewReport
from .contracts import relative_path_from, repo_path


def render_connectivity_view(root: Path, report: ConnectivityViewReport) -> str:
    output = Path(report.output_directory)
    receipt_link = escape(
        quote(
            relative_path_from(repo_path(root, report.source_receipt), output).as_posix(),
            safe="/.-_",
        ),
        quote=True,
    )
    cards = "".join(
        '<article class="component">'
        f'<div class="selected"><strong>{escape(report.net)}</strong>'
        f"<small>{escape(', '.join(item.selected_pins))}</small></div>"
        f'<div class="device"><strong>{escape(item.reference)}</strong>'
        f"<small>{escape(item.observed_symbol or 'symbol unknown')} · "
        f"{escape(item.observed_footprint or 'footprint unknown')}"
        f"{' · DNP' if item.dnp else ''}</small></div>"
        '<div class="neighbors">'
        + (
            "".join(
                f'<div class="neighbor"><strong>{escape(other.net or "unconnected")}</strong>'
                f"<small>{escape(', '.join(other.pins))}</small></div>"
                for other in item.other_nets
            )
            or '<div class="neighbor">No other observed terminal</div>'
        )
        + "</div></article>"
        for item in report.components
    )
    pin_rows = "".join(
        f"<tr><th>{escape(item.pin)}</th><td>{escape(item.expected_net or '—')}</td>"
        f"<td>{escape(', '.join(item.observed_nets) or '—')}</td>"
        f"<td>{escape(item.status)}</td></tr>"
        for item in report.pins
    )
    roles = ", ".join(report.authored_roles) or "No exact authored ground or power role"
    issues = "".join(f"<li>{escape(item)}</li>" for item in report.issues)
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connectivity · {escape(report.net)}</title>
<style>:root{{font:15px/1.5 system-ui;color:#203145;background:#f3f6f9}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1200px;margin:auto;padding:32px 20px}}
section{{background:white;border:1px solid #d8e1e8;border-radius:12px;padding:20px;margin:16px 0}}
.component{{display:grid;grid-template-columns:minmax(150px,1fr) minmax(150px,1fr) minmax(180px,2fr);
gap:12px;align-items:start;border-top:1px solid #dce4ec;padding:14px 0}}
.selected,.device,.neighbor{{padding:9px;border-radius:8px;background:#e8f2f5}}
.device{{background:#f4eedf}}.neighbor{{background:#eef1fa;margin-bottom:7px}}
small{{display:block;color:#526577;overflow-wrap:anywhere}}table{{border-collapse:collapse;width:100%}}
th,td{{padding:8px;border-bottom:1px solid #e2e8ee;text-align:left;vertical-align:top}}
code{{overflow-wrap:anywhere}}.scroll{{overflow:auto}}a{{color:#126477}}
a:focus-visible{{outline:3px solid #318e9c}}
@media(max-width:650px){{.component{{grid-template-columns:1fr}}}}
</style><main><h1>Connectivity · {escape(report.net)}</h1>
<p>Exact netlist membership and other terminals on the same components.
Shared component membership does not establish an internal conductive path or PCB copper continuity.</p>
<section><h2>Evidence</h2><p>Authored role: {escape(roles)}.</p>
<p>Observation: {report.observation_status}. Source against current checkout: {report.source_status}.</p>
<p><a href="{receipt_link}">Selected electrical receipt</a> · SHA-256
<code>{report.source_report_sha256}</code></p><p>Requirements: <code>{report.requirements_sha256}</code> ·
native netlist: <code>{report.native_netlist_sha256 or "not retained"}</code></p>
{f"<ul>{issues}</ul>" if issues else ""}</section>
<section><h2>One neighboring component hop</h2>
{cards or "<p>No retained component neighborhood for this exact net.</p>"}</section>
<section><h2>Authored and observed pins</h2><div class="scroll"><table>
<thead><tr><th>Pin</th><th>Authored net</th><th>Observed net</th><th>Status</th></tr></thead>
<tbody>{pin_rows or '<tr><td colspan="4">No pins available.</td></tr>'}</tbody></table></div></section>
<p><a href="connectivity-view.json">Structured receipt</a> · Review only; no electrical or release approval.</p>
</main></html>"""
