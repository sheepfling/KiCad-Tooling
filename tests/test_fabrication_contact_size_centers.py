"""IPC-D-356 pad sizes must stay paired with repeated pin-number centers."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from tests.fabrication_connectivity_support import (
    format_ipc_contact,
    write_synthetic_fabrication,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_FIXTURE = Path(__file__).parent / "fixtures/fabrication-connectivity/repeated-pad-number.kicad_pcb"


def _write_repeated_pin_ipc(fabrication: Path, *, swapped_sizes: bool) -> None:
    first_size, second_size = (2.0, 1.0) if swapped_sizes else (1.0, 2.0)
    contacts = (
        format_ipc_contact("327", "SIGNAL", "J1", "1", 1, 5.0, first_size),
        format_ipc_contact("327", "SIGNAL", "J1", "1", 1, 7.0, second_size),
    )
    (fabrication / "board.d356").write_text(
        "P  UNITS CUST 0\n" + "\n".join(contacts) + "\n999\n", encoding="utf-8"
    )


def _write_repeated_pin_land_flashes(fabrication: Path) -> None:
    gerber = fabrication / "board-F_Cu.gbr"
    source = gerber.read_text(encoding="utf-8")
    aperture = "%ADD15C,1.000000*%"
    flashes = "D15*X5000000Y-5000000D03*X7000000Y-5000000D03*"
    assert source.count(aperture) == 1
    assert source.count(flashes) == 1
    source = source.replace(aperture, f"{aperture}\n%ADD16C,2.000000*%", 1)
    source = source.replace(
        flashes,
        "D15*X5000000Y-5000000D03*D16*X7000000Y-5000000D03*",
        1,
    )
    gerber.write_text(source, encoding="utf-8")


@pytest.mark.parametrize("swapped_sizes", (False, True), ids=("matching", "swapped-by-center"))
def test_analyzer_requires_each_repeated_pin_size_at_its_source_center(
    tmp_path: Path, swapped_sizes: bool
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    board.write_bytes(_FIXTURE.read_bytes())
    _write_repeated_pin_land_flashes(fabrication)
    _write_repeated_pin_ipc(fabrication, swapped_sizes=swapped_sizes)

    report = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    if swapped_sizes:
        assert report.status == "UNSUPPORTED"
        assert not report.findings
        assert "pad dimensions differ" in report.unsupported_reasons[0]
    else:
        assert report.status == "PASS"
        assert report.unsupported_reasons == ()


def test_analyzer_rejects_repeated_pin_centers_below_ipc_resolution(
    tmp_path: Path,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    source = _FIXTURE.read_text(encoding="utf-8")
    source = source.replace("(at 2 0) (size 2 2)", "(at 0.001 0) (size 1 1)", 1)
    board.write_text(source, encoding="utf-8")
    _write_repeated_pin_ipc(fabrication, swapped_sizes=False)

    report = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert report.status == "UNSUPPORTED"
    assert not report.findings
    assert "ambiguous source center" in report.unsupported_reasons[0]
