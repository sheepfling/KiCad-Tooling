"""Offline review gallery for verified outputs from a 3D export receipt."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Literal

from .evidence import digest
from .models import THREE_D_VIEWS
from .three_d_glb import inspect_glb
from .three_d_viewer import write_viewer


@dataclass(frozen=True, slots=True)
class GalleryResult:
    sha256: str
    changed: tuple[str, ...]
    viewer_artifacts: Mapping[str, str]


def valid_artifact(path: Path, kind: str) -> bool:
    """Check the expected native artifact signature before recording it."""
    if not path.is_file() or path.stat().st_size < 16:
        return False
    with path.open("rb") as stream:
        header = stream.read(32)
    if kind == "png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if kind == "glb":
        return inspect_glb(path) is not None
    return header.startswith(b"ISO-10303-21") if kind == "step" else False


def write_gallery(
    directory: Path,
    project_id: str,
    status: str,
    model_status: str,
    artifacts: Mapping[str, str],
    actions: Sequence[str],
    assembly_variant: str | None = None,
    source_sha256: Mapping[str, str] | None = None,
) -> GalleryResult | None:
    """Write a gallery only when native outputs exist and report changed files.

    The explicit output names prevent links to arbitrary paths. Check each hash
    again before linking so an absent or changed file is not presented as valid.
    """
    if not artifacts:
        return None
    expected = tuple(f"{name}.png" for name in THREE_D_VIEWS) + ("board.step", "board.glb")
    available: list[str] = []
    missing: list[str] = []
    for name in expected:
        if name not in artifacts:
            continue
        path = directory / name
        try:
            valid = path.is_file() and not path.is_symlink() and digest(path) == artifacts[name]
            if valid and name == "board.glb":
                valid = valid_artifact(path, "glb")
        except OSError:
            valid = False
        if valid:
            available.append(name)
        else:
            missing.append(name)
    viewer_artifacts: Mapping[str, str] = {}
    viewer_note = ""
    if "board.glb" in available:
        try:
            viewer = write_viewer(
                directory,
                project_id,
                model_status,
                artifacts["board.glb"],
                actions,
                assembly_variant,
                source_sha256 or {},
                has_step="board.step" in available,
            )
        except ValueError:
            available.remove("board.glb")
            missing.append("board.glb")
        else:
            if viewer is None:
                viewer_note = (
                    "<p>The GLB uses external resources and cannot open in this offline viewer.</p>"
                )
            else:
                viewer_artifacts = viewer
                viewer_note = '<p><a href="viewer.html">Open interactive 3D model</a></p>'
    pictures = "".join(
        f'<figure><a href="{escape(name, quote=True)}"><img src="{escape(name, quote=True)}" '
        f'alt="{escape(name.removesuffix(".png"), quote=True)} board view"></a>'
        f"<figcaption>{escape(name.removesuffix('.png'))}</figcaption></figure>"
        for name in available
        if name.endswith(".png")
    )
    if not pictures:
        pictures = "<p>No verified board images are available in this receipt.</p>"
    links = " ".join(
        f'<a href="{escape(name, quote=True)}">{escape(name)}</a>'
        for name in available
        if name in {"board.step", "board.glb"}
    )
    if not links:
        links = "No verified exchange files are available."
    warnings = "".join(f"<li>{escape(action)}</li>" for action in actions)
    missing_text = (
        "<p>Recorded files missing or changed: " + escape(", ".join(missing)) + ".</p>"
        if missing
        else ""
    )
    title = escape(project_id)
    variant = escape(assembly_variant) if assembly_variant else "default"
    gallery_status = "FAIL" if missing else status
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>3D review: {title}</title><style>
body{{font-family:system-ui,sans-serif;line-height:1.5;max-width:1200px;margin:auto;padding:2rem;color:#1c2932}}
.views{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:1rem}}
figure{{margin:0;border:1px solid #bfcbd0;border-radius:.5rem;padding:.5rem}}img{{width:100%;height:auto}}
figcaption{{font-weight:600}}.notice{{padding:1rem;background:#fff4d6}}a{{color:#155d70}}
</style></head><body><h1>3D review: {title}</h1>
<p>Export status: <strong>{escape(gallery_status)}</strong>; model coverage: <strong>{escape(model_status)}</strong>.</p>
<p>Assembly variant: {variant}.</p>
<p class="notice">A failed export may contain only a partial set of views. Inspect images and geometry before mechanical decisions.</p>
{missing_text}<ul>{warnings}</ul><h2>Board views</h2><div class="views">{pictures}</div>
<h2>Exchange files</h2><p>{links}</p>{viewer_note}<p><a href="visualization.json">Visualization receipt</a></p>
</body></html>
"""
    path = directory / "index.html"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(document)
    return GalleryResult(
        sha256=digest(path), changed=tuple(missing), viewer_artifacts=viewer_artifacts
    )


def finalize_gallery(
    directory: Path,
    project_id: str,
    status: Literal["PASS", "FAIL", "ERROR"],
    model_status: str,
    artifacts: dict[str, str],
    actions: tuple[str, ...],
    assembly_variant: str | None = None,
    source_sha256: Mapping[str, str] | None = None,
) -> tuple[Literal["PASS", "FAIL", "ERROR"], tuple[str, ...]]:
    """Bind gallery and report status to the same verified output inventory."""
    gallery = write_gallery(
        directory,
        project_id,
        status,
        model_status,
        artifacts,
        actions,
        assembly_variant,
        source_sha256,
    )
    if gallery is None:
        return status, actions
    if gallery.changed:
        for name in gallery.changed:
            artifacts.pop(name, None)
        status = "FAIL"
        actions = (
            "Retained 3D output missing or changed during export: "
            + ", ".join(gallery.changed)
            + ". Rerun from a stable source into a fresh receipt.",
            *actions,
        )
    artifacts["index.html"] = gallery.sha256
    artifacts.update(gallery.viewer_artifacts)
    return status, actions
