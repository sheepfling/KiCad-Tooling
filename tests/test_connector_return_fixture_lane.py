"""Synthetic orchestration checks for the pinned connector-return native lane."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kicad_tooling.ci_hosted import HostedLog, connector_return_lint_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence, ComponentContract, NetlistContract


class ConnectorReturnFixtureLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="connector-return-lane-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.image = "fixture.invalid/kicad@sha256:" + "a" * 64
        self.config = SimpleNamespace(
            image=self.image,
            kicad_version="10.0.0",
        )
        self.observed = {
            "fault": NetlistContract(
                components={},
                nets={
                    "GND1": ("J1.1", "J1.2"),
                    "GND2": ("J2.1", "J2.2"),
                },
                component_symbols={"J1": "Synthetic:Port6", "J2": "Synthetic:Port6"},
                component_pin_numbers={
                    f"J{reference}": tuple(str(pin) for pin in range(1, 7)) for reference in (1, 2)
                },
                pin_functions={
                    f"J{reference}.{pin}": "GND" for reference in (1, 2) for pin in (1, 2)
                },
            ),
            "control": NetlistContract(
                components={},
                nets={"GND": ("J1.1", "J1.2", "J2.1", "J2.2")},
                component_symbols={"J1": "Synthetic:Port6", "J2": "Synthetic:Port6"},
                component_pin_numbers={
                    f"J{reference}": tuple(str(pin) for pin in range(1, 7)) for reference in (1, 2)
                },
                pin_functions={
                    f"J{reference}.{pin}": "GND" for reference in (1, 2) for pin in (1, 2)
                },
            ),
            "cross-symbol-fault": NetlistContract(
                components={},
                nets={
                    "USB_RETURN": ("J1.4",),
                    "USB_SUPPLY": ("J1.1",),
                    "SERIAL_RETURN": ("J2.7",),
                    "SERIAL_SUPPLY": ("J2.9",),
                    "CHASSIS": ("J3.1",),
                },
                component_symbols={
                    "J1": "Synthetic:UsbPort",
                    "J2": "Synthetic:SerialPort",
                    "J3": "Synthetic:ShieldPort",
                },
                pin_functions={
                    "J1.4": "GND",
                    "J1.1": "PWR",
                    "J2.7": "RTN",
                    "J2.9": "PWR",
                    "J3.1": "SHIELD",
                },
            ),
            "cross-symbol-control": NetlistContract(
                components={},
                nets={
                    "COMMON_RETURN": ("J1.4", "J2.7"),
                    "COMMON_SUPPLY": ("J1.1", "J2.9"),
                    "CHASSIS": ("J3.1",),
                },
                component_symbols={
                    "J1": "Synthetic:UsbPort",
                    "J2": "Synthetic:SerialPort",
                    "J3": "Synthetic:ShieldPort",
                },
                pin_functions={
                    "J1.4": "GND",
                    "J1.1": "PWR",
                    "J2.7": "RTN",
                    "J2.9": "PWR",
                    "J3.1": "SHIELD",
                },
            ),
            "cross-symbol-open": NetlistContract(
                components={},
                nets={
                    "COMMON_RETURN": ("J1.4",),
                    "COMMON_SUPPLY": ("J1.1", "J2.9"),
                    "CHASSIS": ("J3.1",),
                },
                component_symbols={
                    "J1": "Synthetic:UsbPort",
                    "J2": "Synthetic:SerialPort",
                    "J3": "Synthetic:ShieldPort",
                },
                pin_functions={
                    "J1.4": "GND",
                    "J1.1": "PWR",
                    "J2.7": "RTN",
                    "J2.9": "PWR",
                    "J3.1": "SHIELD",
                },
            ),
            "mapped-supply-fault": NetlistContract(
                components={},
                nets={
                    "COMMON_RETURN": ("J1.4", "J2.7"),
                    "SUPPLY_ALPHA": ("J1.1",),
                    "SUPPLY_BETA": ("J2.9",),
                    "CHASSIS": ("J3.1",),
                },
                component_symbols={
                    "J1": "Synthetic:UsbPort",
                    "J2": "Synthetic:SerialPort",
                    "J3": "Synthetic:ShieldPort",
                },
                component_pin_numbers={"J1": ("1", "4"), "J2": ("7", "9"), "J3": ("1",)},
                pin_functions={
                    "J1.4": "GND",
                    "J1.1": "Pin_1",
                    "J2.7": "RTN",
                    "J2.9": "Pin_9",
                    "J3.1": "SHIELD",
                },
            ),
            "mapped-supply-control": NetlistContract(
                components={},
                nets={
                    "COMMON_RETURN": ("J1.4", "J2.7"),
                    "COMMON_SUPPLY": ("J1.1", "J2.9"),
                    "CHASSIS": ("J3.1",),
                },
                component_symbols={
                    "J1": "Synthetic:UsbPort",
                    "J2": "Synthetic:SerialPort",
                    "J3": "Synthetic:ShieldPort",
                },
                component_pin_numbers={"J1": ("1", "4"), "J2": ("7", "9"), "J3": ("1",)},
                pin_functions={
                    "J1.4": "GND",
                    "J1.1": "Pin_1",
                    "J2.7": "RTN",
                    "J2.9": "Pin_9",
                    "J3.1": "SHIELD",
                },
            ),
            "channel-power-fault": NetlistContract(
                components={},
                nets={"CH2_VDD": ("J1.3",), "CH3_VDD": ("J2.3",)},
                component_symbols={"J1": "Lint:Port6", "J2": "Lint:Port6"},
                component_pin_numbers={
                    reference: tuple(str(pin) for pin in range(1, 7)) for reference in ("J1", "J2")
                },
                pin_functions={"J1.3": "VDD", "J2.3": "VDD"},
            ),
            "channel-power-control": NetlistContract(
                components={},
                nets={"CH2_VDD": ("J1.3", "J2.3")},
                component_symbols={"J1": "Lint:Port6", "J2": "Lint:Port6"},
                component_pin_numbers={
                    reference: tuple(str(pin) for pin in range(1, 7)) for reference in ("J1", "J2")
                },
                pin_functions={"J1.3": "VDD", "J2.3": "VDD"},
            ),
            "peer-power-fault": NetlistContract(
                components={
                    f"J{reference}": ComponentContract(value="Synthetic power port", footprint="")
                    for reference in range(1, 4)
                },
                nets={
                    "+5V_1": ("J1.1",),
                    "5V-2": ("J2.1",),
                    "GND": ("J1.2", "J2.2", "J3.2"),
                },
                component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
                component_symbols={
                    f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)
                },
                pin_functions={
                    **{f"J{reference}.1": "1" for reference in range(1, 4)},
                    **{f"J{reference}.2": "GND" for reference in range(1, 4)},
                },
            ),
            "peer-power-control": NetlistContract(
                components={
                    f"J{reference}": ComponentContract(value="Synthetic power port", footprint="")
                    for reference in range(1, 4)
                },
                nets={
                    "+5V": ("J1.1", "J2.1", "J3.1"),
                    "GND": ("J1.2", "J2.2", "J3.2"),
                },
                component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
                component_symbols={
                    f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)
                },
                pin_functions={
                    **{f"J{reference}.1": "1" for reference in range(1, 4)},
                    **{f"J{reference}.2": "GND" for reference in range(1, 4)},
                },
            ),
            "peer-pin-outlier-fault": NetlistContract(
                components={
                    f"J{reference}": ComponentContract(value="Synthetic peer port", footprint="")
                    for reference in range(1, 4)
                },
                nets={
                    "+5V": ("J1.1", "J2.1"),
                    "GND": ("J1.2", "J2.2", "J3.2"),
                },
                component_symbols={
                    f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)
                },
                component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
                pin_functions={
                    **{f"J{reference}.2": "GND" for reference in range(1, 4)},
                },
            ),
            "peer-pin-outlier-control": NetlistContract(
                components={
                    f"J{reference}": ComponentContract(value="Synthetic peer port", footprint="")
                    for reference in range(1, 4)
                },
                nets={
                    "+5V": ("J1.1", "J2.1", "J3.1"),
                    "GND": ("J1.2", "J2.2", "J3.2"),
                },
                component_symbols={
                    f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)
                },
                component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
                pin_functions={
                    **{f"J{reference}.2": "GND" for reference in range(1, 4)},
                },
            ),
            "peer-pin-minority-fault": NetlistContract(
                components={},
                nets={
                    "+5V": ("J1.1", "J2.1"),
                    "+3V3": ("J3.1",),
                    "GND": ("J1.2", "J2.2", "J3.2"),
                },
                component_symbols={
                    f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)
                },
                component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
                pin_functions={f"J{reference}.2": "GND" for reference in range(1, 4)},
            ),
            "peer-pin-divergence-fault": NetlistContract(
                components={},
                nets={
                    "+5V": ("J1.1",),
                    "+3V3": ("J2.1",),
                    "+12V": ("J3.1",),
                    "GND": ("J1.2", "J2.2", "J3.2"),
                },
                component_symbols={
                    f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)
                },
                component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
                pin_functions={f"J{reference}.2": "GND" for reference in range(1, 4)},
            ),
            "generic-placeholder-divergence-fault": NetlistContract(
                components={},
                nets={
                    "+5V": ("J1.1",),
                    "+3V3": ("J2.1",),
                    "+12V": ("J3.1",),
                    "GND": ("J1.2", "J2.2", "J3.2"),
                },
                component_symbols={
                    f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)
                },
                component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
                pin_functions={
                    **{f"J{reference}.1": "Pin_1" for reference in range(1, 4)},
                    **{f"J{reference}.2": "GND" for reference in range(1, 4)},
                },
            ),
            "peer-scope-split-return-fault": NetlistContract(
                components={},
                nets={
                    "+5V": ("J1.1",),
                    "+3V3": ("J2.1",),
                    "+12V": ("J3.1",),
                    "RETURN_A": ("J1.2",),
                    "RETURN_B": ("J2.2",),
                    "RETURN_C": ("J3.2",),
                },
                component_symbols={
                    f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)
                },
                component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
                pin_functions={
                    **{f"J{reference}.1": "Pin_1" for reference in range(1, 4)},
                    **{f"J{reference}.2": "GND" for reference in range(1, 4)},
                },
            ),
            "generic-placeholder-control": NetlistContract(
                components={},
                nets={
                    "+5V": ("J1.1", "J2.1", "J3.1"),
                    "GND": ("J1.2", "J2.2", "J3.2"),
                },
                component_symbols={
                    f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)
                },
                component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
                pin_functions={
                    **{f"J{reference}.1": "Pin_1" for reference in range(1, 4)},
                    **{f"J{reference}.2": "GND" for reference in range(1, 4)},
                },
            ),
            "two-peer-open-fault": NetlistContract(
                components={},
                nets={"+5V": ("J1.1",), "GND": ("J1.2", "J2.2")},
                component_symbols={"J1": "Lint:PeerPowerPort", "J2": "Lint:PeerPowerPort"},
                component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
                pin_functions={"J1.2": "GND", "J2.2": "GND"},
            ),
            "two-peer-no-connect-fault": NetlistContract(
                components={},
                nets={"+5V": ("J1.1",), "GND": ("J1.2", "J2.2")},
                unconnected_nets={"unconnected": ("J2.1",)},
                component_symbols={"J1": "Lint:PeerPowerPort", "J2": "Lint:PeerPowerPort"},
                component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
                pin_functions={"J1.2": "GND", "J2.2": "GND"},
            ),
            "two-peer-common-control": NetlistContract(
                components={},
                nets={"+5V": ("J1.1", "J2.1"), "GND": ("J1.2", "J2.2")},
                component_symbols={"J1": "Lint:PeerPowerPort", "J2": "Lint:PeerPowerPort"},
                component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
                pin_functions={"J1.2": "GND", "J2.2": "GND"},
            ),
            "single-offboard-port-control": NetlistContract(
                components={},
                nets={"+5V": ("J1.1",), "GND": ("J1.2",)},
                component_symbols={"J1": "Lint:PeerPowerPort"},
                component_pin_numbers={"J1": ("1", "2")},
                pin_functions={"J1.2": "GND"},
            ),
            "four-db9-fault": NetlistContract(
                components={
                    f"J{reference}": ComponentContract(
                        value="Synthetic DB9", footprint="Synthetic:DB9"
                    )
                    for reference in range(1, 5)
                },
                nets={
                    **{
                        f"0V PWM {reference}": (f"J{reference}.7", f"J{reference}.9")
                        for reference in range(1, 5)
                    },
                    **{
                        f"SIGNAL{pin}": tuple(f"J{reference}.{pin}" for reference in range(1, 5))
                        for pin in (1, 2, 3, 4, 5, 6, 8)
                    },
                },
                component_symbols={f"J{reference}": "Lint:DB9" for reference in range(1, 5)},
                component_pin_numbers={
                    f"J{reference}": tuple(str(pin) for pin in range(1, 10))
                    for reference in range(1, 5)
                },
                pin_functions={
                    f"J{reference}.{pin}": "GND" if pin in {7, 9} else f"SIGNAL{pin}"
                    for reference in range(1, 5)
                    for pin in range(1, 10)
                },
            ),
            "four-db9-neutral-fault": NetlistContract(
                components={},
                nets={
                    **{
                        f"NET_{chr(64 + reference)}": (
                            f"J{reference}.7",
                            f"J{reference}.9",
                        )
                        for reference in range(1, 5)
                    },
                    **{
                        f"SIGNAL{pin}": tuple(f"J{reference}.{pin}" for reference in range(1, 5))
                        for pin in (1, 2, 3, 4, 5, 6, 8)
                    },
                },
                component_symbols={f"J{reference}": "Lint:DB9" for reference in range(1, 5)},
                component_pin_numbers={
                    f"J{reference}": tuple(str(pin) for pin in range(1, 10))
                    for reference in range(1, 5)
                },
                pin_functions={
                    f"J{reference}.{pin}": str(pin) if pin in {7, 9} else f"SIGNAL{pin}"
                    for reference in range(1, 5)
                    for pin in range(1, 10)
                },
            ),
            "four-db9-neutral-control": NetlistContract(
                components={},
                nets={
                    "NET_COMMON": tuple(
                        f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)
                    ),
                    **{
                        f"SIGNAL{pin}": tuple(f"J{reference}.{pin}" for reference in range(1, 5))
                        for pin in (1, 2, 3, 4, 5, 6, 8)
                    },
                },
                component_symbols={f"J{reference}": "Lint:DB9" for reference in range(1, 5)},
                component_pin_numbers={
                    f"J{reference}": tuple(str(pin) for pin in range(1, 10))
                    for reference in range(1, 5)
                },
                pin_functions={
                    f"J{reference}.{pin}": str(pin) if pin in {7, 9} else f"SIGNAL{pin}"
                    for reference in range(1, 5)
                    for pin in range(1, 10)
                },
            ),
            "four-db9-control": NetlistContract(
                components={
                    f"J{reference}": ComponentContract(
                        value="Synthetic DB9", footprint="Synthetic:DB9"
                    )
                    for reference in range(1, 5)
                },
                nets={
                    "0V PWM": tuple(
                        f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)
                    ),
                    **{
                        f"SIGNAL{pin}": tuple(f"J{reference}.{pin}" for reference in range(1, 5))
                        for pin in (1, 2, 3, 4, 5, 6, 8)
                    },
                },
                component_symbols={f"J{reference}": "Lint:DB9" for reference in range(1, 5)},
                component_pin_numbers={
                    f"J{reference}": tuple(str(pin) for pin in range(1, 10))
                    for reference in range(1, 5)
                },
                pin_functions={
                    f"J{reference}.{pin}": "GND" if pin in {7, 9} else f"SIGNAL{pin}"
                    for reference in range(1, 5)
                    for pin in range(1, 10)
                },
            ),
            "unconnected-generic-power-input-fault": NetlistContract(
                components={},
                nets={"GND": ("J1.2", "J2.2")},
                component_symbols={
                    "J1": "Lint:GenericPowerInputPort",
                    "J2": "Lint:GenericPowerInputPort",
                },
                component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
                pin_functions={
                    "J1.1": "1",
                    "J1.2": "GND",
                    "J2.1": "1",
                    "J2.2": "GND",
                },
                pin_electrical_types={
                    "J1.1": "power_in",
                    "J1.2": "passive",
                    "J2.1": "power_in",
                    "J2.2": "passive",
                },
            ),
            "unconnected-generic-power-input-control": NetlistContract(
                components={},
                nets={"+5V": ("J1.1", "J2.1"), "GND": ("J1.2", "J2.2")},
                component_symbols={
                    "J1": "Lint:GenericPowerInputPort",
                    "J2": "Lint:GenericPowerInputPort",
                },
                component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
                pin_functions={
                    "J1.1": "1",
                    "J1.2": "GND",
                    "J2.1": "1",
                    "J2.2": "GND",
                },
                pin_electrical_types={
                    "J1.1": "power_in",
                    "J1.2": "passive",
                    "J2.1": "power_in",
                    "J2.2": "passive",
                },
            ),
        }

    def test_pinned_native_export_checks_fault_control_hashes_and_mount_scope(self) -> None:
        def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
            self.assertEqual(root, self.root.resolve())
            self.assertEqual(timeout, 600)
            self.assertIn("--network", argv)
            self.assertEqual(argv[argv.index("--network") + 1], "none")
            self.assertIn("--read-only", argv)
            self.assertEqual(argv[argv.index("--entrypoint") + 1], "/bin/sh")
            self.assertEqual(argv[argv.index("--platform") + 1], "linux/amd64")
            self.assertIn(self.image, argv)
            script = argv[-1]
            self.assertIn('test "$actual" = "10.0.0"', script)
            self.assertIn("kicad-cli sch export netlist", script)

            mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
            self.assertEqual(len(mounts), 2)
            source_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
            output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
            source_directory = Path(source_mount.removesuffix(":/fixtures:ro"))
            output_directory = Path(output_mount.removesuffix(":/output:rw"))
            cases = tuple(sorted(self.observed))
            self.assertEqual(
                {item.name for item in source_directory.iterdir()},
                {f"{case}.kicad_sch" for case in cases},
            )
            for case in cases:
                for run in ("first", "repeat"):
                    (output_directory / f"{case}.{run}.netlist.xml").write_text(
                        f"synthetic {case} netlist with export timestamp {run}\n",
                        encoding="utf-8",
                    )
            return CommandEvidence(
                argv=argv,
                started_utc="2026-09-29T00:00:00+00:00",
                returncode=0,
                stdout="kicad_version=10.0.0\n",
            )

        def fake_read_netlist(path: Path) -> NetlistContract:
            case = path.name.split(".", 1)[0]
            return self.observed[case]

        log = HostedLog(self.root, "connector-return")
        with (
            patch("kicad_tooling.hwrepo.electrical.selected_config", return_value=self.config),
            patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_run_command),
            patch("kicad_tooling.validate.read_netlist", side_effect=fake_read_netlist),
        ):
            connector_return_lint_fixture_lane(
                self.root,
                project="synthetic-project",
                image=self.image,
                log=log,
            )

        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("connector-return-fixture/")
        }
        fault = results["connector-return-fixture/fault"]
        control = results["connector-return-fixture/control"]
        self.assertEqual(fault["status"], "PASS")
        self.assertEqual(fault["lint_status"], "REVIEW")
        self.assertEqual(
            set(fault["findings"].split(",")),
            {"connector.repeated_pin_function", "net.numbered_returns"},
        )
        self.assertEqual(control["status"], "PASS")
        self.assertEqual(control["lint_status"], "PASS")
        self.assertEqual(control["findings"], "none")
        cross_fault = results["connector-return-fixture/cross-symbol-fault"]
        self.assertEqual(cross_fault["lint_status"], "REVIEW")
        self.assertEqual(
            set(cross_fault["subjects"].split(";")),
            {
                "multiple connector symbols: ground/return",
                "multiple connector symbols: PWR",
            },
        )
        self.assertIn("J3.1=SHIELD", cross_fault["pin_functions"])
        cross_control = results["connector-return-fixture/cross-symbol-control"]
        self.assertEqual(cross_control["lint_status"], "PASS")
        self.assertEqual(cross_control["findings"], "none")
        cross_open = results["connector-return-fixture/cross-symbol-open"]
        self.assertEqual(cross_open["lint_status"], "REVIEW")
        self.assertEqual(cross_open["subjects"], "multiple connector symbols: ground/return")
        channel_fault = results["connector-return-fixture/channel-power-fault"]
        channel_control = results["connector-return-fixture/channel-power-control"]
        self.assertEqual(channel_fault["lint_status"], "REVIEW")
        self.assertIn("net.numbered_power_rails", channel_fault["findings"].split(","))
        self.assertIn("CH VDD", channel_fault["subjects"].split(";"))
        self.assertEqual(channel_control["lint_status"], "PASS")
        self.assertEqual(channel_control["findings"], "none")
        peer_power_fault = results["connector-return-fixture/peer-power-fault"]
        peer_power_control = results["connector-return-fixture/peer-power-control"]
        self.assertEqual(peer_power_fault["lint_status"], "REVIEW")
        self.assertEqual(
            set(peer_power_fault["findings"].split(",")),
            {"connector.repeated_pin_function", "net.numbered_power_rails"},
        )
        self.assertIn("J3.1=1", peer_power_fault["pin_functions"])
        self.assertEqual(peer_power_control["lint_status"], "PASS")
        self.assertEqual(peer_power_control["findings"], "none")
        peer_pin_fault = results["connector-return-fixture/peer-pin-outlier-fault"]
        peer_pin_control = results["connector-return-fixture/peer-pin-outlier-control"]
        self.assertEqual(peer_pin_fault["lint_status"], "REVIEW")
        self.assertEqual(peer_pin_fault["findings"], "connector.peer_pin_assignment_outlier")
        self.assertEqual(peer_pin_fault["subjects"], "Lint:PeerPowerPort pin 1")
        self.assertEqual(peer_pin_fault["pin_functions"], "J1.2=GND;J2.2=GND;J3.2=GND")
        self.assertEqual(peer_pin_control["lint_status"], "PASS")
        self.assertEqual(peer_pin_control["findings"], "none")
        two_peer_fault = results["connector-return-fixture/two-peer-open-fault"]
        two_peer_control = results["connector-return-fixture/two-peer-common-control"]
        self.assertEqual(two_peer_fault["lint_status"], "REVIEW")
        self.assertEqual(two_peer_fault["findings"], "connector.peer_pin_assignment_outlier")
        self.assertEqual(two_peer_fault["subjects"], "Lint:PeerPowerPort pin 1")
        self.assertEqual(two_peer_fault["pin_functions"], "J1.2=GND;J2.2=GND")
        self.assertEqual(two_peer_control["lint_status"], "PASS")
        self.assertEqual(two_peer_control["findings"], "none")
        no_connect = results["connector-return-fixture/two-peer-no-connect-fault"]
        self.assertEqual(no_connect["lint_status"], "REVIEW")
        self.assertEqual(no_connect["findings"], "connector.peer_pin_assignment_outlier")
        self.assertEqual(no_connect["repeatable"], "true")
        offboard = results["connector-return-fixture/single-offboard-port-control"]
        self.assertEqual(offboard["lint_status"], "PASS")
        self.assertEqual(offboard["findings"], "none")
        offboard_unreviewed = results["connector-return-fixture/offboard-inventory-unreviewed"]
        self.assertEqual(offboard_unreviewed["coverage_status"], "UNDECLARED")
        self.assertEqual(offboard_unreviewed["lint_status"], "REVIEW")
        self.assertEqual(offboard_unreviewed["findings"], "none")
        offboard_reviewed = results["connector-return-fixture/offboard-interface-control"]
        self.assertEqual(offboard_reviewed["coverage_status"], "COMPLETE")
        self.assertEqual(offboard_reviewed["lint_status"], "PASS")
        self.assertEqual(offboard_reviewed["findings"], "none")
        peer_pin_minority = results["connector-return-fixture/peer-pin-minority-fault"]
        self.assertEqual(peer_pin_minority["lint_status"], "REVIEW")
        self.assertEqual(peer_pin_minority["findings"], "connector.peer_pin_assignment_outlier")
        self.assertEqual(peer_pin_minority["subjects"], "Lint:PeerPowerPort pin 1")
        peer_pin_divergence = results["connector-return-fixture/peer-pin-divergence-fault"]
        self.assertEqual(peer_pin_divergence["lint_status"], "REVIEW")
        self.assertEqual(
            peer_pin_divergence["findings"], "connector.peer_pin_assignment_divergence"
        )
        self.assertEqual(peer_pin_divergence["subjects"], "Lint:PeerPowerPort pin 1")
        db9_fault = results["connector-return-fixture/four-db9-fault"]
        db9_control = results["connector-return-fixture/four-db9-control"]
        self.assertEqual(db9_fault["lint_status"], "REVIEW")
        self.assertEqual(
            set(db9_fault["findings"].split(",")),
            {"connector.repeated_pin_function", "net.numbered_returns"},
        )
        self.assertEqual(db9_control["lint_status"], "PASS")
        self.assertEqual(db9_control["findings"], "none")
        grounding_expectations = {
            "ground-contract-common-fault": "FAIL",
            "ground-contract-common-control": "PASS",
            "ground-contract-isolated-fault": "PASS",
            "ground-contract-isolated-control": "FAIL",
        }
        for case, expected_contract_status in grounding_expectations.items():
            item = results[f"connector-return-fixture/{case}"]
            self.assertEqual(item["status"], "PASS")
            self.assertEqual(item["contract_status"], expected_contract_status)
            self.assertEqual(item["repeatable"], "true")
            self.assertRegex(item["grounding_contract_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            results["connector-return-fixture/ground-contract-common-fault"]["checks"],
            "grounding/0V PWM=FAIL;grounding/component-coverage=PASS;"
            "grounding/return-net-review=FAIL",
        )
        self.assertEqual(
            results["connector-return-fixture/ground-contract-common-control"]["checks"],
            "grounding/0V PWM=PASS;grounding/component-coverage=PASS",
        )
        pin_connectivity_expectations = {
            "common-fault": "FAIL",
            "common-control": "PASS",
            "isolated-fault": "PASS",
            "isolated-control": "FAIL",
            "peer-common-open-fault": "FAIL",
            "peer-common-control": "PASS",
            "peer-independent-control": "PASS",
            "peer-independent-common-net-mismatch": "FAIL",
        }
        for case, expected_contract_status in pin_connectivity_expectations.items():
            item = results[f"connector-return-fixture/pin-connectivity-contract-{case}"]
            self.assertEqual(item["status"], "PASS")
            self.assertEqual(item["contract_status"], expected_contract_status)
            self.assertEqual(item["repeatable"], "true")
            self.assertRegex(item["pin_connectivity_contract_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            results["connector-return-fixture/pin-connectivity-contract-common-fault"]["checks"],
            "pin-connectivity/db9-common-return=FAIL",
        )
        self.assertEqual(
            results["connector-return-fixture/pin-connectivity-contract-common-control"]["checks"],
            "pin-connectivity/db9-common-return=PASS",
        )
        self.assertEqual(
            results["connector-return-fixture/pin-connectivity-contract-isolated-fault"]["checks"],
            ";".join(
                f"pin-connectivity/db9-{reference}-isolated-return=PASS"
                for reference in range(1, 5)
            ),
        )
        self.assertEqual(
            results["connector-return-fixture/pin-connectivity-contract-isolated-control"][
                "checks"
            ],
            ";".join(
                f"pin-connectivity/db9-{reference}-isolated-return=FAIL"
                for reference in range(1, 5)
            ),
        )
        self.assertEqual(
            results["connector-return-fixture/pin-connectivity-contract-peer-common-open-fault"][
                "checks"
            ],
            "pin-connectivity/peer-common-power=FAIL",
        )
        self.assertEqual(
            results["connector-return-fixture/pin-connectivity-contract-peer-common-control"][
                "checks"
            ],
            "pin-connectivity/peer-common-power=PASS",
        )
        self.assertEqual(
            results["connector-return-fixture/pin-connectivity-contract-peer-independent-control"][
                "checks"
            ],
            "pin-connectivity/peer-independent-power-outputs=PASS;"
            "pin-connectivity/peer-j3-power-unused=PASS",
        )
        self.assertEqual(
            results[
                "connector-return-fixture/"
                "pin-connectivity-contract-peer-independent-common-net-mismatch"
            ]["checks"],
            "pin-connectivity/peer-independent-power-outputs=FAIL;"
            "pin-connectivity/peer-j3-power-unused=FAIL",
        )
        stale_pin = results[
            "connector-return-fixture/pin-connectivity-contract-stale-pin-reference"
        ]
        self.assertEqual(stale_pin["status"], "PASS")
        self.assertEqual(stale_pin["contract_status"], "FAIL")
        self.assertEqual(stale_pin["relationship"], "stale-symbol-pin")
        self.assertEqual(stale_pin["checks"], "pin-connectivity/stale-pin-reference=FAIL")
        self.assertIn(
            "unknown symbol pins=['J1.99']",
            json.loads(stale_pin["check_details"])["pin-connectivity/stale-pin-reference"],
        )
        self.assertEqual(stale_pin["repeatable"], "true")
        neutral_fault = results["connector-return-fixture/four-db9-neutral-fault"]
        neutral_control = results["connector-return-fixture/four-db9-neutral-control"]
        self.assertEqual(neutral_fault["lint_status"], "REVIEW")
        self.assertEqual(
            set(neutral_fault["findings"].split(",")),
            {"connector.repeated_pin_function", "connector.no_connected_return"},
        )
        self.assertEqual(
            set(neutral_fault["subjects"].split(";")),
            {
                "Lint:DB9: 7",
                "Lint:DB9: 9",
                *(f"J{reference}: no connected return" for reference in range(1, 5)),
            },
        )
        self.assertIn("J1.7=7", neutral_fault["pin_functions"])
        self.assertIn("J1.9=9", neutral_fault["pin_functions"])
        self.assertEqual(neutral_control["lint_status"], "REVIEW")
        self.assertEqual(
            set(neutral_control["findings"].split(",")),
            {"connector.no_connected_return"},
        )
        generic_power_fault = results[
            "connector-return-fixture/unconnected-generic-power-input-fault"
        ]
        generic_power_control = results[
            "connector-return-fixture/unconnected-generic-power-input-control"
        ]
        self.assertEqual(generic_power_fault["lint_status"], "REVIEW")
        self.assertEqual(
            set(generic_power_fault["findings"].split(",")),
            {"connector.unconnected_power_input"},
        )
        self.assertEqual(
            set(generic_power_fault["subjects"].split(";")),
            {
                "J1.1: generic native power-input pin is unassigned",
                "J2.1: generic native power-input pin is unassigned",
            },
        )
        self.assertEqual(generic_power_control["lint_status"], "PASS")
        self.assertEqual(generic_power_control["findings"], "none")
        self.assertNotEqual(fault["netlist_sha256"], fault["repeat_netlist_sha256"])
        self.assertNotEqual(control["netlist_sha256"], control["repeat_netlist_sha256"])
        self.assertEqual(
            fault["normalized_netlist_sha256"], fault["repeat_normalized_netlist_sha256"]
        )
        self.assertEqual(
            control["normalized_netlist_sha256"],
            control["repeat_normalized_netlist_sha256"],
        )
        self.assertRegex(fault["source_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(control["source_sha256"], r"^[0-9a-f]{64}$")
        for case in (
            "cross-symbol-fault",
            "cross-symbol-control",
            "cross-symbol-open",
            "mapped-supply-fault",
            "mapped-supply-control",
            "channel-power-fault",
            "channel-power-control",
            "peer-power-fault",
            "peer-power-control",
            "peer-pin-outlier-fault",
            "peer-pin-outlier-control",
            "two-peer-open-fault",
            "two-peer-no-connect-fault",
            "two-peer-common-control",
            "single-offboard-port-control",
            "peer-pin-minority-fault",
            "peer-pin-divergence-fault",
            "four-db9-fault",
            "four-db9-control",
            "four-db9-neutral-fault",
            "four-db9-neutral-control",
            "ground-contract-common-fault",
            "ground-contract-common-control",
            "ground-contract-isolated-fault",
            "ground-contract-isolated-control",
            "pin-connectivity-contract-common-fault",
            "pin-connectivity-contract-common-control",
            "pin-connectivity-contract-isolated-fault",
            "pin-connectivity-contract-isolated-control",
            "pin-connectivity-contract-peer-common-open-fault",
            "pin-connectivity-contract-peer-common-control",
            "pin-connectivity-contract-peer-independent-control",
            "pin-connectivity-contract-peer-independent-common-net-mismatch",
        ):
            item = results[f"connector-return-fixture/{case}"]
            self.assertEqual(item["status"], "PASS")
            self.assertEqual(
                item["normalized_netlist_sha256"], item["repeat_normalized_netlist_sha256"]
            )
            self.assertRegex(item["source_sha256"], r"^[0-9a-f]{64}$")
        mapped_supply_fault = results["connector-return-fixture/reviewed-supply-fault"]
        mapped_supply_control = results["connector-return-fixture/reviewed-supply-control"]
        mapped_supply_domain_control = results[
            "connector-return-fixture/reviewed-supply-domain-control"
        ]
        self.assertEqual(mapped_supply_fault["coverage_status"], "COMPLETE")
        self.assertEqual(mapped_supply_fault["lint_status"], "REVIEW")
        self.assertEqual(mapped_supply_fault["findings"], "connector.repeated_pin_function")
        self.assertEqual(mapped_supply_control["coverage_status"], "COMPLETE")
        self.assertEqual(mapped_supply_control["lint_status"], "PASS")
        self.assertEqual(mapped_supply_control["findings"], "none")
        self.assertEqual(mapped_supply_domain_control["coverage_status"], "COMPLETE")
        self.assertEqual(mapped_supply_domain_control["lint_status"], "PASS")
        self.assertEqual(mapped_supply_domain_control["findings"], "none")
        self.assertTrue((self.root / fault["command_receipt"]).is_file())
        export = results["connector-return-fixture/native-export"]
        self.assertEqual(export["status"], "PASS")
        self.assertEqual(export["kicad_version"], "10.0.0")


if __name__ == "__main__":
    unittest.main()
