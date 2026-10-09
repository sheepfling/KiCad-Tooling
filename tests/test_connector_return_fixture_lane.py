"""Synthetic orchestration checks for the pinned connector-return native lane."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted import HostedLog, connector_return_lint_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence, ComponentContract, NetlistContract


@pytest.fixture
def connector_return_fixture_lane_context(tmp_path: Path) -> SimpleNamespace:
    root = tmp_path
    image = "fixture.invalid/kicad@sha256:" + "a" * 64
    config = SimpleNamespace(
        image=image,
        kicad_version="10.0.0",
    )
    observed = {
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
            pin_functions={f"J{reference}.{pin}": "GND" for reference in (1, 2) for pin in (1, 2)},
        ),
        "control": NetlistContract(
            components={},
            nets={"GND": ("J1.1", "J1.2", "J2.1", "J2.2")},
            component_symbols={"J1": "Synthetic:Port6", "J2": "Synthetic:Port6"},
            component_pin_numbers={
                f"J{reference}": tuple(str(pin) for pin in range(1, 7)) for reference in (1, 2)
            },
            pin_functions={f"J{reference}.{pin}": "GND" for reference in (1, 2) for pin in (1, 2)},
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
            component_symbols={f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)},
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
            component_symbols={f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)},
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
            component_symbols={f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)},
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
            component_symbols={f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)},
            component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
            pin_functions={
                **{f"J{reference}.2": "GND" for reference in range(1, 4)},
            },
        ),
        "peer-pin-part-id-open-fault": NetlistContract(
            components={
                reference: ComponentContract(
                    value="Synthetic two-contact connector",
                    footprint="Synthetic:Port_2x1",
                    part_id="SYNTHETIC-CONNECTOR-2PIN-001",
                )
                for reference in ("J1", "J2")
            },
            nets={"SYNTHETIC_DATA": ("J1.1", "J2.1"), "SYNTHETIC_RETURN": ("J1.2",)},
            component_symbols={
                "J1": "Synthetic:GenericPort",
                "J2": "Synthetic:GenericPortAlias",
            },
            component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
            pin_functions={
                "J1.1": "Pin_1",
                "J1.2": "Pin_2",
                "J2.1": "Pin_1",
                "J2.2": "Pin_2",
            },
            pin_electrical_types={
                "J1.1": "passive",
                "J1.2": "passive",
                "J2.1": "passive",
                "J2.2": "passive",
            },
        ),
        "peer-pin-part-id-common-control": NetlistContract(
            components={
                reference: ComponentContract(
                    value="Synthetic two-contact connector",
                    footprint="Synthetic:Port_2x1",
                    part_id="SYNTHETIC-CONNECTOR-2PIN-001",
                )
                for reference in ("J1", "J2")
            },
            nets={
                "SYNTHETIC_NET_1": ("J1.1", "J2.1"),
                "SYNTHETIC_RETURN": ("J1.2", "J2.2"),
            },
            component_symbols={
                "J1": "Synthetic:GenericPort",
                "J2": "Synthetic:GenericPortAlias",
            },
            component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
            pin_functions={
                "J1.1": "Pin_1",
                "J1.2": "Pin_2",
                "J2.1": "Pin_1",
                "J2.2": "Pin_2",
            },
            pin_electrical_types={
                "J1.1": "passive",
                "J1.2": "passive",
                "J2.1": "passive",
                "J2.2": "passive",
            },
        ),
        "peer-pin-part-id-split-fault": NetlistContract(
            components={
                reference: ComponentContract(
                    value="Synthetic two-contact connector",
                    footprint="Synthetic:Port_2x1",
                    part_id="SYNTHETIC-CONNECTOR-2PIN-001",
                )
                for reference in ("J1", "J2")
            },
            nets={
                "SYNTHETIC_NET_1": ("J1.1", "J2.1"),
                "SYNTHETIC_NET_2": ("J1.2",),
                "SYNTHETIC_NET_3": ("J2.2",),
            },
            component_symbols={
                "J1": "Synthetic:GenericPort",
                "J2": "Synthetic:GenericPortAlias",
            },
            component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
            pin_functions={
                "J1.1": "Pin_1",
                "J1.2": "Pin_2",
                "J2.1": "Pin_1",
                "J2.2": "Pin_2",
            },
            pin_electrical_types={
                "J1.1": "passive",
                "J1.2": "passive",
                "J2.1": "passive",
                "J2.2": "passive",
            },
        ),
        "peer-pin-minority-fault": NetlistContract(
            components={},
            nets={
                "+5V": ("J1.1", "J2.1"),
                "+3V3": ("J3.1",),
                "GND": ("J1.2", "J2.2", "J3.2"),
            },
            component_symbols={f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)},
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
            component_symbols={f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)},
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
            component_symbols={f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)},
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
            component_symbols={f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)},
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
            component_symbols={f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)},
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
                f"J{reference}": ComponentContract(value="Synthetic DB9", footprint="Synthetic:DB9")
                for reference in range(1, 5)
            },
            nets={
                **{
                    f"RETURN_PORT_{reference}": (f"J{reference}.7", f"J{reference}.9")
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
                f"J{reference}": ComponentContract(value="Synthetic DB9", footprint="Synthetic:DB9")
                for reference in range(1, 5)
            },
            nets={
                "COMMON_RETURN": tuple(
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
    for case in (
        "unconnected-generic-component-power-input-fault",
        "unconnected-generic-component-power-input-control",
        "unconnected-generic-component-power-input-no-connect-fault",
        "unconnected-generic-component-power-input-dnp-control",
    ):
        connected = case.endswith("-control") and not case.endswith("-dnp-control")
        observed[case] = NetlistContract(
            components={
                "U1": ComponentContract(
                    value="Synthetic generic power-input component",
                    footprint="Synthetic:Component",
                )
            },
            nets={
                **({"POWER_INPUT_TEST": ("U1.1",)} if connected else {}),
                "SIGNAL": ("U1.2",),
            },
            dnp_components=("U1",) if case.endswith("-dnp-control") else (),
            component_symbols={"U1": "Lint:GenericPowerInputComponent"},
            component_pin_numbers={"U1": ("1", "2")},
            pin_functions={"U1.1": "1", "U1.2": "2"},
            pin_electrical_types={"U1.1": "power_in", "U1.2": "passive"},
        )

    return SimpleNamespace(root=root, image=image, config=config, observed=observed)


def test_pinned_native_export_checks_fault_control_hashes_and_mount_scope(
    connector_return_fixture_lane_context: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = connector_return_fixture_lane_context.root
    image = connector_return_fixture_lane_context.image
    config = connector_return_fixture_lane_context.config
    observed = connector_return_fixture_lane_context.observed

    def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert root == connector_return_fixture_lane_context.root.resolve()
        assert timeout == 600
        assert "--network" in argv
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert argv[argv.index("--entrypoint") + 1] == "/bin/sh"
        assert argv[argv.index("--platform") + 1] == "linux/amd64"
        assert image in argv
        script = argv[-1]
        assert 'test "$actual" = "10.0.0"' in script
        assert "kicad-cli sch export netlist" in script

        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        assert len(mounts) == 2
        source_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
        output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
        source_directory = Path(source_mount.removesuffix(":/fixtures:ro"))
        output_directory = Path(output_mount.removesuffix(":/output:rw"))
        cases = tuple(sorted(observed))
        assert {item.name for item in source_directory.iterdir()} == {
            f"{case}.kicad_sch" for case in cases
        }
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
        return observed[case]

    log = HostedLog(root, "connector-return")
    monkeypatch.setattr("kicad_tooling.hwrepo.electrical.selected_config", lambda *_args: config)
    monkeypatch.setattr("kicad_tooling.hwrepo.contract_coach.run_command", fake_run_command)
    monkeypatch.setattr("kicad_tooling.validate.read_netlist", fake_read_netlist)
    connector_return_lint_fixture_lane(
        root,
        project="synthetic-project",
        image=image,
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
    assert fault["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert set(fault["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "net.numbered_returns",
    }
    assert control["status"] == "PASS"
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    cross_fault = results["connector-return-fixture/cross-symbol-fault"]
    assert cross_fault["lint_status"] == "REVIEW"
    assert set(cross_fault["subjects"].split(";")) == {
        "multiple connector symbols: ground/return",
        "multiple connector symbols: PWR",
    }
    assert "J3.1=SHIELD" in cross_fault["pin_functions"]
    cross_control = results["connector-return-fixture/cross-symbol-control"]
    assert cross_control["lint_status"] == "PASS"
    assert cross_control["findings"] == "none"
    cross_open = results["connector-return-fixture/cross-symbol-open"]
    assert cross_open["lint_status"] == "REVIEW"
    assert cross_open["subjects"] == "multiple connector symbols: ground/return"
    channel_fault = results["connector-return-fixture/channel-power-fault"]
    channel_control = results["connector-return-fixture/channel-power-control"]
    assert channel_fault["lint_status"] == "REVIEW"
    assert "net.numbered_power_rails" in channel_fault["findings"].split(",")
    assert "CH VDD" in channel_fault["subjects"].split(";")
    assert channel_control["lint_status"] == "PASS"
    assert channel_control["findings"] == "none"
    peer_power_fault = results["connector-return-fixture/peer-power-fault"]
    peer_power_control = results["connector-return-fixture/peer-power-control"]
    assert peer_power_fault["lint_status"] == "REVIEW"
    assert set(peer_power_fault["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "net.numbered_power_rails",
    }
    assert "J3.1=1" in peer_power_fault["pin_functions"]
    assert peer_power_control["lint_status"] == "PASS"
    assert peer_power_control["findings"] == "none"
    peer_pin_fault = results["connector-return-fixture/peer-pin-outlier-fault"]
    peer_pin_control = results["connector-return-fixture/peer-pin-outlier-control"]
    assert peer_pin_fault["lint_status"] == "REVIEW"
    assert peer_pin_fault["findings"] == "connector.peer_pin_assignment_outlier"
    assert peer_pin_fault["subjects"] == "Lint:PeerPowerPort pin 1"
    assert peer_pin_fault["pin_functions"] == "J1.2=GND;J2.2=GND;J3.2=GND"
    assert peer_pin_control["lint_status"] == "PASS"
    assert peer_pin_control["findings"] == "none"
    part_id_fault = results["connector-return-fixture/peer-pin-part-id-open-fault"]
    part_id_control = results["connector-return-fixture/peer-pin-part-id-common-control"]
    assert part_id_fault["lint_status"] == "REVIEW"
    assert part_id_fault["findings"] == "connector.peer_pin_assignment_outlier"
    assert part_id_fault["subjects"] == "PART_ID SYNTHETIC-CONNECTOR-2PIN-001 pin 2"
    assert part_id_control["lint_status"] == "PASS"
    assert part_id_control["findings"] == "none"
    part_id_split = results["connector-return-fixture/peer-pin-part-id-split-fault"]
    assert part_id_split["lint_status"] == "REVIEW"
    assert part_id_split["findings"] == "connector.peer_pin_assignment_divergence"
    assert part_id_split["subjects"] == "PART_ID SYNTHETIC-CONNECTOR-2PIN-001 pin 2"
    for (
        case,
        expected_open,
        expected_different,
        expected_common,
        expected_outliers,
        expected_divergences,
    ) in (
        ("peer-pin-part-id-open-fault", 1, 1, 1, 1, 0),
        ("peer-pin-part-id-common-control", 0, 0, 2, 0, 0),
        ("peer-pin-part-id-split-fault", 0, 1, 1, 0, 1),
    ):
        item = results[f"connector-return-fixture/{case}"]
        coverage = json.loads(item["connector_peer_pin_coverage"])
        aliases = coverage["part_id_alias_coverage"]
        assert coverage["status"] == "NO_EXACT_SYMBOL_PEERS"
        assert coverage["netlist_sha256"] == item["netlist_sha256"]
        assert aliases["status"] == "EVALUATED"
        assert aliases["candidate_group_count"] == 1
        assert aliases["eligible_peer_group_count"] == 1
        assert aliases["compared_pin_group_count"] == 2
        assert aliases["common_assignment_pin_group_count"] == expected_common
        assert aliases["open_assignment_pin_group_count"] == expected_open
        assert aliases["outlier_finding_count"] == expected_outliers
        assert aliases["different_assignment_pin_group_count"] == expected_different
        assert aliases["divergence_finding_count"] == expected_divergences
    two_peer_fault = results["connector-return-fixture/two-peer-open-fault"]
    two_peer_control = results["connector-return-fixture/two-peer-common-control"]
    assert two_peer_fault["lint_status"] == "REVIEW"
    assert two_peer_fault["findings"] == "connector.peer_pin_assignment_outlier"
    assert two_peer_fault["subjects"] == "Lint:PeerPowerPort pin 1"
    assert two_peer_fault["pin_functions"] == "J1.2=GND;J2.2=GND"
    assert two_peer_control["lint_status"] == "PASS"
    assert two_peer_control["findings"] == "none"
    no_connect = results["connector-return-fixture/two-peer-no-connect-fault"]
    assert no_connect["lint_status"] == "REVIEW"
    assert no_connect["findings"] == "connector.peer_pin_assignment_outlier"
    assert no_connect["repeatable"] == "true"
    offboard = results["connector-return-fixture/single-offboard-port-control"]
    assert offboard["lint_status"] == "PASS"
    assert offboard["findings"] == "none"
    offboard_unreviewed = results["connector-return-fixture/offboard-inventory-unreviewed"]
    assert offboard_unreviewed["coverage_status"] == "UNDECLARED"
    assert offboard_unreviewed["lint_status"] == "REVIEW"
    assert offboard_unreviewed["findings"] == "none"
    offboard_reviewed = results["connector-return-fixture/offboard-interface-control"]
    assert offboard_reviewed["coverage_status"] == "COMPLETE"
    assert offboard_reviewed["lint_status"] == "PASS"
    assert offboard_reviewed["findings"] == "none"
    peer_pin_minority = results["connector-return-fixture/peer-pin-minority-fault"]
    assert peer_pin_minority["lint_status"] == "REVIEW"
    assert peer_pin_minority["findings"] == "connector.peer_pin_assignment_outlier"
    assert peer_pin_minority["subjects"] == "Lint:PeerPowerPort pin 1"
    peer_pin_divergence = results["connector-return-fixture/peer-pin-divergence-fault"]
    assert peer_pin_divergence["lint_status"] == "REVIEW"
    assert peer_pin_divergence["findings"] == "connector.peer_pin_assignment_divergence"
    assert peer_pin_divergence["subjects"] == "Lint:PeerPowerPort pin 1"
    db9_fault = results["connector-return-fixture/four-db9-fault"]
    db9_control = results["connector-return-fixture/four-db9-control"]
    assert db9_fault["lint_status"] == "REVIEW"
    assert set(db9_fault["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "net.numbered_returns",
    }
    assert db9_control["lint_status"] == "PASS"
    assert db9_control["findings"] == "none"
    grounding_expectations = {
        "ground-contract-common-fault": "FAIL",
        "ground-contract-common-control": "PASS",
        "ground-contract-isolated-fault": "PASS",
        "ground-contract-isolated-control": "FAIL",
    }
    for case, expected_contract_status in grounding_expectations.items():
        item = results[f"connector-return-fixture/{case}"]
        assert item["status"] == "PASS"
        assert item["contract_status"] == expected_contract_status
        assert item["repeatable"] == "true"
        assert re.search(r"^[0-9a-f]{64}$", item["grounding_contract_sha256"]) is not None
    assert results["connector-return-fixture/ground-contract-common-fault"]["checks"] == (
        "grounding/COMMON_RETURN=FAIL;grounding/component-coverage=PASS;grounding/return-net-review=FAIL"
    )
    assert (
        results["connector-return-fixture/ground-contract-common-control"]["checks"]
        == "grounding/COMMON_RETURN=PASS;grounding/component-coverage=PASS"
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
        assert item["status"] == "PASS"
        assert item["contract_status"] == expected_contract_status
        assert item["repeatable"] == "true"
        assert re.search(r"^[0-9a-f]{64}$", item["pin_connectivity_contract_sha256"]) is not None
    assert (
        results["connector-return-fixture/pin-connectivity-contract-common-fault"]["checks"]
        == "pin-connectivity/db9-common-return=FAIL"
    )
    assert (
        results["connector-return-fixture/pin-connectivity-contract-common-control"]["checks"]
        == "pin-connectivity/db9-common-return=PASS"
    )
    assert results["connector-return-fixture/pin-connectivity-contract-isolated-fault"][
        "checks"
    ] == ";".join(
        f"pin-connectivity/db9-{reference}-isolated-return=PASS" for reference in range(1, 5)
    )
    assert results["connector-return-fixture/pin-connectivity-contract-isolated-control"][
        "checks"
    ] == ";".join(
        f"pin-connectivity/db9-{reference}-isolated-return=FAIL" for reference in range(1, 5)
    )
    assert (
        results["connector-return-fixture/pin-connectivity-contract-peer-common-open-fault"][
            "checks"
        ]
        == "pin-connectivity/peer-common-power=FAIL"
    )
    assert (
        results["connector-return-fixture/pin-connectivity-contract-peer-common-control"]["checks"]
        == "pin-connectivity/peer-common-power=PASS"
    )
    assert results["connector-return-fixture/pin-connectivity-contract-peer-independent-control"][
        "checks"
    ] == (
        "pin-connectivity/peer-independent-power-outputs=PASS;"
        "pin-connectivity/peer-j3-power-unused=PASS"
    )
    assert results[
        "connector-return-fixture/pin-connectivity-contract-peer-independent-common-net-mismatch"
    ]["checks"] == (
        "pin-connectivity/peer-independent-power-outputs=FAIL;"
        "pin-connectivity/peer-j3-power-unused=FAIL"
    )
    stale_pin = results["connector-return-fixture/pin-connectivity-contract-stale-pin-reference"]
    assert stale_pin["status"] == "PASS"
    assert stale_pin["contract_status"] == "FAIL"
    assert stale_pin["relationship"] == "stale-symbol-pin"
    assert stale_pin["checks"] == "pin-connectivity/stale-pin-reference=FAIL"
    assert (
        "unknown symbol pins=['J1.99']"
        in json.loads(stale_pin["check_details"])["pin-connectivity/stale-pin-reference"]
    )
    assert stale_pin["repeatable"] == "true"
    neutral_fault = results["connector-return-fixture/four-db9-neutral-fault"]
    neutral_control = results["connector-return-fixture/four-db9-neutral-control"]
    assert neutral_fault["lint_status"] == "REVIEW"
    assert set(neutral_fault["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "connector.no_connected_return",
    }
    assert set(neutral_fault["subjects"].split(";")) == {
        "Lint:DB9: 7",
        "Lint:DB9: 9",
        *(f"J{reference}: no connected return" for reference in range(1, 5)),
    }
    assert "J1.7=7" in neutral_fault["pin_functions"]
    assert "J1.9=9" in neutral_fault["pin_functions"]
    assert neutral_control["lint_status"] == "REVIEW"
    assert set(neutral_control["findings"].split(",")) == {"connector.no_connected_return"}
    generic_power_fault = results["connector-return-fixture/unconnected-generic-power-input-fault"]
    generic_power_control = results[
        "connector-return-fixture/unconnected-generic-power-input-control"
    ]
    assert generic_power_fault["lint_status"] == "REVIEW"
    assert set(generic_power_fault["findings"].split(",")) == {"connector.unconnected_power_input"}
    assert set(generic_power_fault["subjects"].split(";")) == {
        "J1.1: generic native power-input pin is unassigned",
        "J2.1: generic native power-input pin is unassigned",
    }
    assert generic_power_control["lint_status"] == "PASS"
    assert generic_power_control["findings"] == "none"
    generic_component_cases = (
        "unconnected-generic-component-power-input-fault",
        "unconnected-generic-component-power-input-no-connect-fault",
    )
    for case in generic_component_cases:
        item = results[f"connector-return-fixture/{case}"]
        assert item["lint_status"] == "REVIEW"
        assert item["findings"] == "component.unconnected_power_input"
        assert item["subjects"] == "U1.1: generic native power-input pin is unassigned"
        assert item["pin_electrical_types"] == "U1.1=power_in;U1.2=passive"
    for case in (
        "unconnected-generic-component-power-input-control",
        "unconnected-generic-component-power-input-dnp-control",
    ):
        item = results[f"connector-return-fixture/{case}"]
        assert item["lint_status"] == "PASS"
        assert item["findings"] == "none"
    assert fault["netlist_sha256"] != fault["repeat_netlist_sha256"]
    assert control["netlist_sha256"] != control["repeat_netlist_sha256"]
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]
    assert re.search(r"^[0-9a-f]{64}$", fault["source_sha256"]) is not None
    assert re.search(r"^[0-9a-f]{64}$", control["source_sha256"]) is not None
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
        "peer-pin-part-id-open-fault",
        "peer-pin-part-id-common-control",
        "peer-pin-part-id-split-fault",
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
        assert item["status"] == "PASS"
        assert item["normalized_netlist_sha256"] == item["repeat_normalized_netlist_sha256"]
        assert re.search(r"^[0-9a-f]{64}$", item["source_sha256"]) is not None
    mapped_supply_fault = results["connector-return-fixture/reviewed-supply-fault"]
    mapped_supply_control = results["connector-return-fixture/reviewed-supply-control"]
    mapped_supply_domain_control = results[
        "connector-return-fixture/reviewed-supply-domain-control"
    ]
    assert mapped_supply_fault["coverage_status"] == "COMPLETE"
    assert mapped_supply_fault["lint_status"] == "REVIEW"
    assert mapped_supply_fault["findings"] == "connector.repeated_pin_function"
    assert mapped_supply_control["coverage_status"] == "COMPLETE"
    assert mapped_supply_control["lint_status"] == "PASS"
    assert mapped_supply_control["findings"] == "none"
    assert mapped_supply_domain_control["coverage_status"] == "COMPLETE"
    assert mapped_supply_domain_control["lint_status"] == "PASS"
    assert mapped_supply_domain_control["findings"] == "none"
    assert (root / fault["command_receipt"]).is_file()
    export = results["connector-return-fixture/native-export"]
    assert export["status"] == "PASS"
    assert export["kicad_version"] == "10.0.0"
