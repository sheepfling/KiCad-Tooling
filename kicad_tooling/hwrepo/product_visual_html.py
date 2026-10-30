"""Offline assembly hierarchy and authored connection cards for one variant."""

from __future__ import annotations

from html import escape

from .product_visual_models import ProductVisualEndpoint, ProductVisualReport

_STYLE = """
body{font:1rem/1.5 system-ui,sans-serif;color:#203044;background:#f3f6f7;margin:0}
main{max-width:1450px;margin:auto;padding:1.5rem}section{background:#fff;border:1px solid #d7e0e3;
border-radius:.6rem;padding:1rem;margin:1rem 0}h1{margin-bottom:.2rem}a{color:#075d76}
.note{background:#fff3d8;padding:.7rem}.muted{color:#52687a}.scroll{overflow:auto;max-height:70vh}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #e2e8eb;padding:.6rem;
text-align:left;vertical-align:top}th{background:#f7f9fa}code{overflow-wrap:anywhere}
.omitted{opacity:.65}.unresolved{background:#fff3d8}.relations{display:grid;grid-template-columns:
repeat(auto-fit,minmax(min(100%,460px),1fr));gap:.75rem}.relation{border:1px solid #cfdbdf;
border-radius:.5rem;padding:.75rem}.connection{display:grid;grid-template-columns:minmax(0,1fr) auto
minmax(0,1fr);align-items:center;gap:.6rem}.endpoint{border:1px solid #d7e0e3;background:#f7f9fa;
border-radius:.4rem;padding:.5rem;overflow-wrap:anywhere}.edge{font-size:1.3rem;color:#27728d}
.relation.functional .edge{color:#9b5b20}.relation.mechanical .edge{color:#6b5b91}
.relation.protocol .edge{color:#367055}
input{font:inherit;padding:.5rem;width:min(100%,30rem)}[hidden]{display:none!important}
"""

_SCRIPT = """
const search=document.getElementById('visual-search');
function filter(){const query=search.value.toLowerCase();let shown=0;
document.querySelectorAll('.searchable').forEach(item=>{
item.hidden=!item.textContent.toLowerCase().includes(query);if(!item.hidden)shown++;
});document.getElementById('count').textContent=shown+' item(s) shown';}
search.addEventListener('input',filter);filter();
"""


def _endpoint(value: ProductVisualEndpoint) -> str:
    identity = f"{value.instance or 'UNKNOWN'} / pin {value.pin or 'UNKNOWN'}"
    interface = (
        f"<br>Interface <code>{escape(value.interface_id)}</code> / "
        f"<code>{escape(value.interface_pin or 'UNKNOWN')}</code>"
        if value.interface_id
        else ""
    )
    return (
        f'<div class="endpoint"><strong>{escape(value.terminal_id)}</strong><br>'
        f"{escape(identity)}{interface}<br><small>{value.status}</small></div>"
    )


