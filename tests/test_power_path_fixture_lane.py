"""Orchestration and pinned-native regressions for mapped power-path fixtures."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kicad_tooling.ci_hosted import HostedLog, power_path_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence, ComponentContract, NetlistContract
from tests.test_power_pin_paths import (
    series_diode_netlist,
    series_jumper_netlist,
    series_three_pin_jumper_netlist,
)


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


class PowerPathFixtureLaneTests(unittest.TestCase):
    def test_synthetic_lane_checks_read_only_export_fault_control_and_repeatability(self) -> None:
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
                self.assertEqual(command_root, root.resolve())
                self.assertEqual(timeout, 600)
                self.assertEqual(argv[argv.index("--network") + 1], "none")
                self.assertIn("--read-only", argv)
                self.assertEqual(argv[argv.index("--entrypoint") + 1], "/bin/sh")
                self.assertEqual(argv[argv.index("--platform") + 1], "linux/amd64")
                self.assertIn(image, argv)
                self.assertIn('test "$actual" = "10.0.0"', argv[-1])
                mounts = tuple(
                    argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v"
                )
                self.assertEqual(len(mounts), 2)
                source_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
                output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
                source_directory = Path(source_mount.removesuffix(":/fixtures:ro"))
                output_directory = Path(output_mount.removesuffix(":/output:rw"))
                self.assertEqual(
                    {item.name for item in source_directory.iterdir()},
                    {
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
                    },
                )
                for case in cases:
                    for run in ("first", "repeat"):
                        (output_directory / f"{case}.{run}.netlist.xml").write_text(
                            f"synthetic {case} native output {run}\n", encoding="utf-8"
                        )
                        (output_directory / f"{case}.{run}.erc.json").write_text(
                            '{"kicad_version":"10.0.0","sheets":[{"violations":[]}]}',
                            encoding="utf-8",
                        )
                self.assertIn("kicad-cli sch erc --format json --severity-all", argv[-1])
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
                    wrong_source=case
                    in {"fault", "custom-capacitor-fault", "opaque-capacitor-fault"},
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
                patch(
                    "kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_run_command
                ),
                patch("kicad_tooling.validate.read_netlist", side_effect=fake_read_netlist),
            ):
                power_path_fixture_lane(root, project="synthetic-project", image=image, log=log)

            events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
            results = {
                item["stage"]: item
                for item in events
                if item.get("stage", "").startswith("power-path-fixture/")
            }
            self.assertEqual(
                set(results),
                {
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
                },
            )
            control = results["power-path-fixture/control"]
            self.assertEqual(control["lint_status"], "PASS")
            fault = results["power-path-fixture/fault"]
            self.assertEqual(fault["lint_status"], "REVIEW")
            self.assertIn("source-through-bead-to-load", fault["power_path_findings"])
            self.assertIn("FB1.1 is assigned to GND; expected VIN", fault["power_path_details"])
            self.assertEqual(fault["other_findings"], "none")
            self.assertEqual(control["unmapped_power_input_findings"], "none")
            self.assertEqual(
                fault["unmapped_power_input_findings"],
                "power.input_without_supported_source_path:VLOAD: power-input source-path review",
            )
            self.assertEqual(control["unmapped_lint_status"], "PASS")
            bridged_jumper = results["power-path-fixture/bridged-jumper-control"]
            open_jumper = results["power-path-fixture/open-jumper-fault"]
            self.assertEqual(bridged_jumper["unmapped_lint_status"], "PASS")
            self.assertEqual(bridged_jumper["unmapped_power_input_findings"], "none")
            self.assertEqual(open_jumper["unmapped_lint_status"], "REVIEW")
            self.assertEqual(
                open_jumper["unmapped_power_input_findings"],
                "power.input_without_supported_source_path:VLOAD: power-input source-path review",
            )
            isolated = results["power-path-fixture/isolated-control"]
            self.assertEqual(isolated["lint_status"], "PASS")
            self.assertEqual(isolated["unmapped_lint_status"], "PASS")
            self.assertEqual(isolated["unmapped_power_input_findings"], "none")
            self.assertEqual(isolated["return_nets"], "ISO_RETURN")
            self.assertEqual(isolated["erc_error_types"], "none")
            custom_control = results["power-path-fixture/custom-capacitor-control"]
            custom_fault = results["power-path-fixture/custom-capacitor-fault"]
            opaque_fault = results["power-path-fixture/opaque-capacitor-fault"]
            self.assertEqual(custom_control["unmapped_lint_status"], "PASS")
            self.assertEqual(custom_control["unmapped_power_input_findings"], "none")
            self.assertEqual(custom_fault["unmapped_lint_status"], "REVIEW")
            self.assertEqual(custom_fault["unmapped_other_findings"], "none")
            self.assertIn(
                "power.input_without_supported_source_path:VLOAD",
                custom_fault["unmapped_power_input_findings"],
            )
            self.assertEqual(opaque_fault["unmapped_lint_status"], "REVIEW")
            self.assertEqual(opaque_fault["unmapped_power_input_findings"], "none")
            self.assertEqual(
                opaque_fault["unmapped_other_findings"],
                "power.ic_rail_without_fitted_capacitor:VLOAD: IC supply decoupling review",
            )
            external_control = results["power-path-fixture/external-source-control"]
            dnp_external_fault = results["power-path-fixture/dnp-external-source-fault"]
            alternate_source = results["power-path-fixture/alternate-source-control"]
            both_sources_dnp = results["power-path-fixture/both-sources-dnp-fault"]
            self.assertEqual(external_control["unmapped_lint_status"], "PASS")
            self.assertEqual(external_control["unmapped_power_input_findings"], "none")
            self.assertEqual(dnp_external_fault["unmapped_lint_status"], "REVIEW")
            self.assertEqual(
                dnp_external_fault["unmapped_power_input_findings"],
                "power.input_without_supported_source_path:VLOAD: power-input source-path review",
            )
            self.assertEqual(dnp_external_fault["unmapped_other_findings"], "none")
            self.assertEqual(external_control["source_population"], "FITTED")
            self.assertEqual(dnp_external_fault["source_population"], "DNP")
            self.assertEqual(alternate_source["source_population"], "J1_DNP_J2_FITTED")
            self.assertEqual(alternate_source["lint_status"], "PASS")
            self.assertEqual(alternate_source["unmapped_lint_status"], "PASS")
            self.assertEqual(alternate_source["unmapped_power_input_findings"], "none")
            self.assertEqual(alternate_source["erc_error_types"], "none")
            self.assertEqual(both_sources_dnp["source_population"], "BOTH_DNP")
            self.assertEqual(both_sources_dnp["lint_status"], "REVIEW")
            self.assertEqual(both_sources_dnp["unmapped_lint_status"], "REVIEW")
            self.assertEqual(
                both_sources_dnp["unmapped_power_input_findings"],
                "power.input_without_supported_source_path:VLOAD: power-input source-path review",
            )
            self.assertEqual(both_sources_dnp["unmapped_other_findings"], "none")
            self.assertEqual(both_sources_dnp["erc_error_types"], "none")
            self.assertEqual(fault["unmapped_lint_status"], "REVIEW")
            for case in cases:
                result = results[f"power-path-fixture/{case}"]
                self.assertEqual(result["repeatable"], "true")
                self.assertEqual(result["erc_error_types"], "none")
                self.assertEqual(
                    result["normalized_erc_sha256"], result["repeat_normalized_erc_sha256"]
                )
                self.assertEqual(
                    result["normalized_netlist_sha256"],
                    result["repeat_normalized_netlist_sha256"],
                )


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_POWER_PATH_FIXTURES") == "1",
    "native power-path fixtures run in the digest-pinned package acceptance lane",
)
class NativePowerPathFixtureTests(unittest.TestCase):
    def test_mapped_ferrite_path_control_and_wrong_rail_fault(self) -> None:
        from kicad_tooling.hwrepo.electrical import selected_config
        from tests.support import reference_root

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-power-path-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        expected_source_hashes = {
            "control": "2f81814b683e60208a405e1bed48ea99e72578590ca5b5d3cf5f36217091e83b",
            "fault": "8a042a236f587869ee1da38a04f1dcb8e9f67b38e71b83d32e6000dd0ee7e8f1",
            "diode-control": "b750aa6d2f2a35c8e377108d9ff170dba4ac8c916c9bf45ae5df2ee63f2d3a6e",
            "diode-reverse-fault": "3ccc41b19fefe5cc4d2bd4dcdeab63b1a4818b8ea08c06dfa271623097d71d01",
            "schottky-diode-control": "e445d0500527b88bdbe5e8c7c6b48190c5d3b3b15199b564c4167fdf3d2cecb6",
            "bridged-jumper-control": "b01f9bd7ae106c81928443606fd88e4db34c76a024cf647d264ef0738d91f57d",
            "open-jumper-fault": "0af7bfb07703ced61d99d4769201f164193f34eaeef84611ddb767f234119e59",
            "bridged-three-pin12-control": "c952212ba4302cb5b1c613b2b788b7d5be16dab5d792f21b118af8aa5e3db02b",
            "bridged-three-pin123-control": "87bf21582a48fb399e9eb0739e78140ad0eb721d2622f81ed0db752d34307abd",
            "bridged-three-pin12-unbridged-terminal-fault": "c246a84d7d12059c927a8ecda26c5383e826d89dbee47f7c86b152491cd1f214",
            "isolated-control": "efed3c0180961a10925e61df2a9e147e85d6b7fd13f0db8c32d84a4e77b30970",
            "custom-capacitor-control": "333c63e0a3b629d5d2769d53321f11fe7bb7c21bdf4c47af705994d0d357a4fc",
            "custom-capacitor-fault": "3c70ab0b0a1f6d8846e424d286ba461c5645371067728c44e0f216b63ef5bca9",
            "opaque-capacitor-fault": "46dfad381efae9194734a9b88cad6adf2ead95b9d254436bb060c12e2265eb35",
            "external-source-control": "dd3c7433c0070a1f00a30ed8646085c4a4cd349010c9b2216486f8bff2707539",
            "dnp-external-source-fault": "e1e77f3335c5e5cec3bd3805f87feb644f5ba6486555cf3aba17199ea10f9b30",
            "alternate-source-control": "42d4afac7c4f409b706f09ac5673efaeb0847f0e2042eea4e4623873be77c752",
            "both-sources-dnp-fault": "bbd21576756b29d75c60f1074326309f22741c12f2e699c00fe6b9a4b153020b",
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-power-path-{project}")
                power_path_fixture_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("power-path-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
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
                    },
                )
                control = results["power-path-fixture/control"]
                fault = results["power-path-fixture/fault"]
                bridged_jumper = results["power-path-fixture/bridged-jumper-control"]
                open_jumper = results["power-path-fixture/open-jumper-fault"]
                bridged_three_pin12 = results["power-path-fixture/bridged-three-pin12-control"]
                bridged_three_pin123 = results["power-path-fixture/bridged-three-pin123-control"]
                bridged_three_pin_fault = results[
                    "power-path-fixture/bridged-three-pin12-unbridged-terminal-fault"
                ]
                diode_control = results["power-path-fixture/diode-control"]
                diode_fault = results["power-path-fixture/diode-reverse-fault"]
                schottky_control = results["power-path-fixture/schottky-diode-control"]
                isolated = results["power-path-fixture/isolated-control"]
                custom_control = results["power-path-fixture/custom-capacitor-control"]
                custom_fault = results["power-path-fixture/custom-capacitor-fault"]
                opaque_fault = results["power-path-fixture/opaque-capacitor-fault"]
                external_control = results["power-path-fixture/external-source-control"]
                dnp_external_fault = results["power-path-fixture/dnp-external-source-fault"]
                alternate_source = results["power-path-fixture/alternate-source-control"]
                both_sources_dnp = results["power-path-fixture/both-sources-dnp-fault"]
                self.assertEqual(control["power_path_findings"], "none")
                self.assertIn("source-through-bead-to-load", fault["power_path_findings"])
                self.assertEqual(control["lint_status"], "PASS")
                self.assertEqual(fault["lint_status"], "REVIEW")
                self.assertIn("FB1.1 is assigned to GND; expected VIN", fault["power_path_details"])
                self.assertEqual(
                    diode_control["source_sha256"], expected_source_hashes["diode-control"]
                )
                self.assertEqual(
                    diode_fault["source_sha256"], expected_source_hashes["diode-reverse-fault"]
                )
                self.assertEqual(
                    schottky_control["source_sha256"],
                    expected_source_hashes["schottky-diode-control"],
                )
                self.assertEqual(diode_control["unmapped_lint_status"], "PASS")
                self.assertEqual(diode_control["unmapped_power_input_findings"], "none")
                self.assertEqual(schottky_control["unmapped_lint_status"], "PASS")
                self.assertEqual(schottky_control["unmapped_power_input_findings"], "none")
                self.assertEqual(diode_fault["unmapped_lint_status"], "REVIEW")
                self.assertEqual(
                    diode_fault["unmapped_power_input_findings"],
                    "power.input_without_supported_source_path:VLOAD: power-input source-path review",
                )
                self.assertEqual(bridged_jumper["unmapped_lint_status"], "PASS")
                self.assertEqual(bridged_jumper["unmapped_power_input_findings"], "none")
                self.assertEqual(open_jumper["unmapped_lint_status"], "REVIEW")
                self.assertEqual(
                    open_jumper["unmapped_power_input_findings"],
                    "power.input_without_supported_source_path:VLOAD: power-input source-path review",
                )
                self.assertEqual(bridged_three_pin12["unmapped_lint_status"], "PASS")
                self.assertEqual(bridged_three_pin12["unmapped_power_input_findings"], "none")
                self.assertEqual(bridged_three_pin123["unmapped_lint_status"], "PASS")
                self.assertEqual(bridged_three_pin123["unmapped_power_input_findings"], "none")
                self.assertEqual(bridged_three_pin_fault["unmapped_lint_status"], "REVIEW")
                self.assertEqual(
                    bridged_three_pin_fault["unmapped_power_input_findings"],
                    "power.input_without_supported_source_path:VLOAD: power-input source-path review",
                )
                self.assertEqual(fault["other_findings"], "none")
                self.assertEqual(control["unmapped_power_input_findings"], "none")
                self.assertEqual(
                    fault["unmapped_power_input_findings"],
                    "power.input_without_supported_source_path:VLOAD: power-input source-path review",
                )
                self.assertEqual(control["unmapped_lint_status"], "PASS")
                self.assertEqual(fault["unmapped_lint_status"], "REVIEW")
                self.assertEqual(isolated["power_path_findings"], "none")
                self.assertEqual(isolated["lint_status"], "PASS")
                self.assertEqual(isolated["unmapped_lint_status"], "PASS")
                self.assertEqual(isolated["unmapped_power_input_findings"], "none")
                self.assertEqual(isolated["return_nets"], "ISO_RETURN")
                self.assertEqual(custom_control["power_path_findings"], "none")
                self.assertEqual(custom_control["unmapped_lint_status"], "PASS")
                self.assertEqual(custom_control["unmapped_power_input_findings"], "none")
                self.assertEqual(custom_fault["lint_status"], "REVIEW")
                self.assertEqual(custom_fault["unmapped_lint_status"], "REVIEW")
                self.assertEqual(custom_fault["unmapped_other_findings"], "none")
                self.assertIn(
                    "power.input_without_supported_source_path:VLOAD",
                    custom_fault["unmapped_power_input_findings"],
                )
                self.assertEqual(opaque_fault["lint_status"], "REVIEW")
                self.assertEqual(opaque_fault["unmapped_lint_status"], "REVIEW")
                self.assertEqual(opaque_fault["unmapped_power_input_findings"], "none")
                self.assertEqual(
                    opaque_fault["unmapped_other_findings"],
                    "power.ic_rail_without_fitted_capacitor:VLOAD: IC supply decoupling review",
                )
                self.assertEqual(external_control["lint_status"], "PASS")
                self.assertEqual(external_control["unmapped_lint_status"], "PASS")
                self.assertEqual(external_control["unmapped_power_input_findings"], "none")
                self.assertEqual(dnp_external_fault["lint_status"], "REVIEW")
                self.assertEqual(dnp_external_fault["unmapped_lint_status"], "REVIEW")
                self.assertEqual(
                    dnp_external_fault["unmapped_power_input_findings"],
                    "power.input_without_supported_source_path:VLOAD: power-input source-path review",
                )
                self.assertEqual(dnp_external_fault["unmapped_other_findings"], "none")
                self.assertEqual(external_control["source_population"], "FITTED")
                self.assertEqual(dnp_external_fault["source_population"], "DNP")
                self.assertEqual(alternate_source["source_population"], "J1_DNP_J2_FITTED")
                self.assertEqual(alternate_source["lint_status"], "PASS")
                self.assertEqual(alternate_source["unmapped_lint_status"], "PASS")
                self.assertEqual(alternate_source["unmapped_power_input_findings"], "none")
                self.assertEqual(alternate_source["erc_error_types"], "none")
                self.assertEqual(both_sources_dnp["source_population"], "BOTH_DNP")
                self.assertEqual(both_sources_dnp["lint_status"], "REVIEW")
                self.assertEqual(both_sources_dnp["unmapped_lint_status"], "REVIEW")
                self.assertEqual(
                    both_sources_dnp["unmapped_power_input_findings"],
                    "power.input_without_supported_source_path:VLOAD: power-input source-path review",
                )
                self.assertEqual(both_sources_dnp["unmapped_other_findings"], "none")
                self.assertEqual(both_sources_dnp["erc_error_types"], "none")
                self.assertEqual(external_control["erc_error_types"], "none")
                self.assertEqual(dnp_external_fault["erc_error_types"], "none")
                self.assertEqual(control["erc_error_types"], "none")
                self.assertEqual(fault["erc_error_types"], "none")
                self.assertEqual(control["erc_error_types"], fault["erc_error_types"])
                self.assertEqual(control["erc_violation_types"], fault["erc_violation_types"])
                self.assertEqual(control["kicad_version"], version)
                self.assertEqual(fault["kicad_version"], version)
                for case, result in (
                    ("control", control),
                    ("fault", fault),
                    ("isolated-control", isolated),
                    ("bridged-jumper-control", bridged_jumper),
                    ("open-jumper-fault", open_jumper),
                    ("bridged-three-pin12-control", bridged_three_pin12),
                    ("bridged-three-pin123-control", bridged_three_pin123),
                    ("bridged-three-pin12-unbridged-terminal-fault", bridged_three_pin_fault),
                    ("custom-capacitor-control", custom_control),
                    ("custom-capacitor-fault", custom_fault),
                    ("opaque-capacitor-fault", opaque_fault),
                    ("external-source-control", external_control),
                    ("dnp-external-source-fault", dnp_external_fault),
                    ("alternate-source-control", alternate_source),
                    ("both-sources-dnp-fault", both_sources_dnp),
                ):
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["source_sha256"], expected_source_hashes[case])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["normalized_erc_sha256"],
                        result["repeat_normalized_erc_sha256"],
                    )
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


if __name__ == "__main__":
    unittest.main()
