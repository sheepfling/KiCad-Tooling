"""Exact-version IPC-D-356 access layers remain bound to source pad centers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import (
    UnsupportedFabricationFormat,
    parse_ipc356,
)
from kicad_tooling.hwrepo.fabrication_contact_geometry import (
    require_ipc356_source_pad_coordinates,
    require_ipc356_source_pad_dimensions,
)
from kicad_tooling.hwrepo.fabrication_contact_inventory import (
    require_ipc356_source_pad_inventory,
)
from kicad_tooling.hwrepo.fabrication_contact_layers import (
    require_ipc356_source_pad_access_codes,
    require_ipc356_source_pad_layers,
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
        reason="native contact-layer checks run in the digest-pinned acceptance lane",
    ),
]

_FIXTURE = (
    Path(__file__).parent / "fixtures/fabrication-connectivity/repeated-pad-layer-classes.kicad_pcb"
)
_BOTTOM_ACCESS_CODE_FIXTURE = (
    Path(__file__).parent / "fixtures/fabrication-connectivity/bottom-pad-access-code.kicad_pcb"
)
_FOUR_LAYER_BOTTOM_ACCESS_CODE_FIXTURE = (
    Path(__file__).parent
    / "fixtures/fabrication-connectivity/multilayer/four-layer-bottom-pad-access-code.kicad_pcb"
)


def _run_export(image: str, work: Path, board: Path, output: Path) -> None:
    result = execute_kicad_cli(
        image,
        ("kicad-cli", "pcb", "export", "ipcd356", "--output", str(output), str(board)),
        work,
        home_directory="fabrication-contact-layer-centers",
        fixture_directory=board.parent,
        output_directory=output.parent,
    )
    assert result.returncode == 0, result.stderr
    assert result.error is None


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_layer_classes_remain_bound_to_repeated_pad_centers(
    tmp_path: Path, version: str
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    board = fixtures / _FIXTURE.name
    shutil.copyfile(_FIXTURE, board)
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    export = outputs / "board.d356"

    version_result = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        tmp_path,
        home_directory="fabrication-contact-layer-version",
        fixture_directory=fixtures,
        output_directory=outputs,
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == version
    _run_export(image, tmp_path, board, export)

    source = source_component_pads(board.read_text(encoding="utf-8"))
    original_lines = export.read_text(encoding="utf-8").splitlines()
    contacts = parse_ipc356("\n".join(original_lines))
    assert tuple(pad.contact_layer for pad in source) == ("top", "through")
    assert {contact.layer for contact in contacts} == {"top", "through"}
    require_ipc356_source_pad_inventory(source, contacts)
    require_ipc356_source_pad_coordinates(source, contacts)
    require_ipc356_source_pad_dimensions(source, contacts)
    require_ipc356_source_pad_access_codes(source, contacts, 2)
    require_ipc356_source_pad_layers(source, contacts)

    swapped_lines = [
        "317" + line[3:]
        if line.startswith("327")
        else "327" + line[3:]
        if line.startswith("317")
        else line
        for line in original_lines
    ]
    swapped = parse_ipc356("\n".join(swapped_lines))
    require_ipc356_source_pad_inventory(source, swapped)
    require_ipc356_source_pad_coordinates(source, swapped)
    require_ipc356_source_pad_dimensions(source, swapped)
    with pytest.raises(UnsupportedFabricationFormat, match="layer classification differs"):
        require_ipc356_source_pad_layers(source, swapped)


@pytest.mark.parametrize(
    ("fixture", "copper_layer_count", "access_code"),
    ((_BOTTOM_ACCESS_CODE_FIXTURE, 2, 2), (_FOUR_LAYER_BOTTOM_ACCESS_CODE_FIXTURE, 4, 4)),
    ids=("two-layer", "four-layer"),
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_bottom_access_code_is_bound_to_source_copper_stack(
    tmp_path: Path, version: str, fixture: Path, copper_layer_count: int, access_code: int
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    board = fixtures / fixture.name
    shutil.copyfile(fixture, board)
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    export = outputs / "board.d356"

    version_result = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        tmp_path,
        home_directory="fabrication-contact-access-version",
        fixture_directory=fixtures,
        output_directory=outputs,
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == version
    _run_export(image, tmp_path, board, export)

    source = source_component_pads(board.read_text(encoding="utf-8"))
    original_lines = export.read_text(encoding="utf-8").splitlines()
    contacts = parse_ipc356("\n".join(original_lines))
    assert tuple(pad.contact_layer for pad in source) == ("bottom",)
    assert tuple(contact.access_code for contact in contacts) == (access_code,)
    require_ipc356_source_pad_inventory(source, contacts)
    require_ipc356_source_pad_coordinates(source, contacts)
    require_ipc356_source_pad_dimensions(source, contacts)
    require_ipc356_source_pad_access_codes(source, contacts, copper_layer_count)
    require_ipc356_source_pad_layers(source, contacts)

    mutated_lines: list[str] = []
    for line in original_lines:
        if line.startswith("327") and line[20:26].strip() == "J1":
            original = f"A{access_code:02d}X"
            mutated = f"A{access_code + 1:02d}X"
            assert original in line
            line = line.replace(original, mutated, 1)
        mutated_lines.append(line)
    mutated = parse_ipc356("\n".join(mutated_lines))
    assert mutated[0].layer == "bottom"
    require_ipc356_source_pad_inventory(source, mutated)
    require_ipc356_source_pad_coordinates(source, mutated)
    require_ipc356_source_pad_dimensions(source, mutated)
    require_ipc356_source_pad_layers(source, mutated)
    with pytest.raises(UnsupportedFabricationFormat, match="access code differs"):
        require_ipc356_source_pad_access_codes(source, mutated, copper_layer_count)
