"""Offline face-margin view beside the retained 3D assembly viewer."""

from __future__ import annotations

from html import escape

from .assembly_clearance_models import AssemblyClearanceReport

_FACES = (
    ("x_min", "Left"),
    ("x_max", "Right"),
    ("y_min", "Bottom"),
    ("y_max", "Top"),
    ("z_min", "Back"),
    ("z_max", "Front"),
)


def render_assembly_clearance(report: AssemblyClearanceReport) -> str:
    issues = "".join(f"<li>{escape(item)}</li>" for item in report.issues)
    rows = "".join(
        f"<tr><th>{label} ({key})</th><td>{report.face_margins_mm[key]:.4f} mm</td>"
        f"<td>{'Outside box' if report.face_margins_mm[key] < 0 else 'Inside box'}</td></tr>"
        for key, label in _FACES
        if key in report.face_margins_mm
    )
    measurement = (
        f"<p>Minimum signed face margin: <strong>{report.minimum_margin_mm:.4f} mm</strong>; "
        f"required margin: <strong>{report.required_margin_mm:g} mm</strong>; "
        f"referenced mesh vertices: {report.referenced_vertices}.</p>"
        if report.minimum_margin_mm is not None
        else "<p>No clearance measurement is available for this source and placement.</p>"
    )
    surface = (
        f"<p>Closest board/enclosure mesh surface gap: <strong>{report.surface_gap_mm:.4f} mm"
        f"</strong>; status: <strong>{escape(report.surface_status.lower())}</strong>; "
        f"triangles: {report.board_triangles} board and {report.enclosure_triangles} enclosure; "
        f"pairs evaluated: {report.surface_pairs_tested}."
        + (
            f" First intersecting triangle pair: {report.first_surface_intersection}."
            if report.first_surface_intersection is not None
            else ""
        )
        + "</p>"
        if report.surface_gap_mm is not None
        else "<p>Enclosure mesh surface intersection and gap are unassessed.</p>"
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Assembly clearance: {escape(report.project_id)}</title><style>
body{{font:1rem/1.5 system-ui,sans-serif;background:#f5f8fa;color:#183039;margin:0}}
main{{max-width:1200px;margin:auto;padding:1rem 1.5rem}}section{{background:white;padding:1rem 1.5rem;
border:1px solid #cfdae0;border-radius:.5rem;margin:1rem 0}}h1{{margin-bottom:.2rem}}
table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #d7e1e5;padding:.6rem;text-align:left}}
.state{{font-weight:700;padding:.5rem .8rem;background:#e7f0fa;display:inline-block;border-radius:.3rem}}
.note{{background:#fff1d4;padding:.8rem}}iframe{{width:100%;height:600px;border:1px solid #9baeb8}}
a{{color:#075d76}}code{{overflow-wrap:anywhere}}</style></head><body><main>
<h1>Assembly clearance: {escape(report.project_id)}</h1>
<p class="state">{escape(report.status.replace("_", " "))}</p>
<p class="note">Box margins use the project-authored rectangular free-space region.
Mesh surface gap and intersections use the retained board and enclosure triangles.
Solid containment, watertightness, fasteners, mating features, and flexible parts remain unassessed.
This receipt does not certify fit or authorize a build.</p>
<section><h2>Declared free space and margins</h2><p>Basis: {escape(report.free_space.basis)}.</p>
<p>Lower bounds: <code>{escape(str(report.free_space.lower))}</code>; upper bounds:
<code>{escape(str(report.free_space.upper))}</code> in the declared enclosure model unit.</p>
{measurement}<table><thead><tr><th>Free-space face</th><th>Signed margin</th><th>Position</th></tr></thead>
<tbody>{rows or '<tr><td colspan="3">Unassessed</td></tr>'}</tbody></table></section>
<section><h2>Board and enclosure mesh surfaces</h2>{surface}</section>
<section><h2>3D board and enclosure</h2><p>The viewer shows the selected model placement.
Use the face margins above to review the authored box separately.</p>
<iframe src="assembly/index.html" title="Retained 3D board and enclosure viewer"></iframe>
<p><a href="assembly/index.html">Open the 3D viewer directly</a></p></section>
<section><h2>Coverage and issues</h2><ul>{issues}</ul></section>
<section><h2>Source identity</h2><p>Assembly receipt: <code>{escape(report.assembly_review)}</code>
SHA-256 <code>{report.assembly_review_sha256}</code>.</p>
<p>Clearance contract: <code>{escape(report.clearance_contract)}</code>
SHA-256 <code>{report.clearance_contract_sha256}</code>.</p>
<p><a href="assembly-clearance.json">Structured clearance receipt</a></p></section>
</main></body></html>"""
