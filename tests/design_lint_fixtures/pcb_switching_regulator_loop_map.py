"""Synthetic switching-regulator netlists and authored loop-map controls."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    NetlistContract,
    PcbSwitchingLoopMap,
    PcbSwitchingLoopPad,
    PcbSwitchingLoopRequirement,
)


def regulator_netlist(
    *,
    symbol: str = "Regulator_Switching:SyntheticBuck",
    footprint: str = "Synthetic:QFN",
    dnp: bool = False,
    missing_function_pin: str | None = None,
    missing_type_pin: str | None = None,
    open_switch_pin: str | None = None,
    ambiguous_switch_pin: str | None = None,
    function_overrides: Mapping[str, str] | None = None,
) -> NetlistContract:
    """Return complete native-like pin data, with narrow fault controls."""
    pin_functions = {"U1.1": "VIN", "U1.2": "SW", "U1.3": "LX1", "U1.4": "GND"}
    pin_types = {pin: "passive" for pin in pin_functions}
    nets = {
        "INPUT": ("U1.1",),
        "SWITCH_A": ("U1.2",),
        "SWITCH_B": ("U1.3",),
        "RETURN": ("U1.4",),
    }
    if missing_function_pin is not None:
        pin_functions.pop(missing_function_pin, None)
    if function_overrides is not None:
        pin_functions.update(function_overrides)
    if missing_type_pin is not None:
        pin_types.pop(missing_type_pin, None)
    if open_switch_pin is not None:
        for net, pins in tuple(nets.items()):
            nets[net] = tuple(pin for pin in pins if pin != open_switch_pin)
            if not nets[net]:
                del nets[net]
    if ambiguous_switch_pin is not None:
        nets["SECOND_ASSIGNMENT"] = (ambiguous_switch_pin,)

    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic buck", footprint=footprint)},
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": symbol},
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers={"U1": ("1", "2", "3", "4")},
    )


def loop_map(mapped_pins: tuple[str, ...]) -> PcbSwitchingLoopMap:
    """Build a minimal schema-valid loop map containing selected switch pads."""
    pads = [
        PcbSwitchingLoopPad(pad=pin, footprint="Synthetic:QFN", net="SWITCH")
        for pin in mapped_pins
    ]
    pads.extend(
        (
            PcbSwitchingLoopPad(pad="C1.1", footprint="Synthetic:Capacitor", net="INPUT"),
            PcbSwitchingLoopPad(pad="C1.2", footprint="Synthetic:Capacitor", net="RETURN"),
            PcbSwitchingLoopPad(pad="C1.3", footprint="Synthetic:Capacitor", net="RETURN"),
        )
    )
    return PcbSwitchingLoopMap(
        basis="Synthetic authored converter switching-loop review",
        requirements=(
            PcbSwitchingLoopRequirement(
                id="synthetic-buck-loop",
                basis="Synthetic fixture only",
                loop_pads=tuple(pads),
                return_net="RETURN",
                return_plane_layer="B.Cu",
                return_plane_pads=(pads[-2], pads[-1]),
            ),
        ),
    )
