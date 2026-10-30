"""Offline offer comparison with per-currency cost bars and missing fields."""

from __future__ import annotations

from html import escape

from .supplier_analysis_models import SupplierAnalysisReport, SupplierOfferCost


def _money(value: int | None, currency: str) -> str:
    return "unavailable" if value is None else f"{value:,} {escape(currency)} minor units"


def _offer(value: SupplierOfferCost | None, other: SupplierOfferCost | None) -> str:
    if value is None:
        return "<span class='muted'>No offer in this snapshot.</span>"
    comparable = (
        other is not None
        and value.currency == other.currency
        and value.extended_minor is not None
        and other.extended_minor is not None
    )
    bar = ""
    if comparable and other is not None and other.extended_minor is not None:
        maximum = max(value.extended_minor or 0, other.extended_minor, 1)
        width = round(100 * (value.extended_minor or 0) / maximum)
        bar = f'<div class="bar" style="width:{width}%"></div>'
    return (
        f"<strong>{escape(value.status)}</strong> · {escape(value.currency)} · "
        f"unit {_money(value.unit_price_minor, value.currency)}<br>"
        f"Requested {value.requested_quantity if value.requested_quantity is not None else 'unavailable'} · "
        f"minimum {value.minimum_order_quantity if value.minimum_order_quantity is not None else 'unavailable'} · "
        f"multiple {value.package_multiple if value.package_multiple is not None else 'unavailable'} · "
        f"order {value.order_quantity if value.order_quantity is not None else 'unavailable'}<br>"
        f"Extended {_money(value.extended_minor, value.currency)}{bar}"
        f"<small>Declared availability: {escape(value.availability)} · lead time "
        f"{value.lead_time_days if value.lead_time_days is not None else 'unavailable'} days · "
        f"region {escape(value.region)} · offer ID {escape(value.offer_id)}<br>"
        f"Source: {escape(value.source_url)}</small>"
    )


def render_supplier_analysis(report: SupplierAnalysisReport) -> str:
    rows = (
        "".join(
            "<tr>"
            f"<th>{escape(item.part_id)}<br><small>{escape(item.supplier)} / "
            f"{escape(item.supplier_sku)} · break {item.quantity_break}</small></th>"
            f"<td>{escape(item.change)}</td>"
            f"<td>{_offer(item.before, item.after)}</td>"
            f"<td>{_offer(item.after, item.before)}</td></tr>"
            for item in report.offers
        )
        or '<tr><td colspan="4">No offers in the selected snapshots.</td></tr>'
    )
    issues = (
        "".join(f"<li>{escape(item)}</li>" for item in report.issues) or "<li>None reported.</li>"
    )
    source_rows = "".join(
        f"<tr><th>{escape(path)}</th><td><code>{sha}</code></td></tr>"
        for path, sha in sorted({**report.parts_source_hashes, **report.parts_input_hashes}.items())
    )
    summaries = "".join(
        "<tr>"
        f"<th>{label}</th><td>{escape(item.snapshot_id)}</td>"
        f"<td>{escape(item.observed_at.isoformat())}</td>"
        f"<td><code>{item.source_commit}</code></td>"
        f"<td>{escape(item.freshness)}</td>"
        f"<td>{escape(item.validation_status)}</td>"
        f"<td><code>{item.sha256}</code></td></tr>"
        for label, item in (("Before", report.before), ("After", report.after))
    )
    validation_issues = (
        "".join(
            f"<li>{label}: {escape(issue)}</li>"
            for label, snapshot in (("Before", report.before), ("After", report.after))
            for issue in snapshot.validation_issues
        )
        or "<li>None reported.</li>"
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Supplier offer analysis · {escape(report.project_id)}</title>
<style>:root{{font:15px/1.5 system-ui;color:#203446;background:#f3f6f8}}*{{box-sizing:border-box}}
body{{margin:0}}main{{max-width:1300px;margin:auto;padding:36px 20px 65px}}section{{background:white;
border:1px solid #d9e2e8;border-radius:12px;padding:20px;margin:18px 0}}h1{{font-size:2.1rem}}
.notice{{background:#fff2d9;border-left:4px solid #a56c27;padding:14px 17px;border-radius:6px}}
.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;
vertical-align:top;border-bottom:1px solid #e2e8ed}}td{{min-width:240px}}
code{{font:12px ui-monospace,monospace;overflow-wrap:anywhere}}small{{display:block;color:#586b79}}
p,li,td{{overflow-wrap:anywhere}}a{{color:#116078}}a:focus-visible{{outline:3px solid #218fa5}}
.bar{{height:8px;background:#218fa5;border-radius:5px;margin:6px 0 9px}}.muted{{color:#607587}}</style><main>
<header><h1>Supplier offer analysis · {escape(report.project_id)}</h1>
<p>As of {report.as_of.isoformat()}, maximum age {report.max_age_days} days ·
currencies: {escape(", ".join(report.currencies) or "none")}.</p>
<p class="notice">These are manually captured offers and mathematical quantity estimates.
Availability and lead times are recorded claims, not live checks. No currency conversion,
part substitution, order, purchasing, or release approval is implied.</p></header>
<section><h2>Selected evidence</h2><p>Parts receipt: <code>{escape(report.parts_receipt)}</code> ·
SHA-256 <code>{report.parts_receipt_sha256}</code> · current source:
<strong>{"MATCH" if report.parts_source_current else "STALE"}</strong>.</p>
<p><a href="parts-report.json">Retained parts report</a> ·
<a href="before-snapshot.json">Before snapshot</a> ·
<a href="after-snapshot.json">After snapshot</a>.</p>
<div class="scroll"><table><thead><tr><th>Snapshot</th><th>ID</th><th>Observed</th>
<th>Source commit</th><th>Freshness</th><th>Catalog check</th><th>SHA-256</th></tr></thead><tbody>{summaries}</tbody></table></div>
<p>Fitted references without a BOM line: {escape(", ".join(report.unresolved_references) or "none")}.</p></section>
<section><h2>Offer comparison</h2><p>Cost bars compare only two priced offers in the same
currency for the same supplier, SKU, and break. Totals require explicit packaging terms.</p>
<div class="scroll"><table><thead><tr><th>Part and offer</th><th>Change</th><th>Before</th>
<th>After</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section><h2>Review issues</h2><ul>{issues}</ul><h3>Snapshot validation</h3>
<ul>{validation_issues}</ul></section>
<section><h2>Parts source identity</h2><div class="scroll"><table><thead><tr>
<th>Path</th><th>SHA-256</th></tr></thead><tbody>{source_rows}</tbody></table></div></section>
<p><a href="supplier-analysis.json">Structured analysis receipt</a></p></main></html>"""
