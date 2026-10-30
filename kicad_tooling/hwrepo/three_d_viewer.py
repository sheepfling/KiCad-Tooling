"""Produce a portable, source-bound viewer snapshot of one retained GLB."""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path

from .evidence import digest
from .three_d_glb import inspect_glb

_ASSET = Path(__file__).parent / "assets" / "three_d_viewer.js"
_LICENSE = Path(__file__).parent / "assets" / "threejs-LICENSE.txt"


def write_viewer(
    directory: Path,
    project_id: str,
    model_status: str,
    glb_sha256: str,
    actions: Sequence[str],
    assembly_variant: str | None,
    source_sha256: Mapping[str, str],
    *,
    has_step: bool,
) -> dict[str, str] | None:
    """Embed the exact verified GLB so file:// viewing needs no network server."""
    path = directory / "board.glb"
    info = inspect_glb(path)
    if info is None or not info.offline:
        return None
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != glb_sha256:
        raise ValueError("Retained board.glb changed while the viewer was created")
    script = _ASSET.read_bytes()
    js_path = directory / "viewer.js"
    js_path.write_bytes(script)
    license_path = directory / "viewer-license.txt"
    license_path.write_bytes(_LICENSE.read_bytes())
    sources = "".join(
        f"<li><code>{escape(name)}</code> SHA-256 <code>{escape(sha)}</code></li>"
        for name, sha in sorted(source_sha256.items())
    )
    warnings = "".join(f"<li>{escape(action)}</li>" for action in actions)
    step_link = '<a href="board.step">Original STEP export</a> · ' if has_step else ""
    variant = escape(assembly_variant) if assembly_variant else "default"
    model = base64.b64encode(payload).decode("ascii")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>3D model: {escape(project_id)}</title><style>
body{{font:1rem/1.5 system-ui,sans-serif;color:#183039;background:#f9fbfc;margin:0;padding:1rem}}
main{{max-width:1200px;margin:auto}}h1{{margin:.2rem 0}}p{{margin:.5rem 0}}
#viewport{{height:min(68vh,760px);min-height:340px;border:1px solid #9baeb8;border-radius:.4rem;overflow:hidden}}
#viewport canvas{{display:block}}.controls{{display:flex;flex-wrap:wrap;gap:.5rem;margin:.7rem 0}}
button{{padding:.5rem .8rem;border:1px solid #456374;border-radius:.3rem;background:white;color:#123a4a;cursor:pointer}}
button:focus-visible,canvas:focus-visible{{outline:3px solid #087eac;outline-offset:2px}}
.note{{background:#fff4d6;padding:.7rem}}code{{overflow-wrap:anywhere}}
</style></head><body><main><h1>3D model: {escape(project_id)}</h1>
<p>Model coverage: <strong>{escape(model_status)}</strong>; assembly variant: {variant}.</p>
<p class="note">This is the retained GLB snapshot. It supports visual review, not mechanical fit or clearance approval.</p>
<div class="controls" role="group" aria-label="Model view controls">
<button type="button" data-view="fit">Fit</button>
<button type="button" data-view="top">Top</button>
<button type="button" data-view="bottom">Bottom</button>
<button type="button" data-view="front">Front</button>
<button type="button" data-view="back">Back</button>
<button type="button" data-view="left">Left</button>
<button type="button" data-view="right">Right</button>
<button type="button" data-action="zoom-in">Zoom in</button>
<button type="button" data-action="zoom-out">Zoom out</button>
<button type="button" data-action="pan-left">Pan left</button>
<button type="button" data-action="pan-right">Pan right</button>
<button type="button" data-action="pan-up">Pan up</button>
<button type="button" data-action="pan-down">Pan down</button></div>
<div id="viewport" role="img" aria-label="Interactive 3D board model"></div>
<p id="viewer-status" role="status" aria-live="polite">Preparing viewer…</p>
<p>Drag to rotate; Shift-drag or right-drag to pan; scroll to zoom. Focus the model and use arrow keys to rotate, Shift plus arrow keys to pan, + or - to zoom, and F to fit.</p>
<h2>Source identity</h2><ul>{sources}</ul>
<p>Retained GLB SHA-256: <code>{escape(glb_sha256)}</code>.</p>
<h2>Model and export notes</h2><ul>{warnings}</ul>
<p><a href="index.html">Board-view gallery</a> · <a href="board.glb">Original GLB export</a> ·
{step_link}<a href="visualization.json">Visualization receipt</a> ·
<a href="viewer-license.txt">Viewer license</a></p>
<script id="glb-data" type="application/octet-stream">{model}</script>
<script src="viewer.js"></script></main></body></html>
"""
    html_path = directory / "viewer.html"
    with html_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(page)
    return {
        "viewer.html": digest(html_path),
        "viewer.js": digest(js_path),
        "viewer-license.txt": digest(license_path),
    }
