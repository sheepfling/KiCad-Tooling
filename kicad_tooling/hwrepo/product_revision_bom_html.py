"""Offline comparison of two retained authored product BOM revisions."""

from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

from .contracts import relative_path_from, repo_path
from .product_revision_bom_models import ProductRevisionBomReport, ProductRevisionSnapshot
from .product_variant_bom_models import VariantBomInstanceState


def _state(value: VariantBomInstanceState | None) -> str:
    if value is None:
        return "—"
    return (
        f"{value.population}; {value.part_id or 'unresolved'} @ {value.revision or '?'}; "
        f"{value.quantity} each; {value.item}"
    )


def _snapshot(root: Path, output: Path, label: str, value: ProductRevisionSnapshot) -> str:
    page = repo_path(root, value.view).parent / "index.html"
    link = escape(quote(relative_path_from(page, output).as_posix(), safe="/.-_"), quote=True)
    return (
        '<article class="card">'
        f"<h2>{escape(label)}</h2>"
        f"<p>{escape(value.variant_id)} @ {escape(value.variant_revision)} · "
        f"product @ {escape(value.product_revision)}</p>"
        f"<p>Captured view: {escape(value.view_status)} · source now "
        f"{escape(value.source_relation)}</p>"
        f'<p><a href="{link}">Saved product view</a> · SHA-256 '
        f"<code>{value.view_sha256}</code></p>"
        f"<p>Product <code>{escape(value.product_path)}</code> · "
        f"SHA-256 <code>{value.product_sha256}</code></p>"
        f"<p>Parts catalog: <code>{escape(value.parts_catalog_path or 'not retained')}</code>"
        f" · SHA-256 <code>{value.parts_catalog_sha256 or 'unknown'}</code></p></article>"
    )


def render_product_revision_bom(root: Path, report: ProductRevisionBomReport) -> str:
    output = Path(report.output_directory)
    instances = "".join(
        f'<tr class="{escape(item.change.lower())}"><th><code>{escape(item.path or "ROOT")}</code></th>'
        f"<td>{escape(item.change)}</td><td>{escape(_state(item.before))}</td>"
        f"<td>{escape(_state(item.after))}</td></tr>"
        for item in report.instances
    )
    parts = "".join(
        f'<tr class="{escape(item.change.lower())}"><th><code>{escape(item.part_id)}</code> '
        f"@ {escape(item.revision)}</th><td>{escape(item.change)}</td>"
        f"<td>{item.before.quantity if item.before else '—'}</td>"
        f"<td>{item.after.quantity if item.after else '—'}</td>"
        f"<td>{escape(item.before.instances if item.before else '—')}</td>"
        f"<td>{escape(item.after.instances if item.after else '—')}</td></tr>"
        for item in report.parts
    )
    issues = "".join(f"<li>{escape(item)}</li>" for item in report.issues)
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Product revision BOM · {escape(report.product_id)}</title>
<style>:root{{font:15px/1.45 system-ui;color:#203044;background:#f3f6f8}}
body{{margin:0}}main{{max-width:1250px;margin:auto;padding:24px}}section,.card{{background:white;
padding:18px;border:1px solid #d8e1e8;border-radius:12px;margin:16px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:16px}}
.grid .card{{margin:0}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;
vertical-align:top;padding:9px;border-bottom:1px solid #e2e8ee}}.scroll{{overflow:auto}}
.changed{{background:#fff8e5}}.added{{background:#e9f7ee}}.removed{{background:#fff0ee}}
code{{overflow-wrap:anywhere}}a{{color:#075d76}}a:focus-visible{{outline:3px solid #318e9c}}
</style><main><h1>Product revision BOM · {escape(report.product_id)}</h1>
<p>{escape(report.status)} · variant IDs {escape(report.variant_relation.lower())} ·
product paths {escape(report.product_path_relation.lower())} ·
canonical BOM {"available" if report.bom_projection else "unavailable"}.</p>
<p>Selected saved views are compared as captured. HISTORICAL source does not apply to the
live checkout. Authored BOM projection does not verify observed board population or approve purchases.</p>
<p><a href="comparison.json">Structured comparison</a></p><div class="grid">
{_snapshot(root, output, "Baseline", report.baseline)}
{_snapshot(root, output, "Candidate", report.candidate)}</div>
<section><h2>Issues</h2><ul>{issues or "<li>None recorded.</li>"}</ul></section>
<section><h2>Procurement instances · {len(report.instances)}</h2><div class="scroll"><table>
<thead><tr><th>Path</th><th>Change</th><th>Baseline</th><th>Candidate</th></tr></thead>
<tbody>{instances}</tbody></table></div></section>
<section><h2>Grouped parts · {len(report.parts)}</h2><div class="scroll"><table>
<thead><tr><th>Part @ revision</th><th>Change</th><th>Before qty</th><th>After qty</th>
<th>Before instances</th><th>After instances</th></tr></thead><tbody>{parts}</tbody></table>
</div></section><p>Review only; no build, substitute, or purchasing approval.</p></main></html>"""
