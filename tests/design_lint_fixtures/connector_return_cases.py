"""Synthetic native-netlist cases for the connector-return fixture lane."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def return_case_contracts() -> dict[str, NetlistContract]:
    """Return synthetic fault and control netlists for this theme."""
    return {
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
    }
