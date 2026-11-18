"""Exact-version native artifact regressions for fabrication connectivity."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import (
    UnsupportedFabricationFormat,
    parse_ipc356,
)
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import (
    FabricationConnectivityIgnore,
    FabricationConnectivitySettings,
)
from kicad_tooling.hwrepo.fabrication_contact_geometry import (
    require_ipc356_source_pad_coordinates,
)
from kicad_tooling.hwrepo.fabrication_contact_inventory import (
    require_ipc356_source_pad_inventory,
)
from kicad_tooling.hwrepo.fabrication_contact_layers import require_ipc356_source_pad_layers
from kicad_tooling.hwrepo.fabrication_contact_source import source_component_pads
from tests.fabrication_connectivity_native_support import (
    export_fabrication_outputs,
    run_kicad_cli,
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
        reason="native fabrication artifact checks run in the digest-pinned acceptance lane",
    ),
]

_FIXTURES = Path(__file__).parent / "fixtures/fabrication-connectivity"
_EXPECTED = {
    "clean": ("PASS", set()),
    "isolated": ("PASS", set()),
    "open": ("REVIEW", {"OPEN"}),
    "short": ("REVIEW", {"SHORT"}),
    "via": ("PASS", set()),
}
_MULTILAYER_EXPECTED = {
    "four-layer-clean": ("PASS", set()),
    "four-layer-open": ("REVIEW", {"OPEN"}),
    "four-layer-short": ("REVIEW", {"SHORT"}),
    "four-layer-blind-via": ("UNSUPPORTED", set()),
}


def _copy_contact_position(line: str, source_line: str) -> str:
    def fields(value: str) -> tuple[int, int, int, int, str, str]:
        access_start = value.find("A", 31)
        x_start = value.find("X", access_start)
        y_start = value.find("Y", x_start)
        size_start = value.find("X", y_start)
        if min(access_start, x_start, y_start, size_start) < 0:
            raise AssertionError(f"native IPC-D-356 contact has no coordinate fields: {value}")
        return (
            access_start,
            x_start,
            y_start,
            size_start,
            value[access_start : x_start + 1],
            value[x_start + 1 : y_start] + "Y" + value[y_start + 1 : size_start],
        )

    target_fields = fields(line)
    source_fields = fields(source_line)
    start, _, _, end, _, _ = target_fields
    replacement = source_fields[4] + source_fields[5]
    return line[:start] + replacement + line[end:]


def _remove_native_gerber_contact_flash(text: str, x_mm: int, y_mm: int) -> str:
    command = f"X{x_mm * 1_000_000}Y{-y_mm * 1_000_000}D03*"
    if text.count(command) != 1:
        raise AssertionError(f"expected one native Gerber contact flash {command!r}")
    return text.replace(command, "", 1)


def _native_rotated_contact_controls(
    image: str, tmp_path: Path, fixture_directory: Path, outputs: Path
) -> None:
    original = (_FIXTURES / "clean.kicad_pcb").read_text(encoding="utf-8")
    marker = '(footprint "Synthetic:TwoPadConnector" (layer "F.Cu") (at 5 5)'
    for side in ("top", "bottom"):
        layer = "F.Cu" if side == "top" else "B.Cu"
        board_text = original.replace(
            marker, f'(footprint "Synthetic:TwoPadConnector" (layer "{layer}") (at 10 10 90)', 1
        )
        if side == "bottom":
            board_text = board_text.replace('"F.Cu" "F.Mask"', '"B.Cu" "B.Mask"')
        board = fixture_directory / f"rotated-{side}.kicad_pcb"
        board.write_text(board_text, encoding="utf-8")
        fabrication = outputs / f"rotated-{side}" / "fabrication"
        fabrication.mkdir(parents=True)
        run_kicad_cli(
            image,
            tmp_path,
            fixture_directory,
            fabrication,
            board,
            ("pcb", "export", "ipcd356", "--output", str(fabrication / "board.d356")),
        )
        contacts = parse_ipc356((fabrication / "board.d356").read_text(encoding="utf-8"))
        source_pads = source_component_pads(board_text)
        require_ipc356_source_pad_inventory(source_pads, contacts)
        require_ipc356_source_pad_coordinates(source_pads, contacts)
        require_ipc356_source_pad_layers(source_pads, contacts)
        if side == "top":
            ipc_lines = (fabrication / "board.d356").read_text(encoding="utf-8").splitlines()
            wrong_layer = "\n".join(
                "317" + line[3:] if line.startswith("327") and line[27:31].strip() == "1" else line
                for line in ipc_lines
            )
            with pytest.raises(UnsupportedFabricationFormat, match="layer classification differs"):
                require_ipc356_source_pad_layers(source_pads, parse_ipc356(wrong_layer))
        coordinates = {contact.pin: (contact.x_mm, contact.y_mm) for contact in contacts}
        assert set(coordinates) == {"1", "2"}
        assert coordinates["1"] == pytest.approx((10.0, -10.0), abs=0.00003)
        assert coordinates["2"] == pytest.approx((10.0, -8.0), abs=0.001271)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_gerber_ipc356_connectivity_fault_controls_repeat(
    tmp_path: Path, version: str
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    version_result = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        tmp_path,
        home_directory="fabrication-connectivity-native-version",
        fixture_directory=fixture_directory,
        output_directory=outputs,
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == version

    for name, (expected_status, expected_codes) in _EXPECTED.items():
        board = fixture_directory / f"{name}.kicad_pcb"
        shutil.copyfile(_FIXTURES / board.name, board)
        fabrication = outputs / name / "fabrication"
        fabrication.mkdir(parents=True)
        export_fabrication_outputs(
            image, tmp_path, fixture_directory, fabrication, board, ("F.Cu", "B.Cu")
        )
        for gerber in fabrication.glob("*.gbr"):
            assert gerber.read_text(encoding="utf-8").rstrip().endswith("M02*")

        first = analyze_fabrication_connectivity(
            board, fabrication, FabricationConnectivitySettings()
        )
        repeated = analyze_fabrication_connectivity(
            board, fabrication, FabricationConnectivitySettings()
        )
        assert first == repeated
        assert not first.unsupported_reasons, first.unsupported_reasons
        assert (first.status, {item.code for item in first.findings}) == (
            expected_status,
            expected_codes,
        )

        if name == "four-layer-clean":
            in2_gerber = next(fabrication.glob("*In2_Cu.gbr"))
            original_in2 = in2_gerber.read_text(encoding="utf-8")
            in2_gerber.write_text(
                _remove_native_gerber_contact_flash(original_in2, 5, 5),
                encoding="utf-8",
            )
            missing_layer = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            repeated_missing_layer = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            assert missing_layer == repeated_missing_layer
            assert missing_layer.status == "REVIEW"
            assert {item.code for item in missing_layer.findings} == {"LAYER_COPPER_MISSING"}
            finding = missing_layer.findings[0]
            assert finding.net == "SIGNAL"
            assert finding.contacts == ("J1-1",)
            assert finding.missing_layers == ("In2.Cu",)

            blocked_layer = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings(mode="block")
            )
            ignored_layer = analyze_fabrication_connectivity(
                board,
                fabrication,
                FabricationConnectivitySettings(
                    mode="block",
                    ignores=(
                        FabricationConnectivityIgnore(
                            fingerprint=finding.fingerprint,
                            reason="synthetic exact-fingerprint anti-control",
                        ),
                    ),
                ),
            )
            assert blocked_layer.status == "FAIL"
            assert ignored_layer.status == "PASS"
            assert ignored_layer.ignored_findings == (finding,)

            in2_gerber.write_text(original_in2, encoding="utf-8")
            restored_layer = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            assert restored_layer.status == "PASS"
            assert restored_layer.findings == ()

        if name == "clean":
            _native_rotated_contact_controls(image, tmp_path, fixture_directory, outputs)
            ipc = fabrication / "board.d356"
            original_lines = ipc.read_text(encoding="utf-8").splitlines()
            omitted = [
                line
                for line in original_lines
                if line.startswith(("317", "327"))
                and line[20:26].strip() == "J1"
                and line[27:31].strip() == "2"
            ]
            assert len(omitted) == 1
            ipc.write_text(
                "\n".join(line for line in original_lines if line != omitted[0]) + "\n",
                encoding="utf-8",
            )
            incomplete = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            repeated_incomplete = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            assert incomplete == repeated_incomplete
            assert incomplete.status == "UNSUPPORTED"
            assert "missing j1.2=SIGNAL" in incomplete.unsupported_reasons[0]

            pad_one = next(
                line
                for line in original_lines
                if line.startswith(("317", "327"))
                and line[20:26].strip() == "J1"
                and line[27:31].strip() == "1"
            )
            pad_two = next(
                line
                for line in original_lines
                if line.startswith(("317", "327"))
                and line[20:26].strip() == "J1"
                and line[27:31].strip() == "2"
            )
            mislocated = [
                _copy_contact_position(line, pad_one) if line == pad_two else line
                for line in original_lines
            ]
            ipc.write_text("\n".join(mislocated) + "\n", encoding="utf-8")
            moved = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            repeated_moved = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            assert moved == repeated_moved
            assert moved.status == "UNSUPPORTED"
            assert "coordinates differ from source PCB pad centers" in moved.unsupported_reasons[0]

        if name == "via":
            drill = fabrication / "via-PTH.drl"
            original_drill = drill.read_text(encoding="utf-8")
            mutations = (
                (original_drill.replace("T1C0.300", "T1C0.400", 1), "drill diameter"),
                (
                    "\n".join(
                        line.replace("X6.0Y-5.0", "X6.1Y-5.0", 1) if line.startswith("X") else line
                        for line in original_drill.splitlines()
                    )
                    + "\n",
                    "no circular drill hit",
                ),
            )
            for mutated_drill, reason in mutations:
                assert mutated_drill != original_drill
                drill.write_text(mutated_drill, encoding="utf-8")
                mismatched = analyze_fabrication_connectivity(
                    board, fabrication, FabricationConnectivitySettings()
                )
                repeated_mismatch = analyze_fabrication_connectivity(
                    board, fabrication, FabricationConnectivitySettings()
                )
                assert mismatched == repeated_mismatch
                assert mismatched.status == "UNSUPPORTED"
                assert reason in mismatched.unsupported_reasons[0]
            drill.unlink()
            missing_drill = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            assert missing_drill.status == "UNSUPPORTED"
            assert "no circular drill hit" in missing_drill.unsupported_reasons[0]


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_multilayer_inner_copper_connectivity_and_via_boundary_repeat(
    tmp_path: Path, version: str
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    version_result = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        tmp_path,
        home_directory="fabrication-connectivity-multilayer-version",
        fixture_directory=fixture_directory,
        output_directory=outputs,
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == version

    source_dir = _FIXTURES / "multilayer"
    for name, (expected_status, expected_codes) in _MULTILAYER_EXPECTED.items():
        board = fixture_directory / f"{name}.kicad_pcb"
        shutil.copyfile(source_dir / board.name, board)
        fabrication = outputs / name / "fabrication"
        fabrication.mkdir(parents=True)
        export_fabrication_outputs(
            image,
            tmp_path,
            fixture_directory,
            fabrication,
            board,
            ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"),
        )

        first = analyze_fabrication_connectivity(
            board, fabrication, FabricationConnectivitySettings()
        )
        repeated = analyze_fabrication_connectivity(
            board, fabrication, FabricationConnectivitySettings()
        )
        assert first == repeated
        assert (first.status, {item.code for item in first.findings}) == (
            expected_status,
            expected_codes,
        )
        if name == "four-layer-clean":
            drill_path = next(fabrication.glob("*-PTH.drl"))
            drill_source = drill_path.read_text(encoding="utf-8")
            assert "TF.FileFunction,Plated,1,4,PTH" in drill_source
            drill_path.write_text(
                drill_source.replace(
                    "TF.FileFunction,Plated,1,4,PTH",
                    "TF.FileFunction,Plated,1,2,PTH,Blind",
                ),
                encoding="utf-8",
            )
            mismatched = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            mismatched_repeat = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            assert mismatched == mismatched_repeat
            assert mismatched.status == "UNSUPPORTED"
            assert "full source copper stack" in mismatched.unsupported_reasons[0]
            drill_path.write_text(drill_source, encoding="utf-8")
        if name == "four-layer-blind-via":
            assert "full-stack" in " ".join(first.unsupported_reasons)
        else:
            assert not first.unsupported_reasons, first.unsupported_reasons
