"""Opt-in real-browser exercise of the retained offline 3D viewer."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from kicad_tooling.hwrepo.assembly_review_html import render_assembly_review
from kicad_tooling.hwrepo.assembly_review_models import AssemblyPlacement, AssemblyReviewReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.three_d_viewer import write_viewer

pytestmark = pytest.mark.slow

_FIXTURES = Path(__file__).parent / "fixtures"


def _browser_observation(tmp_path: Path, page: Path) -> dict[str, Any]:
    browser_path = os.environ.get("KICAD_VIEWER_BROWSER")
    if not browser_path:
        pytest.skip("Set KICAD_VIEWER_BROWSER to an installed Chrome-family browser executable")
    browser = Path(browser_path)
    assert browser.is_file(), f"Browser does not exist: {browser}"
    probe = (_FIXTURES / "three_d_browser_probe.js").read_text(encoding="utf-8")
    probe_page = tmp_path / "browser-probe.html"
    probe_page.write_text(
        page.read_text(encoding="utf-8").replace("</body>", f"<script>{probe}</script></body>")
    )
    completed = subprocess.run(
        [
            str(browser),
            "--headless=new",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-extensions",
            "--enable-webgl",
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--virtual-time-budget=8000",
            f"--user-data-dir={tmp_path / 'browser-profile'}",
            "--dump-dom",
            probe_page.as_uri(),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    match = re.search(r'<pre id="viewer-probe-result">(.*?)</pre>', completed.stdout, re.DOTALL)
    assert match is not None, completed.stdout[-2000:]
    observation: dict[str, Any] = json.loads(html.unescape(match.group(1)))
    assert observation["canvas"] and observation["focusable"]
    assert observation["initial"].startswith("Fitted;")
    assert observation["top"].startswith("top view;")
    assert observation["zoom"].startswith("zoom in;")
    assert observation["keyboard"].startswith("Fitted;")
    assert all(resource.startswith("file://") for resource in observation["resources"])
    return observation


def test_offline_board_opens_and_controls_respond_in_browser(tmp_path: Path) -> None:
    board = (_FIXTURES / "three_d_board.glb").read_bytes()
    (tmp_path / "board.glb").write_bytes(board)
    result = write_viewer(
        tmp_path,
        "browser-check",
        "PASS",
        hashlib.sha256(board).hexdigest(),
        (),
        None,
        {"sample.kicad_pcb": "a" * 64},
        has_step=False,
    )
    assert result is not None
    observation = _browser_observation(tmp_path, tmp_path / "viewer.html")
    assert digest(tmp_path / "viewer.html") == result["viewer.html"]
    assert observation["enclosure"] is None


def test_offline_assembly_loads_both_models_and_toggles_enclosure(tmp_path: Path) -> None:
    board = (_FIXTURES / "three_d_board.glb").read_bytes()
    enclosure = (_FIXTURES / "three_d_enclosure.glb").read_bytes()
    placement = AssemblyPlacement(
        source_frame="enclosure-local",
        target_frame="board-export",
        translation_mm=(0.0, -0.2, 0.0),
        rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    )
    report = AssemblyReviewReport(
        project_id="browser-check",
        status="READY",
        board_receipt="build/3d/visualization.json",
        board_receipt_sha256="a" * 64,
        placement_contract="docs/assembly-placement.json",
        placement_contract_sha256="b" * 64,
        board_glb_sha256=hashlib.sha256(board).hexdigest(),
        enclosure_model="cad/enclosure.glb",
        enclosure_expected_sha256=hashlib.sha256(enclosure).hexdigest(),
        enclosure_sha256=hashlib.sha256(enclosure).hexdigest(),
        board_frame="board-export",
        board_unit="mm",
        enclosure_frame="enclosure-local",
        enclosure_unit="m",
        placement=placement,
        source_hashes={"sample.kicad_pcb": "c" * 64},
        model_status="READY",
        output_directory=str(tmp_path),
    )
    page = tmp_path / "index.html"
    page.write_text(render_assembly_review(report, board, enclosure), encoding="utf-8")
    asset = Path(__file__).parent.parent / "kicad_tooling/hwrepo/assets/three_d_viewer.js"
    (tmp_path / "viewer.js").write_bytes(asset.read_bytes())
    observation = _browser_observation(tmp_path, page)
    assert observation["enclosure"] == {
        "initialVisible": "true",
        "hidden": "false",
        "restored": "true",
    }
