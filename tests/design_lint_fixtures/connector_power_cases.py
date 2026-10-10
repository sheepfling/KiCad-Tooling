"""Synthetic native-netlist cases for the connector-return fixture lane."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def connector_power_case_contracts() -> dict[str, NetlistContract]:
    """Return synthetic fault and control netlists for this theme."""
    return {
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


def generic_component_power_input_cases() -> dict[str, NetlistContract]:
    """Return generic component power-input fault and control netlists."""
    cases: dict[str, NetlistContract] = {}
    for case in (
        "unconnected-generic-component-power-input-fault",
        "unconnected-generic-component-power-input-control",
        "unconnected-generic-component-power-input-no-connect-fault",
        "unconnected-generic-component-power-input-dnp-control",
    ):
        connected = case.endswith("-control") and not case.endswith("-dnp-control")
        cases[case] = NetlistContract(
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
    return cases
