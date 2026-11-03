"""Offline named-variant BOM review with links to source drawings."""

from __future__ import annotations

from html import escape

from .cross_probe_models import CrossProbeReport
from .variant_parts_review_models import VariantPartsReviewReport


def render_variant_parts_review(
    report: VariantPartsReviewReport, navigation: CrossProbeReport
) -> str:
    anchors = {
        entry.reference.casefold(): f"navigation/index.html#component-{index}"
        for index, entry in enumerate(navigation.entries, 1)
    }
    lines = "".join(
        "<tr><td>"
        + escape(line.part_id)
        + "</td><td>"
        + escape(line.manufacturer)
        + "</td><td>"
        + escape(line.mpn)
        + "</td><td>"
        + ", ".join(
            f'<a href="{escape(anchors[ref.casefold()], quote=True)}">{escape(ref)}</a>'
            if ref.casefold() in anchors
            else escape(ref)
            for ref in line.references
        )
        + "</td><td>"
        + str(line.per_board)
        + "</td><td>"
        + str(line.quantity)
        + "</td></tr>"
        for line in report.plan.lines
    )
    population = "".join(
        "<tr><td>"
        + (
            f'<a href="{escape(anchors[item.reference.casefold()], quote=True)}">'
            f"{escape(item.reference)}</a>"
            if item.reference.casefold() in anchors
            else escape(item.reference)
        )
        + "</td><td>"
        + ("DNP" if item.dnp else "BOM excluded" if item.exclude_from_bom else "Fitted")
        + "</td><td>"
        + escape(item.part_id or "Unresolved")
        + "</td><td>"
        + escape(item.value)
        + "</td><td>"
        + escape(item.footprint)
        + "</td></tr>"
        for item in report.plan.components
    )
    unresolved = "".join(
        "<li><strong>" + escape(item.reference) + "</strong>: " + escape(item.reason) + "</li>"
        for item in report.unresolved
    )
    findings = "".join(
        "<li><strong>" + escape(item.code) + "</strong>: " + escape(item.message) + "</li>"
        for item in report.plan.findings
    )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Named variant parts review</title>"
        "<style>body{font:16px system-ui;max-width:78rem;margin:auto;padding:2rem;"
        "background:#f5f7fa;color:#16243a}a{color:#075caa}table{border-collapse:collapse;"
        "width:100%;background:white}td,th{border:1px solid #c6d0dc;padding:.55rem;text-align:left}"
        "section{background:white;padding:1rem 1.5rem;margin:1rem 0;border-radius:.5rem}"
        "small{color:#46566d}</style><body><main>"
        f"<h1>{escape(report.project_id)} · {escape(report.assembly_variant)} parts</h1>"
        f"<p>Review state: <strong>{escape(report.plan.status)}</strong>. "
        "Quantities cover only matched fitted schematic and PCB references. "
        "Purchase and build approval are not implied.</p>"
        '<p><a href="navigation/index.html">Open schematic and board navigation</a> · '
        '<a href="bom.csv">Download review BOM CSV</a> · '
        '<a href="unresolved.csv">Download unresolved references CSV</a></p>'
        "<section><h2>Grouped quantities</h2><table><thead><tr><th>PART_ID</th>"
        "<th>Manufacturer</th><th>MPN</th><th>References</th><th>Per board</th>"
        "<th>Order quantity</th></tr></thead><tbody>"
        + (lines or '<tr><td colspan="6">No validated order lines.</td></tr>')
        + "</tbody></table></section><section><h2>Variant population</h2><table>"
        "<thead><tr><th>Reference</th><th>State</th><th>PART_ID</th><th>Value</th>"
        "<th>Footprint</th></tr></thead><tbody>"
        + (population or '<tr><td colspan="5">No reconciled components.</td></tr>')
        + "</tbody></table></section><section><h2>Unresolved population</h2><ul>"
        + (unresolved or "<li>None in the selected native variant exports.</li>")
        + "</ul></section><section><h2>Parts findings</h2><ul>"
        + (findings or "<li>None recorded by the parts planner.</li>")
        + "</ul></section><small>Native variant, project source, catalog and saved receipts "
        "are bound in variant-parts.json.</small></main></body></html>"
    )
