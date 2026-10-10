"""Digest-pinned native digital-peer fixture regressions."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import (
    HostedLog,
)
from tests.support import reference_root

pytestmark = [pytest.mark.template_checkout, pytest.mark.interface_lint]


SERIAL_LABEL_EXPECTED_NETS = json.loads(
    (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/serial-peer-connector-reference-native/"
        "serial-label-expected-nets.json"
    ).read_text(encoding="utf-8")
)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES") == "1",
    "native digital-peer fixtures run in the digest-pinned package acceptance lane",
)
class NativeDigitalPeerFixtureTests(unittest.TestCase):
    def test_native_pin_functions_drive_unrostered_and_rostered_review_cases(self) -> None:
        from kicad_tooling.ci_hosted import digital_peer_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-spi-participant-project-", dir=acceptance))
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
        expected_source_hash = "0c5d901b4dc70ccb3c3818bd8fdf002955a6322b814ac2e7f8bab086d47d5e06"
        component_peer_netlist_hashes: dict[str, tuple[str, str]] = {}
        peer_voltage_netlist_hashes: dict[str, tuple[str, str, str]] = {}
        serial_peer_netlist_hashes: dict[str, tuple[str, str, str]] = {}
        serial_connector_netlist_hashes: dict[str, tuple[str, str]] = {}
        serial_label_netlist_hashes: dict[str, tuple[str, str]] = {}
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-spi-participant-{project}")
                digital_peer_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith(
                        ("spi-participant-fixture/", "component-peer-power-fixture/")
                    )
                }
                self.assertEqual(
                    set(results),
                    {
                        "spi-participant-fixture/native-export",
                        "spi-participant-fixture/unrostered",
                        "spi-participant-fixture/rostered",
                        "spi-participant-fixture/voltage-control",
                        "spi-participant-fixture/voltage-fault",
                        "spi-participant-fixture/peer-control",
                        "spi-participant-fixture/peer-fault",
                        "spi-participant-fixture/peer-translator-control",
                        "spi-participant-fixture/serial-control",
                        "spi-participant-fixture/serial-fault",
                        "spi-participant-fixture/serial-reference-fault",
                        "spi-participant-fixture/serial-connector-control",
                        "spi-participant-fixture/serial-connector-fault",
                        "spi-participant-fixture/serial-label-control",
                        "spi-participant-fixture/serial-label-fault",
                        "component-peer-power-fixture/control",
                        "component-peer-power-fixture/fault",
                    },
                )
                unrostered = results["spi-participant-fixture/unrostered"]
                self.assertEqual(unrostered["status"], "PASS")
                self.assertEqual(unrostered["lint_status"], "REVIEW")
                self.assertEqual(
                    set(unrostered["findings"].split(";")),
                    {"U1: SPI roster coverage", "U2: SPI roster coverage"},
                )
                self.assertEqual(
                    unrostered["pin_functions"],
                    "U1.1=SPI1_SCLK;U1.2=SPI1_COPI;U1.3=SPI1_CIPO;U1.4=SPI1_NSS;"
                    "U2.1=SPI1_SCLK;U2.2=SPI1_COPI;U2.3=SPI1_CIPO;U2.4=SPI1_NSS",
                )
                rostered = results["spi-participant-fixture/rostered"]
                self.assertEqual(rostered["status"], "PASS")
                self.assertEqual(rostered["lint_status"], "PASS")
                self.assertEqual(rostered["findings"], "none")
                voltage_control = results["spi-participant-fixture/voltage-control"]
                voltage_fault = results["spi-participant-fixture/voltage-fault"]
                self.assertEqual(voltage_control["compatibility_status"], "PASS")
                self.assertAlmostEqual(float(voltage_control["minimum_margin_v"]), 0.3)
                self.assertEqual(voltage_control["driver"], "U1.2/SPI_MOSI")
                self.assertEqual(voltage_control["receiver"], "U2.2/SPI_MOSI")
                self.assertEqual(voltage_fault["compatibility_status"], "FAIL")
                self.assertAlmostEqual(float(voltage_fault["minimum_margin_v"]), -1.4)
                self.assertEqual(voltage_fault["driver"], "U1.2/SPI_MOSI")
                self.assertEqual(voltage_fault["receiver"], "U2.2/SPI_MOSI")
                peer_control = results["spi-participant-fixture/peer-control"]
                peer_fault = results["spi-participant-fixture/peer-fault"]
                translator_control = results["spi-participant-fixture/peer-translator-control"]
                self.assertEqual(peer_control["lint_status"], "PASS")
                self.assertEqual(peer_control["peer_voltage_findings"], "none")
                self.assertEqual(peer_control["rail_assignments"], "+3V3=U1.2,U2.2")
                self.assertEqual(peer_fault["lint_status"], "REVIEW")
                self.assertEqual(peer_fault["peer_voltage_findings"], "bus.spi_peer_voltage_review")
                self.assertEqual(peer_fault["rail_assignments"], "+3V3=U2.2;+5V=U1.2")
                self.assertEqual(
                    peer_fault["pin_functions"],
                    "U1.1=SPI1_SCLK;U1.2=VDD;U2.1=SPI1_SCLK;U2.2=VDD",
                )
                self.assertEqual(
                    peer_fault["pin_types"],
                    "U1.1=output;U1.2=power_in;U2.1=input;U2.2=power_in",
                )
                self.assertEqual(translator_control["lint_status"], "PASS")
                self.assertEqual(translator_control["peer_voltage_findings"], "none")
                self.assertEqual(
                    translator_control["signal_assignments"],
                    "SPI_A_SIDE=U1.1,U3.1;SPI_B_SIDE=U2.1,U3.2",
                )
                self.assertEqual(
                    translator_control["rail_assignments"],
                    "+3V3=U2.2,U3.4;+5V=U1.2,U3.3",
                )
                serial_control = results["spi-participant-fixture/serial-control"]
                serial_fault = results["spi-participant-fixture/serial-fault"]
                self.assertEqual(serial_control["lint_status"], "PASS")
                self.assertEqual(serial_control["peer_voltage_findings"], "none")
                self.assertEqual(serial_control["peer_reference_findings"], "none")
                self.assertEqual(serial_control["reference_assignments"], "GND=U1.3,U2.3")
                self.assertEqual(
                    serial_control["source_sha256"],
                    "3c420e5cde0e0c6ee52cb5b5f63fb243237dcb846e7ac6057e61f4b30df7ff79",
                )
                self.assertEqual(serial_control["rail_assignments"], "+3V3=U1.2,U2.2")
                self.assertEqual(serial_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    serial_fault["peer_voltage_findings"],
                    "bus.serial_peer_voltage_review",
                )
                self.assertEqual(
                    serial_fault["peer_reference_findings"],
                    "none",
                )
                self.assertEqual(
                    serial_fault["reference_assignments"],
                    "GND=U1.3,U2.3",
                )
                self.assertEqual(
                    serial_fault["source_sha256"],
                    "14f7c4097f270ed806c471df7d49f4f0dd18607de6402312920e16840f5afdd3",
                )
                self.assertEqual(serial_fault["rail_assignments"], "+3V3=U2.2;+5V=U1.2")
                reference_fault = results["spi-participant-fixture/serial-reference-fault"]
                self.assertEqual(reference_fault["lint_status"], "REVIEW")
                self.assertEqual(reference_fault["peer_voltage_findings"], "none")
                self.assertEqual(
                    reference_fault["peer_reference_findings"],
                    "bus.serial_peer_reference_review",
                )
                self.assertEqual(
                    reference_fault["reference_assignments"],
                    "GND_A=U1.3;GND_B=U2.3",
                )
                self.assertEqual(
                    reference_fault["source_sha256"],
                    "d3c9a6e14e9bc4314c2b616e8be3962638161b1e056789ea7b66977e430081be",
                )
                self.assertEqual(
                    reference_fault["rail_assignments"],
                    "+3V3=U1.2,U2.2",
                )
                serial_connector_control = results[
                    "spi-participant-fixture/serial-connector-control"
                ]
                serial_connector_fault = results["spi-participant-fixture/serial-connector-fault"]
                serial_label_control = results["spi-participant-fixture/serial-label-control"]
                serial_label_fault = results["spi-participant-fixture/serial-label-fault"]
                self.assertEqual(serial_connector_control["lint_status"], "REVIEW")
                self.assertEqual(serial_connector_control["peer_reference_findings"], "none")
                self.assertEqual(
                    serial_connector_control["reference_assignments"], "GND_A=J1.4,U1.4"
                )
                self.assertEqual(serial_connector_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    serial_connector_fault["peer_reference_findings"],
                    "bus.serial_peer_reference_review",
                )
                self.assertEqual(
                    serial_connector_fault["reference_assignments"],
                    "GND_A=U1.4;GND_B=J1.4",
                )
                self.assertEqual(
                    serial_connector_fault["signal_assignments"],
                    "UART_RX=J1.2,U1.2;UART_TX=J1.1,U1.1",
                )
                self.assertEqual(
                    serial_connector_fault["pin_functions"],
                    "J1.1=UART1_RX;J1.2=UART1_TX;J1.3=VDD;J1.4=GND;"
                    "U1.1=UART1_TX;U1.2=UART1_RX;U1.3=VDD;U1.4=GND",
                )
                self.assertEqual(
                    serial_connector_fault["pin_types"],
                    "J1.1=input;J1.2=output;J1.3=passive;J1.4=passive;"
                    "U1.1=output;U1.2=input;U1.3=power_in;U1.4=power_in",
                )
                self.assertEqual(serial_label_control["lint_status"], "REVIEW")
                self.assertEqual(serial_label_control["peer_reference_findings"], "none")
                self.assertEqual(serial_label_control["reference_assignments"], "GND_A=U1.4,U2.4")
                self.assertEqual(serial_label_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    serial_label_fault["peer_reference_findings"],
                    "bus.serial_peer_reference_review",
                )
                self.assertEqual(
                    serial_label_fault["reference_assignments"], "GND_A=U1.4;GND_B=U2.4"
                )
                self.assertEqual(
                    serial_label_fault["signal_assignments"],
                    ";".join(
                        f"{net}={','.join(pins)}"
                        for net, pins in sorted(SERIAL_LABEL_EXPECTED_NETS.items())
                    ),
                )
                self.assertEqual(
                    serial_label_fault["pin_functions"],
                    "U1.1=B2;U1.2=B1;U1.3=VDD;U1.4=GND;U2.1=ADBUS0;U2.2=ADBUS1;U2.3=VDD;U2.4=GND",
                )
                self.assertEqual(
                    serial_label_fault["pin_types"],
                    "U1.1=output;U1.2=input;U1.3=power_in;U1.4=power_in;"
                    "U2.1=input;U2.2=output;U2.3=passive;U2.4=passive",
                )
                self.assertEqual(
                    serial_fault["pin_functions"],
                    "U1.1=UART1_TX;U1.2=VDD;U1.3=GND;U2.1=UART1_RX;U2.2=VDD;U2.3=GND",
                )
                self.assertEqual(
                    serial_fault["pin_types"],
                    "U1.1=output;U1.2=power_in;U1.3=power_in;U2.1=input;U2.2=power_in;U2.3=power_in",
                )
                serial_peer_netlist_hashes[version] = (
                    serial_control["normalized_netlist_sha256"],
                    serial_fault["normalized_netlist_sha256"],
                    reference_fault["normalized_netlist_sha256"],
                )
                peer_voltage_netlist_hashes[version] = (
                    peer_control["normalized_netlist_sha256"],
                    peer_fault["normalized_netlist_sha256"],
                    translator_control["normalized_netlist_sha256"],
                )
                serial_connector_netlist_hashes[version] = (
                    serial_connector_control["normalized_netlist_sha256"],
                    serial_connector_fault["normalized_netlist_sha256"],
                )
                serial_label_netlist_hashes[version] = (
                    serial_label_control["normalized_netlist_sha256"],
                    serial_label_fault["normalized_netlist_sha256"],
                )
                component_peer_control = results["component-peer-power-fixture/control"]
                component_peer_fault = results["component-peer-power-fixture/fault"]
                self.assertEqual(component_peer_control["lint_status"], "PASS")
                self.assertEqual(component_peer_control["peer_power_findings"], "none")
                self.assertEqual(
                    component_peer_control["pin_assignments"],
                    "U1.1=IO_SHARED;U1.2=+3V3;U1.3=GND;U2.1=IO_SHARED;U2.2=+3V3;U2.3=GND",
                )
                self.assertEqual(component_peer_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    component_peer_fault["peer_power_findings"],
                    "component.peer_power_pin_assignment_divergence;"
                    "component.peer_power_pin_assignment_divergence",
                )
                self.assertEqual(
                    component_peer_fault["divergent_pin_roles"],
                    "2:VDD:supply;3:GND:ground/return",
                )
                self.assertEqual(
                    component_peer_fault["pin_assignments"],
                    "U1.1=IO_SHARED;U1.2=+3V3;U1.3=AGND;U2.1=IO_SHARED;U2.2=+5V;U2.3=DGND",
                )
                expected_erc_signatures = {
                    "component-peer-power-fixture/control": (
                        "power_pin_not_driven;power_pin_not_driven",
                        (
                            "footprint_link_issues;footprint_link_issues;"
                            "lib_symbol_issues;lib_symbol_issues"
                        ),
                    ),
                    "component-peer-power-fixture/fault": (
                        (
                            "power_pin_not_driven;power_pin_not_driven;"
                            "power_pin_not_driven;power_pin_not_driven"
                        ),
                        (
                            "footprint_link_issues;footprint_link_issues;"
                            "isolated_pin_label;isolated_pin_label;isolated_pin_label;isolated_pin_label;"
                            "lib_symbol_issues;lib_symbol_issues"
                        ),
                    ),
                }
                for result in (component_peer_control, component_peer_fault):
                    expected_errors, expected_warnings = expected_erc_signatures[result["stage"]]
                    self.assertEqual(result["erc_error_types"], expected_errors)
                    self.assertEqual(result["erc_warning_types"], expected_warnings)
                component_peer_netlist_hashes[version] = (
                    component_peer_control["normalized_netlist_sha256"],
                    component_peer_fault["normalized_netlist_sha256"],
                )
                for result in (
                    unrostered,
                    rostered,
                    voltage_control,
                    voltage_fault,
                    peer_control,
                    peer_fault,
                    translator_control,
                    serial_control,
                    serial_fault,
                    reference_fault,
                    serial_connector_control,
                    serial_connector_fault,
                    component_peer_control,
                    component_peer_fault,
                ):
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["repeatability_basis"],
                        (
                            "normalized_native_netlist_and_electrical_checks"
                            if "compatibility_status" in result
                            else (
                                "normalized_native_netlist_and_design_lint_report"
                                if "peer_voltage_findings" in result
                                or "peer_reference_findings" in result
                                or "peer_power_findings" in result
                                else "normalized_netlist_contract"
                            )
                        ),
                    )
                    if "peer_power_findings" in result:
                        self.assertEqual(result["erc_report_version"], version)
                        self.assertEqual(
                            result["normalized_erc_sha256"],
                            result["repeat_normalized_erc_sha256"],
                        )
                        expected_component_peer_hashes = {
                            "component-peer-power-fixture/control": "0198205216be6cd5be0c03ac14b7c2b9de52258aacd564159e16532fadb10446",
                            "component-peer-power-fixture/fault": "92a2cfda8088c7eebe8305e5ecf786870ed44bc846acb031fe4bb1d567418ae3",
                        }
                        self.assertEqual(
                            result["source_sha256"],
                            expected_component_peer_hashes[result["stage"]],
                        )
                    elif "peer_voltage_findings" in result or "peer_reference_findings" in result:
                        expected_peer_hashes = {
                            "spi-participant-fixture/peer-control": "427bfd18783c800ddc0b9e48d4ce95db8d26ac4fb27bf2a36921908016d75cdd",
                            "spi-participant-fixture/peer-fault": "98ca9f8d999892b9441019064f36eba776eec18770e23519cde30ff1a532e5a4",
                            "spi-participant-fixture/peer-translator-control": "58f2ac474e5c055fc5ff3f5e2f9be0613fc7339298244de035740ca85eaa80a1",
                            "spi-participant-fixture/serial-control": "3c420e5cde0e0c6ee52cb5b5f63fb243237dcb846e7ac6057e61f4b30df7ff79",
                            "spi-participant-fixture/serial-fault": "14f7c4097f270ed806c471df7d49f4f0dd18607de6402312920e16840f5afdd3",
                            "spi-participant-fixture/serial-reference-fault": "d3c9a6e14e9bc4314c2b616e8be3962638161b1e056789ea7b66977e430081be",
                            "spi-participant-fixture/serial-connector-control": "7d086f4f838504fa3cefc906f7f9e415240b10d89e95c9063c19780922915f16",
                            "spi-participant-fixture/serial-connector-fault": "ee9ce9a51a78c422da96e260720247bb09403abe314921952f29c5d9ba110c20",
                            "spi-participant-fixture/serial-label-control": "a0ac8548431af625c5116c1d456e4f2c6cf1714e58cca84c6fe595165d87c561",
                            "spi-participant-fixture/serial-label-fault": "2006adbfa6c6f1c99e88e3320a1ed7230f01a02f5e143c16a946abaa34f9db20",
                        }
                        self.assertEqual(
                            result["source_sha256"], expected_peer_hashes[result["stage"]]
                        )
                    else:
                        self.assertEqual(result["source_sha256"], expected_source_hash)
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
        self.assertEqual(
            component_peer_netlist_hashes["10.0.0"],
            component_peer_netlist_hashes["10.0.5"],
        )
        self.assertEqual(
            component_peer_netlist_hashes["10.0.0"],
            (
                "27b214dc9bd5b33dc7732f1155267462fb7a4efdcd2ed8efb7614ad3e489c0b6",
                "afb64b0e55b04276c8c2d45e94a6aeec056a424aeff2bb349be5aba78b36a1f9",
            ),
        )
        self.assertEqual(serial_peer_netlist_hashes["10.0.0"], serial_peer_netlist_hashes["10.0.5"])
        self.assertEqual(
            peer_voltage_netlist_hashes["10.0.0"], peer_voltage_netlist_hashes["10.0.5"]
        )
        self.assertEqual(
            serial_connector_netlist_hashes["10.0.0"],
            serial_connector_netlist_hashes["10.0.5"],
        )
        self.assertEqual(
            serial_label_netlist_hashes["10.0.0"],
            serial_label_netlist_hashes["10.0.5"],
        )
        self.assertEqual(
            serial_peer_netlist_hashes["10.0.0"],
            (
                "ab26230622e20694fa31df7921381d1c0b629a2f4b5b99a24aa05e7ffa99aac8",
                "c5781c55ed8d12e5fa71b6d4302e9de5893d29014ad392c9e8a6b942368ea11c",
                "c92f4dffc776643127fb64b419f0d117acc97c6ec800549b51e990c407b5da60",
            ),
        )
