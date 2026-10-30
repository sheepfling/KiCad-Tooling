"""Render a portable, explicitly scoped mechanical assembly overlay."""

from __future__ import annotations

import base64
import json
from html import escape

from .assembly_review_models import AssemblyReviewReport


def render_assembly_review(
    report: AssemblyReviewReport, board: bytes, enclosure: bytes | None
) -> str:
    """Embed verified model bytes so local file viewing needs no server."""
    ready = report.status != "INCOMPLETE" and enclosure is not None and report.placement is not None
    config: dict[str, object] = {"board_unit": report.board_unit}
    if ready and report.placement is not None:
        config.update(
            enclosure_unit=report.enclosure_unit,
            translation_mm=report.placement.translation_mm,
            rotation_xyzw=report.placement.rotation_xyzw,
        )
    configuration = json.dumps(config, separators=(",", ":")).replace("<", "\\u003c")
    issues = "".join(f"<li>{escape(issue)}</li>" for issue in report.issues)
    source = "".join(
        f"<li><code>{escape(name)}</code> SHA-256 <code>{sha}</code></li>"
        for name, sha in sorted(report.source_hashes.items())
    )
    placement = report.placement
    transform = (
        f"<p>Transform: <code>{escape(placement.source_frame)}</code> to "
        f"<code>{escape(placement.target_frame)}</code>; translation "
        f"<code>{escape(str(placement.translation_mm))}</code> mm; quaternion XYZW "
        f"<code>{escape(str(placement.rotation_xyzw))}</code>.</p>"
        if ready and placement is not None
        else "<p>No verified enclosure placement is available for a combined view.</p>"
    )
    enclosure_data = (
        '<script id="assembly-glb-data" type="application/octet-stream">'
        + base64.b64encode(enclosure).decode("ascii")
        + "</script>"
        if ready and enclosure is not None
        else ""
    )
    enclosure_link = (
        '<a href="enclosure.glb">Retained enclosure GLB</a> · ' if enclosure is not None else ""
    )
    controls = "".join(
        f'<button type="button" data-view="{name}">{name.title()}</button>'
        for name in ("fit", "top", "bottom", "front", "back", "left", "right")
    )
    controls += "".join(
        f'<button type="button" data-action="{name}">{name.replace("-", " ").title()}</button>'
        for name in ("zoom-in", "zoom-out", "pan-left", "pan-right", "pan-up", "pan-down")
    )
    if ready:
        controls += (
            '<button type="button" data-model="board" aria-pressed="true">Board visible</button>'
            '<button type="button" data-model="enclosure" aria-pressed="true">Enclosure visible</button>'
        )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mechanical assembly review: {escape(report.project_id)}</title><style>
body{{font:1rem/1.5 system-ui,sans-serif;color:#183039;background:#f9fbfc;margin:0;padding:1rem}}
main{{max-width:1200px;margin:auto}}h1{{margin:.2rem 0}}p{{margin:.5rem 0}}
#viewport{{height:min(68vh,760px);min-height:340px;border:1px solid #9baeb8;border-radius:.4rem;overflow:hidden}}
#viewport canvas{{display:block}}.controls{{display:flex;flex-wrap:wrap;gap:.5rem;margin:.7rem 0}}
button{{padding:.5rem .8rem;border:1px solid #456374;border-radius:.3rem;background:white;color:#123a4a;cursor:pointer}}
button:focus-visible,canvas:focus-visible{{outline:3px solid #087eac;outline-offset:2px}}
.note{{background:#fff4d6;padding:.7rem}}code{{overflow-wrap:anywhere}}
</style></head><body><main><h1>Mechanical assembly review: {escape(report.project_id)}</h1>
<p>Status: <strong>{report.status}</strong>; board model coverage: <strong>{escape(report.model_status)}</strong>.</p>
<p>Board export variant: <strong>{escape(report.assembly_variant or "default")}</strong>.</p>
<p class="note">Visual geometry overlay only. No interference, clearance, or fit calculation was performed.</p>
<p>Board frame <code>{escape(report.board_frame)}</code> ({report.board_unit}); enclosure frame
<code>{escape(report.enclosure_frame)}</code> ({report.enclosure_unit}).</p>{transform}
<div class="controls" role="group" aria-label="Model view controls">{controls}</div>
<div id="viewport" role="img" aria-label="Interactive board and enclosure review"></div>
<p id="viewer-status" role="status" aria-live="polite">Preparing viewer…</p>
<p>Drag to rotate; Shift-drag or right-drag to pan; scroll to zoom. Focus the model and use
arrow keys to rotate, Shift plus arrow keys to pan, + or - to zoom, and F to fit.</p>
<h2>Scope and issues</h2><ul>{issues}</ul><p>Model sources and placement were selected explicitly.
No tolerance, mating feature, enclosure interior, or clearance was assessed.</p>
<h2>Source identity</h2><ul>{source}</ul>
<p>Board receipt <code>{escape(report.board_receipt)}</code> SHA-256
<code>{report.board_receipt_sha256}</code>; board GLB SHA-256 <code>{report.board_glb_sha256}</code>.</p>
<p>Placement contract <code>{escape(report.placement_contract)}</code> SHA-256
<code>{report.placement_contract_sha256}</code>; enclosure model
<code>{escape(report.enclosure_model)}</code> expected SHA-256
<code>{report.enclosure_expected_sha256}</code>; observed
<code>{report.enclosure_sha256 or "MISSING"}</code>.</p>
<p><a href="board.glb">Retained board GLB</a> · {enclosure_link}
<a href="assembly-review.json">Structured review receipt</a> ·
<a href="viewer-license.txt">Viewer license</a></p>
<script id="glb-data" type="application/octet-stream">{base64.b64encode(board).decode("ascii")}</script>
{enclosure_data}<script id="assembly-config" type="application/json">{configuration}</script>
<script src="viewer.js"></script></main></body></html>"""