def render_product_visual(report: ProductVisualReport) -> str:
    """Keep omitted and unresolved relationships visible beside valid projections."""
    harness_ids = {item.harness_id for item in report.harnesses}
    instances = "".join(
        f'<tr class="searchable {"omitted" if item.population == "OMITTED" else ""} '
        f'{"unresolved" if item.kind == "UNRESOLVED" else ""}">'
        f'<td style="padding-left:{min(item.path.count(".") + 1, 32) * 1.3:.1f}rem">'
        f"<code>{escape(item.path or 'ROOT')}</code></td><td>{escape(item.item)}</td>"
        f"<td>{item.quantity}</td><td>{item.kind}</td><td>{item.population}</td>"
        f"<td>{escape(item.project_id or '')}</td></tr>"
        for item in report.instances
    )
    relations = "".join(
        f'<article class="relation searchable {item.kind} {item.population.lower()}">'
        f"<h3>{escape(item.id)} · {escape(item.kind.title())}</h3>"
        f'<div class="connection">{_endpoint(item.from_endpoint)}'
        f'<span class="edge" aria-hidden="true">⟶</span>{_endpoint(item.to_endpoint)}</div>'
        f"<p><strong>{item.population}</strong>; assurance {escape(item.assurance)}"
        f"; harness "
        + (
            f'<a href="#harness-{escape(item.harness, quote=True)}">{escape(item.harness)}</a>'
            if item.harness and item.harness in harness_ids
            else escape(item.harness or "none")
        )
        + f"; evidence {escape(', '.join(item.evidence) or 'none')}.</p></article>"
        for item in report.relations
    )
    harnesses = "".join(
        f'<tr class="searchable" id="harness-{escape(item.harness_id, quote=True)}">'
        f"<th>{escape(item.harness_id)}</th>"
        f"<td>{escape(item.instance)}</td><td>{item.length_mm:g} mm</td>"
        f"<td>{item.conductor_area_mm2:g} mm²</td>"
        f"<td>{escape(', '.join(item.endpoint_terminal_ids))}</td>"
        f"<td>{escape(', '.join(item.electrical_connection_ids))}</td></tr>"
        for item in report.harnesses
    )
    projects = "".join(
        f"<tr><th>{escape(item.project_id)}</th><td>{item.status}</td>"
        f"<td><code>{escape(item.config_path or 'UNKNOWN')}</code></td>"
        f"<td>{len(item.source_hashes)}</td><td>{escape(item.issue or '')}</td></tr>"
        for item in report.projects
    )
    source = "".join(
        f"<li><code>{escape(name)}</code> SHA-256 <code>{sha}</code></li>"
        for name, sha in sorted(report.source_hashes.items())
    )
    issues = "".join(f"<li>{escape(item)}</li>" for item in report.issues)
    open_items = "".join(f"<li>{escape(item)}</li>" for item in report.open_items)
    projection_links = (
        '<a href="system.json">Canonical system view</a> · '
        '<a href="harness-schedule.json">Canonical harness schedule</a> · '
        if report.system_projection and report.harness_projection
        else "Canonical system and harness projections are unavailable for this review · "
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Product view: {escape(report.product_id)} / {escape(report.variant_id)}</title>
<style>{_STYLE}</style></head><body><main>
<h1>Product view: {escape(report.product_id)} / {escape(report.variant_id)}</h1>
<p>Product revision <strong>{escape(report.product_revision)}</strong>; variant revision
<strong>{escape(report.variant_revision)}</strong>; source status <strong>{report.status}</strong>.</p>
<p class="note">All relationships shown are authored product claims. A line does not establish
observed wiring, electrical continuity, harness construction, or build approval. Omitted and
unresolved items remain visible for review.</p>
<section><h2>Explore this variant</h2><label for="visual-search">Search instances and relations</label>
<p><input id="visual-search" type="search" autocomplete="off"></p>
<p id="count" aria-live="polite"></p></section>
<section><h2>Assembly hierarchy</h2><div class="scroll"><table><thead><tr><th>Instance path</th>
<th>Item</th><th>Quantity</th><th>Kind</th><th>Variant</th><th>Project</th></tr></thead>
<tbody>{instances}</tbody></table></div></section>
<section><h2>Interface and system relationships</h2><p class="muted">Blue electrical,
brown functional, purple mechanical, and green protocol arrows have different meanings. Endpoints retain
terminal IDs, instance paths, pins, and interface identities when authored.</p>
<div class="relations">{relations}</div></section>
<section><h2>Harness schedule</h2><p>These rows come from the canonical selected-variant
schedule when the source product passes its typed policy checks.</p><div class="scroll"><table>
<thead><tr><th>Harness</th><th>Instance</th><th>Length</th><th>Conductor area</th>
<th>Endpoints</th><th>Connections</th></tr></thead><tbody>{harnesses}</tbody></table></div></section>
<section><h2>Project source identity</h2><table><thead><tr><th>Project</th><th>Status</th>
<th>Config</th><th>Source files</th><th>Issue</th></tr></thead><tbody>{projects}</tbody></table>
<details><summary>All retained source hashes</summary><ul>{source}</ul></details></section>
<section><h2>Issues and authored open items</h2><h3>Review issues</h3><ul>{issues}</ul>
<h3>Product open items</h3><ul>{open_items}</ul></section>
<p><a href="product.json">Exact authored product record</a> ·
<a href="product-index.json">Selected product index</a> · {projection_links}
<a href="product-visual.json">Structured visual receipt</a></p>
</main><script>{_SCRIPT}</script></body></html>"""
