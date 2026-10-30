"""Offline, escaped project review overview markup."""

from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

from .contracts import relative_path_from, repo_path
from .review_overview_models import OverviewItem, OverviewLink, ReviewOverviewReport
from .schematic_geometry_source import source_tree_sha256

_LABELS = {
    "native": "Schematic and PCB",
    "findings": "Findings explorer",
    "parts": "BOM and parts",
    "three_d": "3D and CAD",
    "simulation": "Simulation charts",
    "verification": "Verification",
}

_STYLE = """
:root{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
line-height:1.5;color:#1d3040;background:#f2f5f7}*{box-sizing:border-box}body{margin:0}
main{max-width:1160px;margin:auto;padding:40px 22px 70px}header{margin-bottom:25px}
h1{font-size:clamp(2rem,4vw,3rem);line-height:1.1;letter-spacing:-.035em;margin:8px 0}
h2{font-size:1.18rem;margin:0 0 8px}p{margin:8px 0}.eyebrow{font-size:.76rem;
font-weight:700;text-transform:uppercase;letter-spacing:.13em;color:#426d70}
.lede,.muted{color:#506374}.lede{max-width:760px}.notice{background:#e8f2f1;
border-left:4px solid #3f8580;padding:14px 17px;border-radius:5px;margin:20px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:16px}
.card{background:#fff;border:1px solid #d7e0e5;border-radius:12px;padding:20px;min-width:0}
.badges{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.badge{border-radius:999px;
padding:4px 10px;background:#e8edf0;font-size:.78rem;font-weight:700}
.current{background:#dceee8;color:#185847}.stale,.missing,.unavailable{background:#fce5df;
color:#883b2b}.unknown,.not-selected{background:#fff0d2;color:#795519}
a{color:#165d6c;text-underline-offset:3px}a:focus-visible,summary:focus-visible{
outline:3px solid #42938d;outline-offset:3px}ul{padding-left:1.2rem;margin:8px 0}
li{margin:5px 0;overflow-wrap:anywhere}code{font:0.81rem ui-monospace,SFMono-Regular,monospace;
overflow-wrap:anywhere}small{color:#627383}details{margin-top:12px}summary{cursor:pointer;font-weight:600}
.source{background:#fff;border:1px solid #d7e0e5;border-radius:12px;padding:20px;margin:22px 0}
footer{font-size:.8rem;color:#637684;margin-top:28px}
"""


def _href(root: Path, directory: Path, path: str) -> str:
    target = repo_path(root, path)
    return escape(quote(relative_path_from(target, directory).as_posix(), safe="/.-_"), quote=True)


def _links(root: Path, directory: Path, links: tuple[OverviewLink, ...]) -> str:
    if not links:
        return '<p class="muted">No verified local view is available.</p>'
    rows: list[str] = []
    for link in links:
        qualifier = "receipt hash matched" if link.receipt_bound else "snapshot hash only"
        rows.append(
            f'<li><a href="{_href(root, directory, link.path)}">{escape(link.label)}</a> '
            f"<small>({qualifier}; SHA-256 {escape(link.sha256[:12])}…)</small></li>"
        )
    return "<ul>" + "".join(rows) + "</ul>"


def _card(root: Path, directory: Path, item: OverviewItem) -> str:
    detail = "".join(f"<li>{escape(issue)}</li>" for issue in item.issues)
    identity = (
        f"<p><small>Source commit:</small> <code>{escape(item.source_commit)}</code></p>"
        if item.source_commit
        else ""
    )
    source = (
        f"<p><small>{'Checkout inputs' if item.kind == 'verification' else 'Source files'}:"
        f"</small> {len(item.source_hashes)}; "
        f"<small>inventory SHA-256:</small> <code>{source_tree_sha256(item.source_hashes)}</code></p>"
        if item.source_hashes
        else '<p class="muted">No source hash inventory in this receipt.</p>'
    )
    selected = (
        f"<p><small>Selected:</small> <code>{escape(item.selected_path)}</code></p>"
        if item.selected_path
        else '<p class="muted">No receipt selected.</p>'
    )
    class_name = item.freshness.lower().replace("_", "-")
    return (
        '<article class="card">'
        f"<h2>{escape(_LABELS[item.kind])}</h2>"
        f'<div class="badges"><span class="badge">{escape(item.status)}</span>'
        f'<span class="badge {class_name}">{escape(item.freshness.replace("_", " "))}</span></div>'
        + selected
        + identity
        + source
        + _links(root, directory, item.links)
        + (f"<ul>{detail}</ul>" if detail else "")
        + "</article>"
    )


def render_review_overview(root: Path, report: ReviewOverviewReport) -> str:
    """Show receipt state and provenance without implying engineering readiness."""
    directory = Path(report.output_directory)
    inventory_hash = source_tree_sha256(report.current_source_hashes)
    cards = "".join(_card(root, directory, item) for item in report.items)
    manifest = _href(root, directory, report.project_manifest)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<title>Project review overview: {escape(report.project_id)}</title><style>{_STYLE}</style></head>
<body><main><header><p class="eyebrow">Project review · selected evidence</p>
<h1>{escape(report.project_id)}</h1><p class="lede">One local index of explicitly selected receipts.
Current means recorded bytes matched when this page was generated. It is not an electrical,
mechanical, purchasing, manufacturing, or release approval.</p></header>
<div class="notice"><strong>Reading the states:</strong> Missing is a selected absent receipt;
stale means source or a recorded artifact changed; unavailable means the receipt could not be
validated; unknown means its saved identity is insufficient. Unselected categories were not searched.</div>
<section class="source"><h2>Current project context</h2>
<p><a href="{manifest}">Project manifest</a> · SHA-256 <code>{report.project_manifest_sha256}</code></p>
<p>KiCad toolchain: <strong>{escape(report.toolchain_id)}</strong> · {escape(report.kicad_version)}</p>
<p>Declared source inventory: {len(report.current_source_hashes)} file(s) · SHA-256
<code>{inventory_hash}</code></p><p class="muted">Exact file hashes and every selected receipt state are in
<a href="overview.json">overview.json</a>.</p></section>
<div class="grid">{cards}</div><footer>Local snapshot only. Recreate this overview after source or receipts change.
No tools were rerun to make this page.</footer></main></body></html>
"""
