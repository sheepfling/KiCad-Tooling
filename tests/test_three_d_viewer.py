"""The offline 3D viewer is bound to a retained, structurally valid GLB."""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.three_d_gallery import finalize_gallery, valid_artifact, write_gallery
from kicad_tooling.hwrepo.three_d_glb import inspect_glb

BOARD = (Path(__file__).parent / "fixtures" / "three_d_board.glb").read_bytes()


def _glb(document: dict[str, object]) -> bytes:
    chunk = json.dumps(document).encode("utf-8")
    chunk += b" " * (-len(chunk) % 4)
    return (
        struct.pack("<4sII", b"glTF", 2, 20 + len(chunk))
        + struct.pack("<I4s", len(chunk), b"JSON")
        + chunk
    )


def test_representative_board_has_local_viewer_and_source_identity(tmp_path: Path) -> None:
    (tmp_path / "board.glb").write_bytes(BOARD)
    (tmp_path / "board.step").write_bytes(b"ISO-10303-21;\nHEADER;\nENDSEC;\n")
    artifacts = {name: digest(tmp_path / name) for name in ("board.glb", "board.step")}
    source = {"board<review>.kicad_pcb": "a" * 64}
    status, actions = finalize_gallery(
        tmp_path,
        "board<script>",
        "PASS",
        "REVIEW",
        artifacts,
        ("Review missing <model> assignments.",),
        "pilot",
        source,
    )
    assert status == "PASS" and actions
    assert set(artifacts) == {
        "board.glb",
        "board.step",
        "viewer.html",
        "viewer.js",
        "viewer-license.txt",
        "index.html",
    }
    assert all(digest(tmp_path / name) == sha for name, sha in artifacts.items())
    html = (tmp_path / "viewer.html").read_text(encoding="utf-8")
    gallery = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'href="viewer.html"' in gallery
    assert 'src="viewer.js"' in html
    embedded = html.split('<script id="glb-data" type="application/octet-stream">', 1)[1].split(
        "</script>", 1
    )[0]
    assert base64.b64decode(embedded) == BOARD
    assert "board&lt;review&gt;.kicad_pcb" in html
    assert "board&lt;script&gt;" in html
    assert "Review missing &lt;model&gt; assignments." in html
    assert html.count('data-view="') == 7
    assert html.count('data-action="') == 6
    assert "https://" not in html and "http://" not in html
    assert 'role="status"' in html
    assert inspect_glb(tmp_path / "board.glb") is not None


def test_missing_and_corrupt_glb_never_offer_a_viewer(tmp_path: Path) -> None:
    assert write_gallery(tmp_path, "board", "FAIL", "REVIEW", {}, ()) is None
    path = tmp_path / "board.glb"
    path.write_bytes(BOARD[:-4])
    assert not valid_artifact(path, "glb")
    artifacts = {"board.glb": digest(path)}
    status, actions = finalize_gallery(tmp_path, "board", "PASS", "REVIEW", artifacts, ())
    assert status == "FAIL"
    assert "board.glb" not in artifacts
    assert "board.glb" in actions[0]
    assert 'href="viewer.html"' not in (tmp_path / "index.html").read_text()
    assert not (tmp_path / "viewer.html").exists()


def test_external_resource_glb_retains_export_but_omits_offline_viewer(tmp_path: Path) -> None:
    path = tmp_path / "board.glb"
    path.write_bytes(_glb({"asset": {"version": "2.0"}, "images": [{"uri": "texture.png"}]}))
    assert valid_artifact(path, "glb")
    result = write_gallery(tmp_path, "board", "PASS", "PASS", {"board.glb": digest(path)}, ())
    assert result is not None
    assert not result.viewer_artifacts
    gallery = (tmp_path / "index.html").read_text()
    assert "external resources" in gallery
    assert 'href="board.glb"' in gallery
    assert 'href="viewer.html"' not in gallery
