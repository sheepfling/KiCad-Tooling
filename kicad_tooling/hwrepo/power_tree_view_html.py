"""Offline presentation of one authored power rail and its evidence."""

from __future__ import annotations

from html import escape

from .power_tree_view_models import PowerTreeRelationship, PowerTreeViewReport


def _relationship(item: PowerTreeRelationship) -> str:
    endpoints = "".join(
        "<section class='endpoint'>"
        f"<h4>{escape(endpoint.reference)} · {escape(endpoint.id)}</h4>"
        f"<p>Authored symbol: <code>{escape(endpoint.symbol)}</code><br>"
        f"Authored footprint: <code>{escape(endpoint.footprint)}</code></p>"
        f"<p>Observed component: {endpoint.observed_component}; "
        f"symbol <code>{escape(endpoint.observed_symbol or '—')}</code>; "
        f"footprint <code>{escape(endpoint.observed_footprint or '—')}</code>; "
        f"DNP {('yes' if endpoint.observed_dnp else 'no') if endpoint.observed_dnp is not None else 'unreviewed'}.</p>"
        "<table><thead><tr><th>Pin</th><th>Observed net</th><th>Membership</th></tr></thead><tbody>"
        + "".join(
            f"<tr class='{escape(pin.status.lower())}'><th>{escape(pin.pin)}</th>"
            f"<td>{escape(', '.join(pin.observed_nets) or '—')}</td>"
            f"<td>{escape(pin.status)}</td></tr>"
            for pin in endpoint.pins
        )
        + "</tbody></table></section>"
        for endpoint in item.endpoints
    )
    selection = (
        f"<p>Source selection: <strong>{escape(item.selection)}</strong></p>"
        if item.selection is not None
        else ""
    )
    demand = (
        f"<p>Authored load: {item.steady_a:g} A steady, {item.startup_a:g} A startup "
        f"for {item.startup_s:g} s.</p>"
        if item.steady_a is not None and item.startup_a is not None and item.startup_s is not None
        else ""
    )
    return (
        f"<article class='relationship {escape(item.check_status.lower())}'>"
        f"<h3>{escape(item.id)} <span>{escape(item.check_status)}</span></h3>"
        f"<p>{escape(item.basis)}</p>{selection}{demand}"
        f"<p class='detail'>{escape(item.check_detail)}</p>{endpoints}</article>"
    )


def render_power_tree(report: PowerTreeViewReport) -> str:
    """Keep intended relationships separate from netlist observations and budget math."""
    sources = "".join(_relationship(item) for item in report.source_groups)
    loads = "".join(_relationship(item) for item in report.loads)
    extras = "".join(
        f"<li><code>{escape(pin.pin)}</code> observed on <code>{escape(report.net)}</code></li>"
        for pin in report.undeclared_pins
    )
    budget = report.budget
    budget_html = (
        "<p>No authored rail budget was retained for this relationship.</p>"
        if budget is None
        else f"""<table><thead><tr><th>Authored calculation</th><th>Demand</th><th>Limit</th><th>Result</th></tr></thead><tbody>
<tr><th>Steady current</th><td>{budget.steady_demand_a:g} A</td><td>{budget.continuous_limit_a:g} A</td><td>{budget.steady_status}</td></tr>
<tr><th>Startup current</th><td>{budget.startup_demand_a:g} A</td><td>{budget.peak_limit_a:g} A</td><td>{budget.startup_status}</td></tr>
<tr><th>Startup duration</th><td>{budget.startup_duration_assessed_s:g} s</td><td>{budget.peak_duration_limit_s:g} s</td><td>{budget.duration_status}</td></tr>
</tbody></table><p>Nominal authored rail voltage: {budget.voltage_v:g} V. These values are a simultaneous-load budget, not measured current.</p>"""
    )
    source_hashes = "".join(
        f"<li><code>{escape(name)}</code> SHA-256 <code>{sha}</code></li>"
        for name, sha in sorted(report.analysis_source_sha256.items())
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Power tree: {escape(report.rail_id)}</title><style>
body{{font:15px/1.5 system-ui,sans-serif;color:#20343e;background:#f4f7f9;margin:0;padding:1.5rem}}
main{{max-width:1400px;margin:auto}}h1{{margin:.2rem 0}}h2{{margin-top:0}}
.flow{{display:grid;grid-template-columns:minmax(270px,1fr) minmax(210px,.7fr) minmax(270px,1fr);gap:1rem;align-items:start}}
.rail,.relationship,.panel{{background:white;border:1px solid #c9d6dd;border-radius:.5rem;padding:1rem;margin-bottom:1rem}}
.rail{{background:#dceef5;text-align:center;align-self:center}}.rail strong{{font-size:1.25rem}}
.relationship.pass{{border-left:5px solid #2c8659}}.relationship.fail{{border-left:5px solid #bc5d29}}
.relationship.unreviewed{{border-left:5px solid #7d8991}}.relationship h3{{display:flex;justify-content:space-between;gap:.5rem;margin:.1rem 0}}
.endpoint{{border-top:1px solid #dce3e8;padding-top:.4rem;margin-top:.7rem}}.endpoint h4{{margin:.3rem 0}}
.detail{{background:#f4f6f8;padding:.5rem;border-radius:.3rem}}table{{border-collapse:collapse;width:100%}}
th,td{{text-align:left;padding:.35rem;border-bottom:1px solid #dce3e8}}.match{{background:#e7f5ec}}
.different,.missing,.unconnected,.ambiguous,.undeclared{{background:#fff2df}}.unreviewed{{background:#eff2f4}}
code{{overflow-wrap:anywhere}}@media(max-width:850px){{.flow{{grid-template-columns:1fr}}}}
</style></head><body><main><h1>Power tree · {escape(report.rail_id)}</h1>
<p>Authored net <code>{escape(report.net)}</code> · saved analysis {report.analysis_status} · observation {report.observation_status} ·
recorded source against current checkout {report.source_status}.</p>
<p>{escape(report.basis)}</p><div class="flow">
<section aria-label="Authored source groups"><h2>Sources</h2>{sources}</section>
<section class="rail" aria-label="Selected rail"><h2>Rail</h2><strong>{escape(report.rail_id)}</strong><p><code>{escape(report.net)}</code></p></section>
<section aria-label="Authored loads"><h2>Loads</h2>{loads}</section></div>
<section class="panel"><h2>Authored current budget</h2>{budget_html}</section>
<section class="panel"><h2>Observed pins outside this map</h2>
{f"<ul>{extras}</ul>" if extras else "<p>None recorded on the selected net.</p>"}</section>
<section class="panel"><h2>Evidence identity</h2>
<p>Analysis receipt: <code>{escape(report.source_receipt)}</code> SHA-256 <code>{report.source_report_sha256}</code>.</p>
<p>Requirements SHA-256: <code>{report.requirements_sha256}</code>.</p>
<p>Netlist evidence SHA-256: <code>{report.observed_sha256 or "not supplied"}</code>;
native netlist SHA-256: <code>{report.native_netlist_sha256 or "not supplied"}</code>.</p>
<p>Recorded analysis source files:</p>{f"<ul>{source_hashes}</ul>" if source_hashes else "<p>Not recorded in this saved analysis.</p>"}</section>
<p>This view compares authored source/load intent, saved schematic netlist membership, and authored budget math.
It does not infer a power path from net names or prove PCB copper, component behavior, thermal margin, or physical continuity.</p>
</main></body></html>"""
