"""Synthetic native-netlist cases for the connector-return fixture lane."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from tests.design_lint_fixtures.connector_footprint_alias_numeric_cases import (
    footprint_alias_numeric_peer_pin_cases,
)


def _all_open_generic_peer_pin_cases() -> dict[str, NetlistContract]:
    references = ("J1", "J2")
    functions = {
        f"{reference}.{number}": f"Pin_{number}"
        for reference in references
        for number in ("1", "2")
    }
    electrical_types = {pin: "passive" for pin in functions}
    exact_components = {
        reference: ComponentContract(value="Synthetic generic peer port", footprint="")
        for reference in references
    }
    alias_components = {
        reference: ComponentContract(
            value="Synthetic two-contact connector",
            footprint="Synthetic:Port_2x1",
            part_id="SYNTHETIC-CONNECTOR-2PIN-001",
        )
        for reference in references
    }
    return {
        "all-open-generic-peer-fault": NetlistContract(
            components=exact_components,
            nets={"+5V": ("J1.1", "J2.1")},
            component_symbols={reference: "Lint:PeerPowerPort" for reference in references},
            component_pin_numbers={reference: ("1", "2") for reference in references},
            pin_functions=functions,
            pin_electrical_types=electrical_types,
        ),
        "all-open-generic-peer-control": NetlistContract(
            components=exact_components,
            nets={"+5V": ("J1.1", "J2.1"), "GND": ("J1.2", "J2.2")},
            component_symbols={reference: "Lint:PeerPowerPort" for reference in references},
            component_pin_numbers={reference: ("1", "2") for reference in references},
            pin_functions=functions,
            pin_electrical_types=electrical_types,
        ),
        "part-id-all-open-generic-peer-fault": NetlistContract(
            components=alias_components,
            nets={"SYNTHETIC_DATA": ("J1.1", "J2.1")},
            component_symbols={
                "J1": "Synthetic:GenericPort",
                "J2": "Synthetic:GenericPortAlias",
            },
            component_pin_numbers={reference: ("1", "2") for reference in references},
            pin_functions=functions,
            pin_electrical_types=electrical_types,
        ),
    }


def _footprint_alias_peer_pin_cases() -> dict[str, NetlistContract]:
    references = ("J1", "J2")
    components = {
        reference: ComponentContract(
            value="Synthetic two-contact connector",
            footprint="Synthetic:Connector_2x1",
        )
        for reference in references
    }
    symbols = {
        "J1": "Synthetic:GenericPort",
        "J2": "Synthetic:GenericPortAlias",
    }
    pin_numbers = {reference: ("1", "2") for reference in references}
    functions = {
        f"{reference}.{number}": f"Pin_{number}"
        for reference in references
        for number in ("1", "2")
    }
    electrical_types = {pin: "passive" for pin in functions}
    return {
        "footprint-alias-fault": NetlistContract(
            components=components,
            nets={
                "SYNTHETIC_NET_1": ("J1.1", "J2.1"),
                "SYNTHETIC_NET_2": ("J1.2",),
                "SYNTHETIC_NET_3": ("J2.2",),
            },
            component_symbols=symbols,
            component_pin_numbers=pin_numbers,
            pin_functions=functions,
            pin_electrical_types=electrical_types,
        ),
        "footprint-alias-control": NetlistContract(
            components=components,
            nets={
                "SYNTHETIC_NET_1": ("J1.1", "J2.1"),
                "SYNTHETIC_NET_2": ("J1.2", "J2.2"),
            },
            component_symbols=symbols,
            component_pin_numbers=pin_numbers,
            pin_functions=functions,
            pin_electrical_types=electrical_types,
        ),
        "footprint-alias-open-fault": NetlistContract(
            components=components,
            nets={
                "SYNTHETIC_NET_1": ("J1.1", "J2.1"),
                "SYNTHETIC_NET_2": ("J1.2",),
            },
            unconnected_nets={"unconnected": ("J2.2",)},
            component_symbols=symbols,
            component_pin_numbers=pin_numbers,
            pin_functions=functions,
            pin_electrical_types=electrical_types,
        ),
    }


def _all_open_generic_signal_peer_pin_cases() -> dict[str, NetlistContract]:
    references = ("J1", "J2")
    components = {
        reference: ComponentContract(value="Synthetic peer signal port", footprint="")
        for reference in references
    }
    return {
        "all-open-generic-signal-peer-fault": NetlistContract(
            components=components,
            nets={"+5V": ("J1.1", "J2.1")},
            component_symbols={reference: "Lint:PeerSignalPort" for reference in references},
            component_pin_numbers={reference: ("1", "2") for reference in references},
            pin_functions={
                f"{reference}.{number}": f"Pin_{number}"
                for reference in references
                for number in ("1", "2")
            },
            pin_electrical_types={
                **{f"{reference}.1": "passive" for reference in references},
                **{f"{reference}.2": "input" for reference in references},
            },
        ),
        "all-open-generic-signal-peer-control": NetlistContract(
            components=components,
            nets={"+5V": ("J1.1", "J2.1"), "GND": ("J1.2", "J2.2")},
            component_symbols={reference: "Lint:PeerSignalPort" for reference in references},
            component_pin_numbers={reference: ("1", "2") for reference in references},
            pin_functions={
                f"{reference}.{number}": f"Pin_{number}"
                for reference in references
                for number in ("1", "2")
            },
            pin_electrical_types={
                **{f"{reference}.1": "passive" for reference in references},
                **{f"{reference}.2": "input" for reference in references},
            },
        ),
    }


def _all_open_generic_signal_type_cases() -> dict[str, NetlistContract]:
    references = ("J1", "J2")
    signal_types = {
        "2": ("input", "SIGNAL_INPUT"),
        "3": ("output", "SIGNAL_OUTPUT"),
        "4": ("bidirectional", "SIGNAL_BIDIRECTIONAL"),
        "5": ("tri_state", "SIGNAL_TRI_STATE"),
        "6": ("open_collector", "SIGNAL_OPEN_COLLECTOR"),
        "7": ("open_emitter", "SIGNAL_OPEN_EMITTER"),
    }
    components = {
        reference: ComponentContract(value="Synthetic peer signal port", footprint="")
        for reference in references
    }
    symbols = {reference: "Lint:PeerSignalPort" for reference in references}
    pin_numbers = {
        reference: tuple(str(number) for number in range(1, 9)) for reference in references
    }
    functions = {
        f"{reference}.{number}": f"Pin_{number}"
        for reference in references
        for number in range(1, 8)
    }
    functions.update({f"{reference}.8": "GND" for reference in references})
    electrical_types = {
        **{f"{reference}.1": "passive" for reference in references},
        **{
            f"{reference}.{number}": electrical_type
            for reference in references
            for number, (electrical_type, _) in signal_types.items()
        },
        **{f"{reference}.8": "passive" for reference in references},
    }
    fault_nets = {"+5V": ("J1.1", "J2.1"), "GND": ("J1.8", "J2.8")}
    control_nets = {
        **fault_nets,
        **{net: (f"J1.{number}", f"J2.{number}") for number, (_, net) in signal_types.items()},
    }
    return {
        "all-open-generic-signal-types-fault": NetlistContract(
            components=components,
            nets=fault_nets,
            component_symbols=symbols,
            component_pin_numbers=pin_numbers,
            pin_functions=functions,
            pin_electrical_types=electrical_types,
        ),
        "all-open-generic-signal-types-control": NetlistContract(
            components=components,
            nets=control_nets,
            component_symbols=symbols,
            component_pin_numbers=pin_numbers,
            pin_functions=functions,
            pin_electrical_types=electrical_types,
        ),
    }


def peer_pin_case_contracts() -> dict[str, NetlistContract]:
    """Return synthetic fault and control netlists for this theme."""
    return {
        **_all_open_generic_peer_pin_cases(),
        **_footprint_alias_peer_pin_cases(),
        **footprint_alias_numeric_peer_pin_cases(),
        **_all_open_generic_signal_peer_pin_cases(),
        **_all_open_generic_signal_type_cases(),
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
