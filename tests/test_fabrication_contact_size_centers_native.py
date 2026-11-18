"""Exact-version KiCad exports retain pad size-to-center associations."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import UnsupportedFabricationFormat, parse_ipc356
from kicad_tooling.hwrepo.fabrication_contact_geometry import (
    require_ipc356_source_pad_coordinates,
    require_ipc356_source_pad_dimensions,
)
from kicad_tooling.hwrepo.fabrication_contact_source import source_component_pads
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
        reason="native repeated-pad size checks run in the digest-pinned acceptance lane",
    ),
]

_FIXTURE = Path(__file__).parent / "fixtures/fabrication-connectivity/repeated-pad-number.kicad_pcb"


def _run_export(image: str, tmp_path: Path, board: Path, output: Path, *arguments: str) -> None:
    result = execute_kicad_cli(
        image,
        ("kicad-cli", *arguments, str(board)),
        tmp_path,
        home_directory="fabrication-repeat-pad-native",
        fixture_directory=board.parent,
        output_directory=output,
    )
    assert result.returncode == 0, result.stderr
    assert result.error is None


def _replace_size(line: str, diameter_token: str) -> str:
    match = re.search(r"(A\d\dX[ +-]?\d+Y[ +-]?\d+X)\d+Y\d+(R\d{3}S\d)", line[31:])
    assert match is not None
    start = 31 + match.start()
    end = 31 + match.end()
    replacement = match.group(1) + diameter_token + "Y0000" + match.group(2)
    return line[:start] + replacement + line[end:]


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_ipc_sizes_remain_bound_to_repeated_pad_centers(
    tmp_path: Path, version: str
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    board_dir = tmp_path / "fixtures"
    board_dir.mkdir()
    board = board_dir / _FIXTURE.name
    shutil.copyfile(_FIXTURE, board)
    output = tmp_path / "fabrication"
    output.mkdir()

    version_result = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        tmp_path,
        home_directory="fabrication-repeat-pad-native-version",
        fixture_directory=board_dir,
        output_directory=output,
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == version
    _run_export(
        image,
        tmp_path,
        board,
        output,
        "pcb",
        "export",
        "ipcd356",
        "--output",
        str(output / "board.d356"),
    )

    ipc = output / "board.d356"
    original_lines = ipc.read_text(encoding="utf-8").splitlines()
    source_pads = source_component_pads(board.read_text(encoding="utf-8"))
    original_contacts = parse_ipc356("\n".join(original_lines) + "\n")
    repeated = tuple(
        contact for contact in original_contacts if contact.reference == "J1" and contact.pin == "1"
    )
    assert len(repeated) == 2
    require_ipc356_source_pad_coordinates(source_pads, original_contacts)
    require_ipc356_source_pad_dimensions(source_pads, original_contacts)

    swapped_lines: list[str] = []
    for line in original_lines:
        if (
            line.startswith(("317", "327"))
            and line[20:26].strip() == "J1"
            and line[27:31].strip() == "1"
        ):
            contact = parse_ipc356(line + "\n999\n")[0]
            swapped_lines.append(_replace_size(line, "0787" if contact.x_mm < 6.0 else "0394"))
        else:
            swapped_lines.append(line)
    mutated = parse_ipc356("\n".join(swapped_lines) + "\n")
    require_ipc356_source_pad_coordinates(source_pads, mutated)
    with pytest.raises(UnsupportedFabricationFormat, match="pad dimensions differ"):
        require_ipc356_source_pad_dimensions(source_pads, mutated)
