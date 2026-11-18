"""Exact-version KiCad exports for source-bound IPC-D-356 VIA contacts."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import (
    UnsupportedFabricationFormat,
    parse_ipc356,
)
from kicad_tooling.hwrepo.fabrication_via_binding import (
    require_ipc356_source_via_access_codes,
    require_ipc356_source_via_geometry,
    source_board_vias,
)
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_ARTIFACT_CONNECTIVITY") != "1",
        reason="native VIA binding checks run in the digest-pinned acceptance lane",
    ),
]

_FIXTURE = Path(__file__).parent / "fixtures/fabrication-connectivity/via.kicad_pcb"


def _run(image: str, tmp_path: Path, board: Path, fabrication: Path, *arguments: str) -> None:
    command = execute_kicad_cli(
        image,
        ("kicad-cli", *arguments, str(board)),
        tmp_path,
        home_directory="fabrication-via-native",
        fixture_directory=board.parent,
        output_directory=fabrication,
    )
    assert command.returncode == 0, command.stderr
    assert command.error is None


def _replace_via_coordinates(line: str) -> str:
    match = re.search(r"(A\d\dX)([ +-]?\d+)(Y)([ +-]?\d+)", line[31:])
    assert match is not None
    start = 31 + match.start()
    end = 31 + match.end()
    replacement = match.group(1) + "+999999Y-999999"
    return line[:start] + replacement + line[end:]


def _replace_via_size(line: str) -> str:
    match = re.search(r"(A\d\dX[ +-]?\d+Y[ +-]?\d+X)\d+Y\d+(R\d{3}S\d)", line[31:])
    assert match is not None
    start = 31 + match.start()
    end = 31 + match.end()
    replacement = match.group(1) + "0394Y0000" + match.group(2)
    return line[:start] + replacement + line[end:]


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_ipc356_via_records_match_source_inventory_and_reject_mutations(
    tmp_path: Path, version: str
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    board_dir = tmp_path / "fixtures"
    board_dir.mkdir()
    board = board_dir / _FIXTURE.name
    shutil.copyfile(_FIXTURE, board)
    fabrication = tmp_path / "fabrication"
    fabrication.mkdir()

    version_result = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        tmp_path,
        home_directory="fabrication-via-native-version",
        fixture_directory=board_dir,
        output_directory=fabrication,
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == version
    _run(
        image,
        tmp_path,
        board,
        fabrication,
        "pcb",
        "export",
        "ipcd356",
        "--output",
        str(fabrication / "board.d356"),
    )

    ipc_path = fabrication / "board.d356"
    ipc_text = ipc_path.read_text(encoding="utf-8")
    lines = ipc_text.splitlines()
    via_lines = [
        line for line in lines if line.startswith(("317", "327")) and line[20:26].strip() == "VIA"
    ]
    assert len(via_lines) == 1
    source_vias = source_board_vias(board.read_text(encoding="utf-8"))
    contacts = parse_ipc356(ipc_text)
    require_ipc356_source_via_geometry(source_vias, contacts)
    require_ipc356_source_via_access_codes(source_vias, contacts)

    wrong_access_lines = [
        line.replace("A00X", "A01X", 1)
        if line.startswith(("317", "327")) and line[20:26].strip() == "VIA"
        else line
        for line in lines
    ]
    wrong_access = parse_ipc356("\n".join(wrong_access_lines) + "\n")
    require_ipc356_source_via_geometry(source_vias, wrong_access)
    with pytest.raises(UnsupportedFabricationFormat, match="access code differs"):
        require_ipc356_source_via_access_codes(source_vias, wrong_access)

    without_via = parse_ipc356("\n".join(line for line in lines if line != via_lines[0]) + "\n")
    with pytest.raises(UnsupportedFabricationFormat, match="count differs"):
        require_ipc356_source_via_geometry(source_vias, without_via)

    moved_lines = [
        _replace_via_coordinates(line) if line == via_lines[0] else line for line in lines
    ]
    moved = parse_ipc356("\n".join(moved_lines) + "\n")
    with pytest.raises(UnsupportedFabricationFormat, match="no matching source via"):
        require_ipc356_source_via_geometry(source_vias, moved)

    duplicate_lines = [*lines[:-1], via_lines[0], lines[-1]]
    duplicate = parse_ipc356("\n".join(duplicate_lines) + "\n")
    with pytest.raises(UnsupportedFabricationFormat, match="count differs"):
        require_ipc356_source_via_geometry(source_vias, duplicate)

    wrong_size_lines = [_replace_via_size(line) if line == via_lines[0] else line for line in lines]
    wrong_size = parse_ipc356("\n".join(wrong_size_lines) + "\n")
    with pytest.raises(UnsupportedFabricationFormat, match="dimensions differ"):
        require_ipc356_source_via_geometry(source_vias, wrong_size)
