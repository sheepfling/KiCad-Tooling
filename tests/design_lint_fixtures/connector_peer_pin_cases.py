"""Synthetic native-netlist cases for the connector-return fixture lane."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def peer_pin_case_contracts() -> dict[str, NetlistContract]:
    """Return synthetic fault and control netlists for this theme."""
    return {
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
    }
