"""Synthetic netlist and roster records shared by SPI participant tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    NetlistContract,
    SpiAnalysis,
    SpiBusRequirement,
    SpiControllerRequirement,
    SpiDeviceRequirement,
    SpiMisoConnectedRequirement,
    SpiPinNetRequirement,
)


def spi_netlist(
    *,
    dnp: tuple[str, ...] = (),
    include_connector: bool = False,
    partial_ic: bool = False,
    combo_interface: bool = False,
) -> NetlistContract:
    """Return a synthetic roster with optional slash-separated combo-device pins."""
    components = {
        "U1": ComponentContract(value="Synthetic controller", footprint="Synthetic:QFN"),
        "U2": ComponentContract(value="Synthetic peripheral", footprint="Synthetic:SOIC"),
        "U3": ComponentContract(value="Synthetic second peripheral", footprint="Synthetic:SOIC"),
        "U4": ComponentContract(value="Synthetic non-SPI IC", footprint="Synthetic:SOIC"),
    }
    symbols = {reference: f"Synthetic:{reference}" for reference in components}
    functions = {
        "U1.1": "SCK",
        "U1.2": "MOSI",
        "U1.3": "MISO",
        "U1.4": "CS",
        "U1.5": "CS",
        "U2.1": "SCK",
        "U2.2": "MOSI",
        "U2.3": "MISO",
        "U2.4": "CS",
        "U3.1": "SPI1_SCLK",
        "U3.2": "SPI1_COPI",
        "U3.3": "SPI1_CIPO",
        "U3.4": "SPI1_NSS",
        "U4.1": "SCK",
        "U4.2": "MOSI",
    }
    if combo_interface:
        functions.update(
            {
                "U4.1": "SCL/SPC",
                "U4.2": "SDA/SDI/SDO",
                "U4.3": "SDO/SA0",
                "U4.4": "CS",
            }
        )
    nets: dict[str, tuple[str, ...]] = {
        "SPI_SCK": ("U1.1", "U2.1", "U3.1", "U4.1"),
        "SPI_MOSI": ("U1.2", "U2.2", "U3.2", "U4.2"),
        "SPI_MISO": ("U1.3", "U2.3", "U3.3"),
        "SPI_CS0": ("U1.4", "U2.4"),
        "SPI_CS1": ("U1.5", "U3.4"),
    }
    if combo_interface:
        nets["SPI_MISO"] = (*nets["SPI_MISO"], "U4.3")
        nets["SPI_CS2"] = ("U4.4",)
    if partial_ic:
        functions.pop("U4.2")
    if include_connector:
        components["J1"] = ComponentContract(
            value="Synthetic connector", footprint="Synthetic:Header"
        )
        symbols["J1"] = "Synthetic:Connector"
        functions.update({"J1.1": "SCK", "J1.2": "MOSI", "J1.3": "CS"})
        nets["SPI_SCK"] = (*nets["SPI_SCK"], "J1.1")
        nets["SPI_MOSI"] = (*nets["SPI_MOSI"], "J1.2")
        nets["SPI_CS0"] = (*nets["SPI_CS0"], "J1.3")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        component_pin_numbers={
            reference: tuple(
                pin.rsplit(".", 1)[1] for pin in functions if pin.startswith(f"{reference}.")
            )
            for reference in components
        },
    )


def spi_roster(*, device_references: tuple[str, ...] = ("U2", "U3")) -> SpiAnalysis:
    """Return a synthetic independently authored controller/device roster."""
    controller = SpiControllerRequirement(
        reference="U1",
        symbol="Synthetic:U1",
        footprint="Synthetic:QFN",
        sck=SpiPinNetRequirement(pin="U1.1", net="SPI_SCK"),
        mosi=SpiPinNetRequirement(pin="U1.2", net="SPI_MOSI"),
        miso=SpiMisoConnectedRequirement(mode="connected", pin="U1.3", net="SPI_MISO"),
        chip_selects=tuple(
            SpiPinNetRequirement(pin=f"U1.{4 + index}", net=f"SPI_CS{index}")
            for index, _reference in enumerate(device_references)
        ),
    )
    devices = tuple(
        SpiDeviceRequirement(
            id=f"device_{index}",
            reference=reference,
            symbol=f"Synthetic:{reference}",
            footprint="Synthetic:SOIC",
            sck=SpiPinNetRequirement(pin=f"{reference}.1", net="SPI_SCK"),
            mosi=SpiPinNetRequirement(pin=f"{reference}.2", net="SPI_MOSI"),
            miso=SpiMisoConnectedRequirement(
                mode="connected", pin=f"{reference}.3", net="SPI_MISO"
            ),
            chip_select=SpiPinNetRequirement(pin=f"{reference}.4", net=f"SPI_CS{index}"),
        )
        for index, reference in enumerate(device_references)
    )
    return SpiAnalysis(
        basis="Synthetic independently authored controller and device roster",
        buses=(
            SpiBusRequirement(
                id="MAIN",
                basis="Synthetic SPI roster fixture",
                controller=controller,
                devices=devices,
            ),
        ),
    )


def coach(observed: NetlistContract, netlist_sha256: str = "a" * 64) -> ContractCoachReport:
    """Wrap a synthetic native-shaped netlist in a review-ready coach report."""
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-spi-roster",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )
