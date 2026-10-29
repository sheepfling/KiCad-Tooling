"""The 3D gallery links only to verified, named local artifacts."""

from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.three_d_gallery import finalize_gallery, write_gallery


def test_gallery_escapes_text_and_omits_changed_or_unexpected_files(tmp_path: Path) -> None:
    (tmp_path / "top.png").write_bytes(b"saved top")
    (tmp_path / "bottom.png").write_bytes(b"saved bottom")
    top_hash = digest(tmp_path / "top.png")
    bottom_hash = digest(tmp_path / "bottom.png")
    (tmp_path / "bottom.png").write_bytes(b"changed")
    gallery_hash = write_gallery(
        tmp_path,
        "project<script>",
        "PASS",
        "REVIEW",
        {"top.png": top_hash, "bottom.png": bottom_hash, "../outside.png": top_hash},
        ("Inspect <models> & files",),
        "<prototype>",
    )
    gallery = tmp_path / "index.html"
    text = gallery.read_text(encoding="utf-8")
    assert gallery_hash is not None
    assert gallery_hash.sha256 == digest(gallery)
    assert gallery_hash.changed == ("bottom.png",)
    assert "Export status: <strong>FAIL</strong>" in text
    assert "project&lt;script&gt;" in text
    assert "Inspect &lt;models&gt; &amp; files" in text
    assert "Assembly variant: &lt;prototype&gt;" in text
    assert 'src="top.png"' in text
    assert 'src="bottom.png"' not in text
    assert "Recorded files missing or changed: bottom.png" in text
    assert "outside.png" not in text
    assert "No verified exchange files are available" in text


def test_empty_inventory_does_not_create_a_gallery(tmp_path: Path) -> None:
    assert write_gallery(tmp_path, "board", "FAIL", "NOT_RUN", {}, ()) is None
    assert not (tmp_path / "index.html").exists()


def test_output_disappearing_during_digest_is_not_recorded_as_valid(tmp_path: Path) -> None:
    top = tmp_path / "top.png"
    top.write_bytes(b"saved top")
    artifacts = {"top.png": digest(top)}
    real_digest = digest

    def vanishing_digest(path: Path) -> str:
        if path == top:
            raise FileNotFoundError(path)
        return real_digest(path)

    with patch("kicad_tooling.hwrepo.three_d_gallery.digest", side_effect=vanishing_digest):
        status, actions = finalize_gallery(tmp_path, "board", "PASS", "PASS", artifacts, ())
    assert status == "FAIL"
    assert "top.png" not in artifacts
    assert "top.png" in actions[0]
    assert "index.html" in artifacts
