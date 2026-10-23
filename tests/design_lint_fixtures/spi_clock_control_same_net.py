"""Minimal synthetic netlists for SPI clock/control and data same-net review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def spi_clock_control_same_net_netlist(
    *,
    shared: bool = True,
    control_function: str = "SCK",
    data_function: str = "MOSI",
    control_channel: int | None = None,
    data_channel: int | None = None,
    control_type: str = "input",
    data_type: str = "input",
    dnp: bool = False,
    component: str = "U1",
    inventory: tuple[str, ...] = ("1", "2", "3", "4"),
) -> NetlistContract:
    """Build one fitted SPI IC with clock/control and data role pins."""
    if control_channel is not None:
        control_function = f"SPI{control_channel}_{control_function}"
    if data_channel is not None:
        data_function = f"SPI{data_channel}_{data_function}"
    control_pin = f"{component}.1"
    data_pin = f"{component}.2"
    miso_pin = f"{component}.3"
    select_pin = f"{component}.4"
    nets = (
        {"SPI_ROLE_SHARED": (control_pin, data_pin)}
        if shared
        else {"SPI_SCK": (control_pin,), "SPI_MOSI": (data_pin,)}
    )
    nets.update({"SPI_MISO": (miso_pin,), "SPI_CS": (select_pin,)})
    return NetlistContract(
        components={
            component: ComponentContract(value="Synthetic SPI device", footprint="Synthetic:IC")
        },
        nets=nets,
        dnp_components=(component,) if dnp else (),
        component_symbols={component: "Synthetic:SpiDevice"},
        pin_functions={
            control_pin: control_function,
            data_pin: data_function,
            miso_pin: "CIPO",
            select_pin: "NSS",
        },
        pin_electrical_types={
            control_pin: control_type,
            data_pin: data_type,
            miso_pin: "tri_state",
            select_pin: "input",
        },
        component_pin_numbers={component: inventory},
    )


def spi_clock_chip_select_same_net_netlist(
    *,
    shared: bool = True,
    clock_function: str = "SCK",
    select_function: str = "NSS",
    clock_channel: int | None = None,
    select_channel: int | None = None,
    clock_type: str = "input",
    select_type: str = "input",
    dnp: bool = False,
    component: str = "U1",
    inventory: tuple[str, ...] = ("1", "2", "3", "4"),
) -> NetlistContract:
    """Build one fitted SPI IC with clock and select roles on configurable nets."""
    if clock_channel is not None:
        clock_function = f"SPI{clock_channel}_{clock_function}"
    if select_channel is not None:
        select_function = f"SPI{select_channel}_{select_function}"
    clock_pin = f"{component}.1"
    select_pin = f"{component}.2"
    input_data_pin = f"{component}.3"
    output_data_pin = f"{component}.4"
    nets = (
        {"SPI_CONTROL_SHARED": (clock_pin, select_pin)}
        if shared
        else {"SPI_SCK": (clock_pin,), "SPI_CS": (select_pin,)}
    )
    nets.update({"SPI_MOSI": (input_data_pin,), "SPI_MISO": (output_data_pin,)})
    return NetlistContract(
        components={
            component: ComponentContract(value="Synthetic SPI device", footprint="Synthetic:IC")
        },
        nets=nets,
        dnp_components=(component,) if dnp else (),
        component_symbols={component: "Synthetic:SpiDevice"},
        pin_functions={
            clock_pin: clock_function,
            select_pin: select_function,
            input_data_pin: "MOSI",
            output_data_pin: "MISO",
        },
        pin_electrical_types={
            clock_pin: clock_type,
            select_pin: select_type,
            input_data_pin: "input",
            output_data_pin: "tri_state",
        },
        component_pin_numbers={component: inventory},
    )
