"""Offline review page for authored product variant BOM differences."""

from __future__ import annotations

from html import escape

from .product_variant_bom_models import (
    ProductVariantBomReport,
    VariantBomInstanceState,
)


def _instance(state: VariantBomInstanceState) -> str:
    identity = f"{state.part_id or 'unresolved'} @ {state.revision or '?'}"
    return f"{state.population}; {identity}; {state.quantity} each; {state.item}"


def render_product_variant_bom(report: ProductVariantBomReport) -> str:
    """Keep omitted and unresolved instances visible beside canonical BOM rows."""
    instances = "".join(
        f"<tr class='{escape(item.change.lower())}'><th><code>{escape(item.path or 'ROOT')}</code></th>"
        f"<td>{item.change}</td><td>{escape(_instance(item.before))}</td>"
        f"<td>{escape(_instance(item.after))}</td></tr>"
        for item in report.instances
    )
    parts = "".join(
        f"<tr class='{escape(item.change.lower())}'><th><code>{escape(item.part_id)}</code> "
        f"@ {escape(item.revision)}</th><td>{item.change}</td>"
        f"<td>{item.before.quantity if item.before else '—'}</td>"
        f"<td>{item.after.quantity if item.after else '—'}</td>"
        f"<td>{escape(item.before.instances if item.before else '—')}</td>"
        f"<td>{escape(item.after.instances if item.after else '—')}</td></tr>"
        for item in report.parts
    )
    sources = "".join(
        f"<tr><th><code>{escape(path)}</code></th><td><code>{sha}</code></td></tr>"
        for path, sha in sorted(report.source_hashes.items())
    )
    issues = "".join(f"<li>{escape(issue)}</li>" for issue in report.issues)
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Product variant BOM comparison</title>
<style>body{{font:15px/1.45 system-ui;color:#203044;background:#f3f6f8;margin:0}}
main{{max-width:1250px;margin:auto;padding:1.5rem}}section{{background:white;padding:1rem;
border-radius:.6rem;margin:1rem 0}}table{{border-collapse:collapse;width:100%}}
th,td{{border-bottom:1px solid #dbe4ea;padding:.6rem;text-align:left;vertical-align:top}}
td{{overflow-wrap:anywhere}}.scroll{{overflow:auto}}.changed{{background:#fff8e5}}
.added{{background:#e9f7ee}}.removed{{background:#fff0ee}}a{{color:#075d76}}</style>
<main><h1>Product variant BOM comparison · {escape(report.product_id)}</h1>
<p>Product revision {escape(report.product_revision)} · {escape(report.before_variant)}
@ {escape(report.before_variant_revision)} → {escape(report.after_variant)}
@ {escape(report.after_variant_revision)} · {report.status}</p>
<p><a href="comparison.json">Structured comparison</a> ·
<a href="before/index.html">Before variant review</a> ·
<a href="after/index.html">After variant review</a></p>
<p>Canonical BOM projection: {"available" if report.bom_projection else "unavailable"}.
Authoring and catalog evidence only; no purchase, substitute, or build approval.</p>
<section><h2>Issues</h2><ul>{issues or "<li>None recorded.</li>"}</ul></section>
<section><h2>Instance population · {len(report.instances)}</h2><div class="scroll"><table>
<thead><tr><th>Path</th><th>Change</th><th>Before</th><th>After</th></tr></thead>
<tbody>{instances}</tbody></table></div></section>
<section><h2>Grouped parts · {len(report.parts)}</h2><div class="scroll"><table>
<thead><tr><th>Part @ revision</th><th>Change</th><th>Before qty</th>
<th>After qty</th><th>Before instances</th><th>After instances</th></tr></thead>
<tbody>{parts}</tbody></table></div></section>
<section><h2>Source identity</h2><p><code>{escape(report.product_path)}</code>
SHA-256 <code>{report.product_sha256}</code></p><div class="scroll"><table>
<thead><tr><th>Path</th><th>SHA-256</th></tr></thead><tbody>{sources}</tbody>
</table></div></section></main></html>"""
