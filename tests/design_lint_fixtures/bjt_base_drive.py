"""Minimal synthetic BJT base-drive topology inputs."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def bjt_base_drive_netlist(
    *,
    family: str = "npn",
    series_resistor: bool = False,
    pin_numbers: Mapping[str, str] | None = None,
    driver_type: str = "output",
    bjt_dnp: bool = False,
    driver_dnp: bool = False,
) -> NetlistContract:
    """Build one supported BJT with either direct drive or a series resistor."""
    if family not in {"npn", "pnp"}:
        raise ValueError("family must be npn or pnp")
    pins = dict(pin_numbers or {"base": "1", "collector": "2", "emitter": "3"})
    if set(pins) != {"base", "collector", "emitter"}:
        raise ValueError("pin_numbers must map base, collector, and emitter")

    base_pin = f"Q1.{pins['base']}"
    collector_pin = f"Q1.{pins['collector']}"
    emitter_pin = f"Q1.{pins['emitter']}"
    driver_pin = "U1.1"
    components = {
        "Q1": ComponentContract(value="Synthetic BJT", footprint="Synthetic:TO-92"),
        "U1": ComponentContract(value="Synthetic output", footprint="Synthetic:Output"),
    }
    nets: dict[str, tuple[str, ...]] = {
        "COLLECTOR": (collector_pin,),
        "EMITTER": (emitter_pin,),
    }
    if series_resistor:
        components["R1"] = ComponentContract(value="1k", footprint="Synthetic:R")
        nets["DRIVER_OUT"] = (driver_pin, "R1.1")
        nets["BASE_DRIVE"] = (base_pin, "R1.2")
    else:
        nets["BASE_DRIVE"] = (base_pin, driver_pin)

    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=tuple(
            reference for reference, is_dnp in (("Q1", bjt_dnp), ("U1", driver_dnp)) if is_dnp
        ),
        component_symbols={
            "Q1": f"Transistor_BJT:Q_{family.upper()}_BCE",
            "U1": "Synthetic:Output",
            **({"R1": "Device:R"} if series_resistor else {}),
        },
        component_pin_numbers={
            "Q1": tuple(pins.values()),
            "U1": ("1",),
            **({"R1": ("1", "2")} if series_resistor else {}),
        },
        pin_functions={
            base_pin: "B",
            collector_pin: "C",
            emitter_pin: "E",
            driver_pin: "CTRL",
        },
        pin_electrical_types={driver_pin: driver_type},
    )
