"""Native KiCad clamps oversized copper-to-edge clearance rules."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

FIXTURES = Path(__file__).parent / "fixtures/design_lint/drc-clearance-clamp"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


def _edge_descriptions(
    image: str, version: str, case: str, repeat: str, root: Path
) -> tuple[str, ...]:
    work = root / f"{case}-{repeat}"
    work.mkdir()
    shutil.copyfile(FIXTURES / f"{case}.kicad_pcb", work / "board.kicad_pcb")
    shutil.copyfile(FIXTURES / "board.kicad_pro", work / "board.kicad_pro")
    shutil.copyfile(FIXTURES / "board.kicad_dru", work / "board.kicad_dru")
    report = work / "report.json"
    command = execute_kicad_cli(
        image,
        (
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--exit-code-violations",
            "--output",
            str(report),
            str(work / "board.kicad_pcb"),
        ),
        root,
        home_directory="kicad-drc-clearance-clamp",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode in {0, 5}, command.model_dump_json(indent=2)
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["kicad_version"] == version
    return tuple(
        violation["description"]
        for violation in payload["violations"]
        if violation["type"] == "copper_edge_clearance"
    )


@pytest.mark.parametrize(("version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_native_drc_clamps_600mm_edge_requirement_to_500mm(
    tmp_path: Path, version: str, image: str
) -> None:
    inside = tuple(
        _edge_descriptions(image, version, "inside", repeat, tmp_path) for repeat in ("a", "b")
    )
    outside = tuple(
        _edge_descriptions(image, version, "outside", repeat, tmp_path) for repeat in ("a", "b")
    )
    assert inside[0] == inside[1]
    assert len(inside[0]) == 1
    assert "clearance 500.0000 mm" in inside[0][0]
    assert "actual 449.8500 mm" in inside[0][0]
    assert outside == ((), ())
