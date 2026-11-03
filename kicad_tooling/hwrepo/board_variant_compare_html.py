"""Offline native board-variant BOM comparison view."""

from __future__ import annotations

from html import escape

from .board_variant_compare_models import (
    BoardVariantComparisonReport,
    BoardVariantReferenceChange,
    BoardVariantState,
)


def _state(value: BoardVariantState | None) -> str:
    if value is None:
        return "—"
    return escape(
        f"Schematic {value.schematic}; PCB {value.board}; "
        f"{value.part_id or 'unresolved part'}; {value.value or '—'}; "
        f"{value.footprint or '—'}"
    )


def _reference_rows(items: tuple[BoardVariantReferenceChange, ...]) -> str:
    return "".join(
        f'<tr class="{item.change.lower()}"><th>{escape(item.reference)}</th>'
        f"<td>{item.change}</td><td>{_state(item.before)}</td>"
        f"<td>{_state(item.after)}</td></tr>"
        for item in items
    )


def _source_rows(report: BoardVariantComparisonReport) -> str:
    shared = "".join(
        f"<li><code>{escape(name)}</code> SHA-256 <code>{sha}</code></li>"
        for name, sha in sorted(report.source_hashes.items())
    )
    evidence = "".join(
        f"<h3>{escape(side.name)}</h3><ul>"
        + "".join(
            f"<li><code>{escape(name)}</code> SHA-256 <code>{sha}</code></li>"
            for name, sha in sorted(side.evidence_sha256.items())
        )
        + "</ul>"
        for side in (report.before, report.after)
    )
    return (
        f"<p>Findings view: <code>{escape(report.findings_view)}</code> "
        f"SHA-256 <code>{report.findings_view_sha256}</code>.</p>"
        f"<p>Design-lint receipt: <code>{escape(report.lint_report)}</code> "
        f"SHA-256 <code>{report.lint_report_sha256}</code>.</p>"
        f"<h3>Project source</h3><ul>{shared}</ul>{evidence}"
    )


def render_board_variant_comparison(report: BoardVariantComparisonReport) -> str:
    """Show reference and grouped fitted quantity changes without approval claims."""
    changed = tuple(item for item in report.references if item.change != "UNCHANGED")
    unchanged = tuple(item for item in report.references if item.change == "UNCHANGED")
    excluded = tuple(
        item
        for item in report.references
        if item.before is not None
        and item.after is not None
        and item.before.board != "FITTED"
        and item.after.board != "FITTED"
    )
    largest = max((max(item.before, item.after) for item in report.quantities), default=1)
    quantity_rows = "".join(
        f"<tr><th>{escape(item.part_id)}</th><td>{escape(item.value)}</td>"
        f"<td>{escape(item.footprint)}</td><td>{item.change}</td>"
        f'<td><span class="bar before" style="width:{100 * item.before / largest:.1f}%"></span>'
        f"{item.before} · {escape(', '.join(item.before_references))}</td>"
        f'<td><span class="bar after" style="width:{100 * item.after / largest:.1f}%"></span>'
        f"{item.after} · {escape(', '.join(item.after_references))}</td></tr>"
        for item in report.quantities
    )
    issues = "".join(f"<li>{escape(issue)}</li>" for issue in report.issues)
    unresolved = "".join(
        f"<li>{escape(side.name)}: "
        + (", ".join(escape(ref) for ref in side.unresolved_fitted) or "none")
        + "</li>"
        for side in (report.before, report.after)
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Board variant comparison: {escape(report.project_id)}</title>
<style>body{{font:1rem/1.5 system-ui,sans-serif;color:#243548;background:#f3f6f8;margin:0}}
main{{max-width:1300px;margin:auto;padding:1.5rem}}section{{background:white;border:1px solid #dae3e8;
border-radius:.6rem;padding:1rem;margin:1rem 0}}table{{border-collapse:collapse;width:100%}}
th,td{{padding:.6rem;text-align:left;border-bottom:1px solid #dce5e9;vertical-align:top}}
.scroll{{overflow:auto;max-height:70vh}}.changed{{background:#fff7e6}}.added{{background:#e9f7ed}}
.removed{{background:#fbeeee}}.bar{{display:block;height:.45rem;border-radius:1rem;min-width:0}}
.before{{background:#567e99}}.after{{background:#0b8b88}}code{{overflow-wrap:anywhere}}
.note{{background:#fff3d7;padding:.8rem}}details summary{{cursor:pointer}}</style></head>
<body><main><h1>Board variant comparison: {escape(report.project_id)}</h1>
<p>{escape(report.before.name)} → {escape(report.after.name)} · {len(changed)} changed references ·
{len(excluded)} excluded or DNP in both</p>
<p class="note">Population comes from saved named KiCad schematic and PCB exports. Fitted
quantities include only matching fitted PCB and schematic references with a PART_ID.
This view does not approve parts, purchasing, assembly, or release.</p>
<section><h2>Reference changes</h2><div class="scroll"><table><thead><tr>
<th>Reference</th><th>Change</th><th>{escape(report.before.name)}</th>
<th>{escape(report.after.name)}</th></tr></thead><tbody>{_reference_rows(changed)}</tbody></table></div>
<details><summary>{len(unchanged)} unchanged references</summary><div class="scroll"><table>
<thead><tr><th>Reference</th><th>Change</th><th>Before</th><th>After</th></tr></thead>
<tbody>{_reference_rows(unchanged)}</tbody></table></div></details></section>
<section><h2>Grouped fitted quantities</h2><div class="scroll"><table><thead><tr>
<th>Part ID</th><th>Value</th><th>Footprint</th><th>Change</th>
<th>{escape(report.before.name)}</th><th>{escape(report.after.name)}</th></tr></thead>
<tbody>{quantity_rows}</tbody></table></div></section>
<section><h2>Unresolved fitted references</h2><ul>{unresolved}</ul></section>
<section><h2>Issues</h2><ul>{issues or '<li>None recorded.</li>'}</ul></section>
<section><h2>Source and evidence</h2><details><summary>Show hashes and saved native files</summary>
{_source_rows(report)}</details><p><a href="comparison.json">Structured comparison record</a></p>
</section></main></body></html>"""
