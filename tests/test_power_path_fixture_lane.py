"""Synthetic orchestration regression for the mapped power-path fixture lane."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from kicad_tooling.ci_hosted import HostedLog, power_path_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence, ComponentContract, NetlistContract
from tests.design_lint_fixtures.power_input_paths import (
    series_diode_netlist,
    series_jumper_netlist,
    series_three_pin_jumper_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]


def observed_power_path(
    *,
    wrong_source: bool = False,
    isolated_return: bool = False,
    capacitor_symbol: str = "Device:C",
    external_source: bool = False,
    dnp_source: bool = False,
    alternate_source: bool = False,
    both_sources_dnp: bool = False,
) -> NetlistContract:
    nets = {
        "VIN": ("U1.1", "FB1.1"),
        "VLOAD": ("FB1.2", "C1.1"),
        "GND": ("C1.2",),
    }
    nets["VLOAD"] = (*nets["VLOAD"], "U2.1")
    if wrong_source:
        nets["VIN"] = ("U1.1",)
        nets["GND"] = ("C1.2", "FB1.1")
    if isolated_return:
        nets.pop("GND")
        nets["ISO_RETURN"] = ("C1.2",)
    components = {
        "U1": ComponentContract(value="Synthetic source", footprint="Synthetic:PowerSource"),
        "FB1": ComponentContract(value="Ferrite bead", footprint="Synthetic:0603"),
        "U2": ComponentContract(value="Synthetic load", footprint="Synthetic:PowerLoad"),
        "C1": ComponentContract(value="100nF", footprint="Synthetic:0603"),
    }
    symbols = {
        "U1": "Synthetic:PowerSource",
        "FB1": "Device:FerriteBead",
        "U2": "Synthetic:PowerLoad",
        "C1": capacitor_symbol,
    }
    pin_functions = {"U1.1": "VOUT", "U2.1": "VIN"}
    pin_electrical_types = {"U1.1": "power_out", "U2.1": "power_in"}
    pin_numbers = {
        "U1": ("1",),
        "FB1": ("1", "2"),
        "U2": ("1",),
        "C1": ("1", "2"),
    }
    dnp_components: tuple[str, ...] = ()
    if external_source:
        components.pop("U1")
        components["J1"] = ComponentContract(
            value="External supply connector", footprint="Synthetic:ExternalSupply"
        )
        symbols.pop("U1")
        symbols["J1"] = "Synthetic:ExternalSupply"
        pin_functions.pop("U1.1")
        pin_functions["J1.1"] = "VOUT"
        pin_electrical_types.pop("U1.1")
        pin_electrical_types["J1.1"] = "power_out"
        pin_numbers.pop("U1")
        pin_numbers["J1"] = ("1", "2")
        nets = {
            "AUX_INPUT": ("J1.1", "FB1.1"),
            "VLOAD": ("FB1.2", "C1.1", "U2.1"),
            "GND": ("C1.2", "J1.2"),
        }
        if alternate_source:
            components["FB2"] = ComponentContract(value="Ferrite bead", footprint="Synthetic:0603")
            components["J2"] = ComponentContract(
                value="External supply connector", footprint="Synthetic:ExternalSupply"
            )
            symbols["FB2"] = "Device:FerriteBead"
            symbols["J2"] = "Synthetic:ExternalSupply"
            pin_numbers["FB2"] = ("1", "2")
            pin_functions["J2.1"] = "VOUT"
            pin_electrical_types["J2.1"] = "power_out"
            pin_numbers["J2"] = ("1", "2")
            nets["AUX_INPUT"] = ("J1.1", "FB1.1")
            nets["ALT_INPUT"] = ("J2.1", "FB2.1")
            nets["VLOAD"] = ("FB1.2", "FB2.2", "C1.1", "U2.1")
            nets["GND"] = ("C1.2", "J1.2", "J2.2")
        if dnp_source:
            dnp_components = ("J1", "J2") if both_sources_dnp else ("J1",)
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=symbols,
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
        component_pin_numbers=pin_numbers,
        dnp_components=dnp_components,
    )


def test_synthetic_lane_checks_read_only_export_fault_control_and_repeatability() -> None:
    with tempfile.TemporaryDirectory(prefix="power-path-lane-test-") as temporary:
        root = Path(temporary)
        image = "fixture.invalid/kicad@sha256:" + "a" * 64
        config = SimpleNamespace(image=image, kicad_version="10.0.0")
        cases = (
            "control",
            "fault",
            "diode-control",
            "diode-reverse-fault",
            "schottky-diode-control",
            "bridged-jumper-control",
            "open-jumper-fault",
            "bridged-three-pin12-control",
            "bridged-three-pin123-control",
            "bridged-three-pin12-unbridged-terminal-fault",
            "isolated-control",
            "custom-capacitor-control",
            "custom-capacitor-fault",
            "opaque-capacitor-fault",
            "external-source-control",
            "dnp-external-source-fault",
            "alternate-source-control",
            "both-sources-dnp-fault",
        )

        def fake_run_command(
            command_root: Path, argv: tuple[str, ...], timeout: int
        ) -> CommandEvidence:
            assert command_root == root.resolve()
            assert timeout == 600
            assert argv[argv.index("--network") + 1] == "none"
            assert "--read-only" in argv
            assert argv[argv.index("--entrypoint") + 1] == "/bin/sh"
            assert argv[argv.index("--platform") + 1] == "linux/amd64"
            assert image in argv
            assert 'test "$actual" = "10.0.0"' in argv[-1]
            mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
            assert len(mounts) == 2
            source_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
            output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
            source_directory = Path(source_mount.removesuffix(":/fixtures:ro"))
            output_directory = Path(output_mount.removesuffix(":/output:rw"))
            assert {item.name for item in source_directory.iterdir()} == {
                "control.kicad_sch",
                "fault.kicad_sch",
                "diode-control.kicad_sch",
                "diode-reverse-fault.kicad_sch",
                "schottky-diode-control.kicad_sch",
                "bridged-jumper-control.kicad_sch",
                "open-jumper-fault.kicad_sch",
                "bridged-three-pin12-control.kicad_sch",
                "bridged-three-pin123-control.kicad_sch",
                "bridged-three-pin12-unbridged-terminal-fault.kicad_sch",
                "isolated-control.kicad_sch",
                "custom-capacitor-control.kicad_sch",
                "custom-capacitor-fault.kicad_sch",
                "opaque-capacitor-fault.kicad_sch",
                "external-source-control.kicad_sch",
                "dnp-external-source-fault.kicad_sch",
                "alternate-source-control.kicad_sch",
                "both-sources-dnp-fault.kicad_sch",
            }
            for case in cases:
                for run in ("first", "repeat"):
                    (output_directory / f"{case}.{run}.netlist.xml").write_text(
                        f"synthetic {case} native output {run}\n", encoding="utf-8"
                    )
                    (output_directory / f"{case}.{run}.erc.json").write_text(
                        '{"kicad_version":"10.0.0","sheets":[{"violations":[]}]}',
                        encoding="utf-8",
                    )
            assert "kicad-cli sch erc --format json --severity-all" in argv[-1]
            return CommandEvidence(
                argv=argv,
                started_utc="2026-09-30T00:00:00+00:00",
                returncode=0,
                stdout="kicad_version=10.0.0\n",
            )

        def fake_read_netlist(path: Path) -> NetlistContract:
            case = path.name.split(".", 1)[0]
            if case in {"diode-control", "diode-reverse-fault", "schottky-diode-control"}:
                return series_diode_netlist(
                    reverse=case == "diode-reverse-fault",
                    symbol=(
                        "Device:D_Schottky" if case == "schottky-diode-control" else "Device:D"
                    ),
                )
            if case in {"bridged-jumper-control", "open-jumper-fault"}:
                return series_jumper_netlist(
                    symbol=(
                        "Jumper:SolderJumper_2_Open"
                        if case == "open-jumper-fault"
                        else "Jumper:SolderJumper_2_Bridged"
                    )
                )
            if case in {
                "bridged-three-pin12-control",
                "bridged-three-pin123-control",
                "bridged-three-pin12-unbridged-terminal-fault",
            }:
                return series_three_pin_jumper_netlist(
                    symbol=(
                        "Jumper:SolderJumper_3_Bridged123"
                        if case == "bridged-three-pin123-control"
                        else "Jumper:SolderJumper_3_Bridged12"
                    ),
                    source_pin="1",
                    load_pin=("2" if case == "bridged-three-pin12-control" else "3"),
                )
            if case == "custom-capacitor-control" or case == "custom-capacitor-fault":
                capacitor_symbol = "Vendor:Power_Capacitor"
            elif case == "opaque-capacitor-fault":
                capacitor_symbol = "Vendor:CAP123"
            else:
                capacitor_symbol = "Device:C"
            return observed_power_path(
                wrong_source=case in {"fault", "custom-capacitor-fault", "opaque-capacitor-fault"},
                isolated_return=case == "isolated-control",
                capacitor_symbol=capacitor_symbol,
                external_source=case
                in {
                    "external-source-control",
                    "dnp-external-source-fault",
                    "alternate-source-control",
                    "both-sources-dnp-fault",
                },
                dnp_source=case
                in {
                    "dnp-external-source-fault",
                    "alternate-source-control",
                    "both-sources-dnp-fault",
                },
                alternate_source=case in {"alternate-source-control", "both-sources-dnp-fault"},
                both_sources_dnp=case == "both-sources-dnp-fault",
            )

        log = HostedLog(root, "power-path")
        with (
            patch("kicad_tooling.hwrepo.electrical.selected_config", return_value=config),
            patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_run_command),
            patch("kicad_tooling.validate.read_netlist", side_effect=fake_read_netlist),
        ):
            power_path_fixture_lane(root, project="synthetic-project", image=image, log=log)

        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("power-path-fixture/")
        }
        assert set(results) == {
            "power-path-fixture/native-export",
            "power-path-fixture/control",
            "power-path-fixture/fault",
            "power-path-fixture/diode-control",
            "power-path-fixture/diode-reverse-fault",
            "power-path-fixture/schottky-diode-control",
            "power-path-fixture/bridged-jumper-control",
            "power-path-fixture/open-jumper-fault",
            "power-path-fixture/bridged-three-pin12-control",
            "power-path-fixture/bridged-three-pin123-control",
            "power-path-fixture/bridged-three-pin12-unbridged-terminal-fault",
            "power-path-fixture/isolated-control",
            "power-path-fixture/custom-capacitor-control",
            "power-path-fixture/custom-capacitor-fault",
            "power-path-fixture/opaque-capacitor-fault",
            "power-path-fixture/external-source-control",
            "power-path-fixture/dnp-external-source-fault",
            "power-path-fixture/alternate-source-control",
            "power-path-fixture/both-sources-dnp-fault",
        }
        control = results["power-path-fixture/control"]
        assert control["lint_status"] == "PASS"
        fault = results["power-path-fixture/fault"]
        assert fault["lint_status"] == "REVIEW"
        assert "source-through-bead-to-load" in fault["power_path_findings"]
        assert "FB1.1 is assigned to GND; expected VIN" in fault["power_path_details"]
        assert fault["other_findings"] == "none"
        assert control["unmapped_power_input_findings"] == "none"
        assert (
            fault["unmapped_power_input_findings"]
            == "power.input_without_supported_source_path:VLOAD: power-input source-path review"
        )
        assert control["unmapped_lint_status"] == "PASS"
        bridged_jumper = results["power-path-fixture/bridged-jumper-control"]
        open_jumper = results["power-path-fixture/open-jumper-fault"]
        assert bridged_jumper["unmapped_lint_status"] == "PASS"
        assert bridged_jumper["unmapped_power_input_findings"] == "none"
        assert open_jumper["unmapped_lint_status"] == "REVIEW"
        assert (
            open_jumper["unmapped_power_input_findings"]
            == "power.input_without_supported_source_path:VLOAD: power-input source-path review"
        )
        isolated = results["power-path-fixture/isolated-control"]
        assert isolated["lint_status"] == "PASS"
        assert isolated["unmapped_lint_status"] == "PASS"
        assert isolated["unmapped_power_input_findings"] == "none"
        assert isolated["return_nets"] == "ISO_RETURN"
        assert isolated["erc_error_types"] == "none"
        custom_control = results["power-path-fixture/custom-capacitor-control"]
        custom_fault = results["power-path-fixture/custom-capacitor-fault"]
        opaque_fault = results["power-path-fixture/opaque-capacitor-fault"]
        assert custom_control["unmapped_lint_status"] == "PASS"
        assert custom_control["unmapped_power_input_findings"] == "none"
        assert custom_fault["unmapped_lint_status"] == "REVIEW"
        assert custom_fault["unmapped_other_findings"] == "none"
        assert (
            "power.input_without_supported_source_path:VLOAD"
            in custom_fault["unmapped_power_input_findings"]
        )
        assert opaque_fault["unmapped_lint_status"] == "REVIEW"
        assert opaque_fault["unmapped_power_input_findings"] == "none"
        assert (
            opaque_fault["unmapped_other_findings"]
            == "power.ic_rail_without_fitted_capacitor:VLOAD: IC supply decoupling review"
        )
        external_control = results["power-path-fixture/external-source-control"]
        dnp_external_fault = results["power-path-fixture/dnp-external-source-fault"]
        alternate_source = results["power-path-fixture/alternate-source-control"]
        both_sources_dnp = results["power-path-fixture/both-sources-dnp-fault"]
        assert external_control["unmapped_lint_status"] == "PASS"
        assert external_control["unmapped_power_input_findings"] == "none"
        assert dnp_external_fault["unmapped_lint_status"] == "REVIEW"
        assert (
            dnp_external_fault["unmapped_power_input_findings"]
            == "power.input_without_supported_source_path:VLOAD: power-input source-path review"
        )
        assert dnp_external_fault["unmapped_other_findings"] == "none"
        assert external_control["source_population"] == "FITTED"
        assert dnp_external_fault["source_population"] == "DNP"
        assert alternate_source["source_population"] == "J1_DNP_J2_FITTED"
        assert alternate_source["lint_status"] == "PASS"
        assert alternate_source["unmapped_lint_status"] == "PASS"
        assert alternate_source["unmapped_power_input_findings"] == "none"
        assert alternate_source["erc_error_types"] == "none"
        assert both_sources_dnp["source_population"] == "BOTH_DNP"
        assert both_sources_dnp["lint_status"] == "REVIEW"
        assert both_sources_dnp["unmapped_lint_status"] == "REVIEW"
        assert (
            both_sources_dnp["unmapped_power_input_findings"]
            == "power.input_without_supported_source_path:VLOAD: power-input source-path review"
        )
        assert both_sources_dnp["unmapped_other_findings"] == "none"
        assert both_sources_dnp["erc_error_types"] == "none"
        assert fault["unmapped_lint_status"] == "REVIEW"
        for case in cases:
            result = results[f"power-path-fixture/{case}"]
            assert result["repeatable"] == "true"
            assert result["erc_error_types"] == "none"
            assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
