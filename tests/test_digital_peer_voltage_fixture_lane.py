"""Orchestration checks for pinned native SPI and UART peer-voltage fixtures."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kicad_tooling.ci_hosted import HostedLog, digital_peer_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence, ComponentContract, NetlistContract
from tests.test_serial_peer_reference_review import serial_connector_reference_netlist

SERIAL_LABEL_EXPECTED_NETS = {
    net: tuple(pins)
    for net, pins in json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures/design_lint/serial-peer-connector-reference-native/"
            "serial-label-expected-nets.json"
        ).read_text(encoding="utf-8")
    ).items()
}


def participant_netlist() -> NetlistContract:
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI node", footprint="Synthetic:QFN"),
            "U2": ComponentContract(value="Synthetic SPI node", footprint="Synthetic:QFN"),
        },
        nets={
            "SPI_SCK": ("U1.1", "U2.1"),
            "SPI_MOSI": ("U1.2", "U2.2"),
            "SPI_MISO": ("U1.3", "U2.3"),
            "SPI_CS": ("U1.4", "U2.4"),
        },
        component_symbols={"U1": "Synthetic:SPI_Node", "U2": "Synthetic:SPI_Node"},
        pin_functions={
            "U1.1": "SPI1_SCLK",
            "U1.2": "SPI1_COPI",
            "U1.3": "SPI1_CIPO",
            "U1.4": "SPI1_NSS",
            "U2.1": "SPI1_SCLK",
            "U2.2": "SPI1_COPI",
            "U2.3": "SPI1_CIPO",
            "U2.4": "SPI1_NSS",
        },
        component_pin_numbers={"U1": ("1", "2", "3", "4"), "U2": ("1", "2", "3", "4")},
    )


def peer_netlist(*, split_supplies: bool) -> NetlistContract:
    nets = {
        "SPI_SCK": ("U1.1", "U2.1"),
        "+3V3": ("U2.2",) if split_supplies else ("U1.2", "U2.2"),
    }
    if split_supplies:
        nets["+5V"] = ("U1.2",)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI controller", footprint="Synthetic:QFN-2"),
            "U2": ComponentContract(value="Synthetic SPI peripheral", footprint="Synthetic:QFN-2"),
        },
        nets=nets,
        component_symbols={
            "U1": "Synthetic:SPI_Controller",
            "U2": "Synthetic:SPI_Peripheral",
        },
        pin_functions={
            "U1.1": "SPI1_SCLK",
            "U1.2": "VDD",
            "U2.1": "SPI1_SCLK",
            "U2.2": "VDD",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "power_in",
            "U2.1": "input",
            "U2.2": "power_in",
        },
        component_pin_numbers={"U1": ("1", "2"), "U2": ("1", "2")},
    )


def translator_peer_netlist() -> NetlistContract:
    """Mirror the native synthetic control with separate translator-side nets."""
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI controller", footprint="Synthetic:QFN-3"),
            "U2": ComponentContract(value="Synthetic SPI peripheral", footprint="Synthetic:QFN-3"),
            "U3": ComponentContract(
                value="Synthetic SPI level translator", footprint="Synthetic:Translator-5"
            ),
        },
        nets={
            "+5V": ("U1.2", "U3.3"),
            "+3V3": ("U2.2", "U3.4"),
            "GND": ("U1.3", "U2.3", "U3.5"),
            "SPI_A_SIDE": ("U1.1", "U3.1"),
            "SPI_B_SIDE": ("U2.1", "U3.2"),
        },
        component_symbols={
            "U1": "Synthetic:SPI_Controller",
            "U2": "Synthetic:SPI_Peripheral",
            "U3": "Synthetic:SPI_LevelTranslator",
        },
        pin_functions={
            "U1.1": "SPI1_SCLK",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "SPI1_SCLK",
            "U2.2": "VDD",
            "U2.3": "GND",
            "U3.1": "A_SCLK",
            "U3.2": "B_SCLK",
            "U3.3": "VCCA",
            "U3.4": "VCCB",
            "U3.5": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "input",
            "U2.2": "power_in",
            "U2.3": "power_in",
            "U3.1": "input",
            "U3.2": "output",
            "U3.3": "power_in",
            "U3.4": "power_in",
            "U3.5": "power_in",
        },
        component_pin_numbers={
            "U1": ("1", "2", "3"),
            "U2": ("1", "2", "3"),
            "U3": ("1", "2", "3", "4", "5"),
        },
    )


def serial_peer_netlist(*, split_supplies: bool, split_references: bool = False) -> NetlistContract:
    rails = (
        {"+3V3": ("U1.2", "U2.2")} if not split_supplies else {"+5V": ("U1.2",), "+3V3": ("U2.2",)}
    )
    references = (
        {"GND_A": ("U1.3",), "GND_B": ("U2.3",)} if split_references else {"GND": ("U1.3", "U2.3")}
    )
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART transmitter", footprint="Synthetic:QFN-2"
            ),
            "U2": ComponentContract(value="Synthetic UART receiver", footprint="Synthetic:QFN-2"),
        },
        nets={
            "UART_TX": ("U1.1", "U2.1"),
            **rails,
            **references,
        },
        component_symbols={
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
        },
        pin_functions={
            "U1.1": "UART1_TX",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "UART1_RX",
            "U2.2": "VDD",
            "U2.3": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "input",
            "U2.2": "power_in",
            "U2.3": "power_in",
        },
        component_pin_numbers={"U1": ("1", "2", "3"), "U2": ("1", "2", "3")},
    )


def serial_label_reference_netlist(*, split_references: bool) -> NetlistContract:
    """Mirror the labeled signal assignments in the fixture manifest."""
    references = (
        {"GND_A": ("U1.4", "U2.4")}
        if not split_references
        else {"GND_A": ("U1.4",), "GND_B": ("U2.4",)}
    )
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART controller", footprint="Synthetic:UART-CONTROLLER"
            ),
            "U2": ComponentContract(
                value="Synthetic serial bridge", footprint="Synthetic:UART-BRIDGE"
            ),
        },
        nets={
            **SERIAL_LABEL_EXPECTED_NETS,
            "+3V3": ("U1.3", "U2.3"),
            **references,
        },
        component_symbols={"U1": "Synthetic:UartController", "U2": "Synthetic:UartBridge"},
        pin_functions={
            "U1.1": "B2",
            "U1.2": "B1",
            "U1.3": "VDD",
            "U1.4": "GND",
            "U2.1": "ADBUS0",
            "U2.2": "ADBUS1",
            "U2.3": "VDD",
            "U2.4": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
            "U2.1": "input",
            "U2.2": "output",
            "U2.3": "passive",
            "U2.4": "passive",
        },
        component_pin_numbers={"U1": ("1", "2", "3", "4"), "U2": ("1", "2", "3", "4")},
    )


def component_peer_power_netlist(*, split_domains: bool) -> NetlistContract:
    nets = {
        "IO_SHARED": ("U1.1", "U2.1"),
        "+3V3": ("U1.2", "U2.2") if not split_domains else ("U1.2",),
        "GND": ("U1.3", "U2.3") if not split_domains else ("U1.3",),
    }
    if split_domains:
        nets["+5V"] = ("U2.2",)
        nets["AGND"] = nets.pop("GND")
        nets["DGND"] = ("U2.3",)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic peer module", footprint="Synthetic:QFN-2"),
            "U2": ComponentContract(value="Synthetic peer module", footprint="Synthetic:QFN-2"),
        },
        nets=nets,
        component_symbols={"U1": "Synthetic:PeerModule", "U2": "Synthetic:PeerModule"},
        pin_functions={
            "U1.1": "IO",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "IO",
            "U2.2": "VDD",
            "U2.3": "GND",
        },
        pin_electrical_types={
            "U1.1": "passive",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "passive",
            "U2.2": "power_in",
            "U2.3": "power_in",
        },
        component_pin_numbers={"U1": ("1", "2", "3"), "U2": ("1", "2", "3")},
    )


class DigitalPeerVoltageFixtureLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="digital-peer-voltage-lane-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.image = "fixture.invalid/kicad@sha256:" + "c" * 64
        self.config = SimpleNamespace(image=self.image, kicad_version="10.0.0")

    def test_spi_peer_voltage_sources_match_recorded_synthetic_digests(self) -> None:
        fixture_root = (
            Path(__file__).resolve().parent / "fixtures/design_lint/spi-peer-voltage-native"
        )
        expected = {
            "peer-control.kicad_sch": "427bfd18783c800ddc0b9e48d4ce95db8d26ac4fb27bf2a36921908016d75cdd",
            "peer-fault.kicad_sch": "98ca9f8d999892b9441019064f36eba776eec18770e23519cde30ff1a532e5a4",
            "peer-translator-control.kicad_sch": "58f2ac474e5c055fc5ff3f5e2f9be0613fc7339298244de035740ca85eaa80a1",
        }
        for name, sha256 in expected.items():
            with self.subTest(fixture=name):
                source = fixture_root / name
                text = source.read_text(encoding="utf-8")
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), sha256)
                self.assertIn("NOT FOR MANUFACTURE - tooling fixture", text)
        translator = (fixture_root / "peer-translator-control.kicad_sch").read_text(
            encoding="utf-8"
        )
        for pin_name in ('"A_SCLK"', '"B_SCLK"', '"VCCA"', '"VCCB"'):
            self.assertIn(pin_name, translator)

    def test_native_lane_checks_voltage_named_peer_fault_and_control(self) -> None:
        def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
            self.assertEqual(root, self.root)
            self.assertEqual(timeout, 600)
            self.assertEqual(argv[argv.index("--network") + 1], "none")
            self.assertIn("--read-only", argv)
            self.assertIn(self.image, argv)
            script = argv[-1]
            self.assertIn('test "$actual" = "10.0.0"', script)
            self.assertIn("kicad-cli sch erc --format json --severity-all", script)
            self.assertIn(
                "peer-control peer-fault peer-translator-control serial-control serial-fault "
                "serial-reference-fault "
                "serial-connector-control serial-connector-fault "
                "serial-label-control serial-label-fault "
                "component-peer-control component-peer-fault",
                script,
            )
            mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
            fixture_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
            output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
            fixtures = Path(fixture_mount.removesuffix(":/fixtures:ro"))
            output = Path(output_mount.removesuffix(":/output:rw"))
            self.assertEqual(
                {item.name for item in fixtures.iterdir()},
                {
                    "multi-device.kicad_sch",
                    "peer-control.kicad_sch",
                    "peer-fault.kicad_sch",
                    "peer-translator-control.kicad_sch",
                    "serial-control.kicad_sch",
                    "serial-fault.kicad_sch",
                    "serial-reference-fault.kicad_sch",
                    "serial-connector-control.kicad_sch",
                    "serial-connector-fault.kicad_sch",
                    "serial-label-control.kicad_sch",
                    "serial-label-fault.kicad_sch",
                    "component-peer-control.kicad_sch",
                    "component-peer-fault.kicad_sch",
                },
            )
            for case in (
                "multi-device",
                "peer-control",
                "peer-fault",
                "peer-translator-control",
                "serial-control",
                "serial-fault",
                "serial-reference-fault",
                "serial-connector-control",
                "serial-connector-fault",
                "serial-label-control",
                "serial-label-fault",
                "component-peer-control",
                "component-peer-fault",
            ):
                for run in ("first", "repeat"):
                    (output / f"{case}.{run}.netlist.xml").write_text(
                        f"synthetic {case} export {run}\n", encoding="utf-8"
                    )
                    if case.startswith("component-peer-"):
                        (output / f"{case}.{run}.erc.json").write_text(
                            json.dumps({"kicad_version": "10.0.0", "sheets": []}),
                            encoding="utf-8",
                        )
            return CommandEvidence(
                argv=argv,
                started_utc="2026-10-01T00:00:00+00:00",
                returncode=0,
                stdout="kicad_version=10.0.0\n",
            )

        def fake_read_netlist(path: Path) -> NetlistContract:
            if path.name.startswith("peer-translator-control"):
                return translator_peer_netlist()
            if path.name.startswith("component-peer-control"):
                return component_peer_power_netlist(split_domains=False)
            if path.name.startswith("component-peer-fault"):
                return component_peer_power_netlist(split_domains=True)
            if path.name.startswith("peer-control"):
                return peer_netlist(split_supplies=False)
            if path.name.startswith("peer-fault"):
                return peer_netlist(split_supplies=True)
            if path.name.startswith("serial-control"):
                return serial_peer_netlist(split_supplies=False)
            if path.name.startswith("serial-fault"):
                return serial_peer_netlist(split_supplies=True)
            if path.name.startswith("serial-reference-fault"):
                return serial_peer_netlist(split_supplies=False, split_references=True)
            if path.name.startswith("serial-connector-control"):
                return serial_connector_reference_netlist(
                    output_reference_net="GND_A", input_reference_net="GND_A"
                )
            if path.name.startswith("serial-connector-fault"):
                return serial_connector_reference_netlist()
            if path.name.startswith("serial-label-control"):
                return serial_label_reference_netlist(split_references=False)
            if path.name.startswith("serial-label-fault"):
                return serial_label_reference_netlist(split_references=True)
            return participant_netlist()

        log = HostedLog(self.root, "digital-peer-voltage")
        with (
            patch("kicad_tooling.hwrepo.electrical.selected_config", return_value=self.config),
            patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_run_command),
            patch("kicad_tooling.validate.read_netlist", side_effect=fake_read_netlist),
        ):
            digital_peer_fixture_lane(
                self.root,
                project="synthetic-project",
                image=self.image,
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
        control = results["spi-participant-fixture/peer-control"]
        fault = results["spi-participant-fixture/peer-fault"]
        self.assertEqual(control["lint_status"], "PASS")
        self.assertEqual(control["peer_voltage_findings"], "none")
        self.assertEqual(fault["lint_status"], "REVIEW")
        self.assertEqual(fault["peer_voltage_findings"], "bus.spi_peer_voltage_review")
        self.assertEqual(fault["pin_types"], "U1.1=output;U1.2=power_in;U2.1=input;U2.2=power_in")
        self.assertEqual(fault["rail_assignments"], "+3V3=U2.2;+5V=U1.2")
        translator_control = results["spi-participant-fixture/peer-translator-control"]
        self.assertEqual(translator_control["lint_status"], "PASS")
        self.assertEqual(translator_control["peer_voltage_findings"], "none")
        self.assertEqual(
            translator_control["pin_functions"],
            "U1.1=SPI1_SCLK;U1.2=VDD;U1.3=GND;U2.1=SPI1_SCLK;U2.2=VDD;"
            "U2.3=GND;U3.1=A_SCLK;U3.2=B_SCLK;U3.3=VCCA;U3.4=VCCB;U3.5=GND",
        )
        self.assertEqual(
            translator_control["rail_assignments"],
            "+3V3=U2.2,U3.4;+5V=U1.2,U3.3",
        )
        self.assertEqual(
            translator_control["signal_assignments"],
            "SPI_A_SIDE=U1.1,U3.1;SPI_B_SIDE=U2.1,U3.2",
        )
        serial_control = results["spi-participant-fixture/serial-control"]
        serial_fault = results["spi-participant-fixture/serial-fault"]
        serial_reference_fault = results["spi-participant-fixture/serial-reference-fault"]
        serial_connector_control = results["spi-participant-fixture/serial-connector-control"]
        serial_connector_fault = results["spi-participant-fixture/serial-connector-fault"]
        serial_label_control = results["spi-participant-fixture/serial-label-control"]
        serial_label_fault = results["spi-participant-fixture/serial-label-fault"]
        self.assertEqual(serial_control["lint_status"], "PASS")
        self.assertEqual(serial_control["peer_voltage_findings"], "none")
        self.assertEqual(serial_control["peer_reference_findings"], "none")
        self.assertEqual(serial_fault["lint_status"], "REVIEW")
        self.assertEqual(serial_fault["peer_voltage_findings"], "bus.serial_peer_voltage_review")
        self.assertEqual(
            serial_fault["pin_functions"],
            "U1.1=UART1_TX;U1.2=VDD;U1.3=GND;U2.1=UART1_RX;U2.2=VDD;U2.3=GND",
        )
        self.assertEqual(serial_fault["rail_assignments"], "+3V3=U2.2;+5V=U1.2")
        self.assertEqual(serial_reference_fault["lint_status"], "REVIEW")
        self.assertEqual(serial_reference_fault["peer_voltage_findings"], "none")
        self.assertEqual(
            serial_reference_fault["peer_reference_findings"],
            "bus.serial_peer_reference_review",
        )
        self.assertEqual(serial_reference_fault["reference_assignments"], "GND_A=U1.3;GND_B=U2.3")
        self.assertEqual(serial_connector_control["peer_reference_findings"], "none")
        self.assertEqual(serial_connector_control["reference_assignments"], "GND_A=J1.4,U1.4")
        self.assertEqual(
            serial_connector_fault["peer_reference_findings"],
            "bus.serial_peer_reference_review",
        )
        self.assertEqual(serial_connector_fault["reference_assignments"], "GND_A=U1.4;GND_B=J1.4")
        self.assertEqual(serial_label_control["lint_status"], "REVIEW")
        self.assertEqual(serial_label_control["peer_reference_findings"], "none")
        self.assertEqual(serial_label_control["reference_assignments"], "GND_A=U1.4,U2.4")
        self.assertEqual(serial_label_fault["lint_status"], "REVIEW")
        self.assertEqual(
            serial_label_fault["peer_reference_findings"],
            "bus.serial_peer_reference_review",
        )
        self.assertEqual(serial_label_fault["reference_assignments"], "GND_A=U1.4;GND_B=U2.4")
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
        component_control = results["component-peer-power-fixture/control"]
        component_fault = results["component-peer-power-fixture/fault"]
        self.assertEqual(component_control["lint_status"], "PASS")
        self.assertEqual(component_control["peer_power_findings"], "none")
        self.assertEqual(
            component_control["pin_assignments"],
            "U1.1=IO_SHARED;U1.2=+3V3;U1.3=GND;U2.1=IO_SHARED;U2.2=+3V3;U2.3=GND",
        )
        self.assertEqual(component_fault["lint_status"], "REVIEW")
        self.assertEqual(
            component_fault["peer_power_findings"],
            "component.peer_power_pin_assignment_divergence;"
            "component.peer_power_pin_assignment_divergence",
        )
        self.assertEqual(
            component_fault["divergent_pin_roles"],
            "2:VDD:supply;3:GND:ground/return",
        )
        self.assertEqual(
            component_fault["pin_assignments"],
            "U1.1=IO_SHARED;U1.2=+3V3;U1.3=AGND;U2.1=IO_SHARED;U2.2=+5V;U2.3=DGND",
        )
        for result in (component_control, component_fault):
            self.assertEqual(result["erc_report_version"], "10.0.0")
            self.assertEqual(result["erc_warning_types"], "none")
            self.assertEqual(result["erc_error_types"], "none")
            self.assertEqual(
                result["normalized_erc_sha256"], result["repeat_normalized_erc_sha256"]
            )
        for result in (
            control,
            fault,
            translator_control,
            serial_control,
            serial_fault,
            serial_reference_fault,
            serial_label_control,
            serial_label_fault,
            component_control,
            component_fault,
        ):
            self.assertEqual(result["repeatable"], "true")
            self.assertEqual(
                result["normalized_netlist_sha256"], result["repeat_normalized_netlist_sha256"]
            )

    def test_component_peer_power_sources_match_recorded_synthetic_digests(self) -> None:
        fixture_root = (
            Path(__file__).resolve().parent / "fixtures/design_lint/component-peer-power-native"
        )
        expected = {
            "control.kicad_sch": "0198205216be6cd5be0c03ac14b7c2b9de52258aacd564159e16532fadb10446",
            "fault.kicad_sch": "92a2cfda8088c7eebe8305e5ecf786870ed44bc846acb031fe4bb1d567418ae3",
        }
        for name, sha256 in expected.items():
            with self.subTest(fixture=name):
                source = fixture_root / name
                text = source.read_text(encoding="utf-8")
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), sha256)
                self.assertIn("NOT FOR MANUFACTURE - tooling fixture", text)
                self.assertEqual(text.count('(symbol "Synthetic:PeerModule"'), 1)
                self.assertEqual(text.count('(lib_id "Synthetic:PeerModule")'), 2)

    def test_serial_peer_voltage_sources_match_recorded_synthetic_digests(self) -> None:
        fixture_root = (
            Path(__file__).resolve().parent / "fixtures/design_lint/serial-peer-voltage-native"
        )
        expected = {
            "serial-control.kicad_sch": "3c420e5cde0e0c6ee52cb5b5f63fb243237dcb846e7ac6057e61f4b30df7ff79",
            "serial-fault.kicad_sch": "14f7c4097f270ed806c471df7d49f4f0dd18607de6402312920e16840f5afdd3",
            "serial-reference-fault.kicad_sch": "d3c9a6e14e9bc4314c2b616e8be3962638161b1e056789ea7b66977e430081be",
        }
        for name, sha256 in expected.items():
            with self.subTest(fixture=name):
                source = fixture_root / name
                text = source.read_text(encoding="utf-8")
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), sha256)
                self.assertIn("NOT FOR MANUFACTURE - tooling fixture", text)
                self.assertIn('"UART1_TX"', text)
                self.assertIn('"UART1_RX"', text)

    def test_channel_label_reference_sources_match_recorded_synthetic_digests(self) -> None:
        fixture_root = (
            Path(__file__).resolve().parent
            / "fixtures/design_lint/serial-peer-connector-reference-native"
        )
        expected = {
            "serial-label-control.kicad_sch": "a0ac8548431af625c5116c1d456e4f2c6cf1714e58cca84c6fe595165d87c561",
            "serial-label-fault.kicad_sch": "2006adbfa6c6f1c99e88e3320a1ed7230f01a02f5e143c16a946abaa34f9db20",
        }
        for name, sha256 in expected.items():
            with self.subTest(fixture=name):
                source = fixture_root / name
                text = source.read_text(encoding="utf-8")
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), sha256)
                self.assertIn("NOT FOR MANUFACTURE - tooling fixture", text)
                self.assertIn('"UART.0.TX"', text)
                self.assertIn('"UART.0.RX"', text)
                self.assertIn('"B2"', text)
                self.assertIn('"ADBUS1"', text)
                self.assertIn('(property "Reference" "U2"', text)
                self.assertNotIn('(property "Reference" "J1"', text)


if __name__ == "__main__":
    unittest.main()
