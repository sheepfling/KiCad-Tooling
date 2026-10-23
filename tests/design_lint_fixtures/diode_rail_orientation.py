"""Synthetic numeric and named-return inputs for diode direction review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

NATIVE_FIXTURE_SHA256 = {
    "fault_numeric": "811b5eeaa973d5183ad849d0115cfe754f8902393bb95ca5869b7b91ef28a195",
    "fault_return": "a9d451916cdb836be6ad2b7f2561fc609827c3daabc9d6645190d34713442c33",
    "control": "98089723702153b63e9e8ce8ad67bf53277215ded30ad149dad6ef52330f78e4",
}


def netlist(
    *,
    anode_net: str = "+3V3",
    cathode_net: str = "+5V",
    symbol: str = "Device:D",
    pin_numbers: tuple[str, ...] = ("1", "2"),
    pin_functions: dict[str, str] | None = None,
    dnp: tuple[str, ...] = (),
    nets: dict[str, tuple[str, ...]] | None = None,
) -> NetlistContract:
    functions = pin_functions or {"D1.1": "K", "D1.2": "A"}
    assignments = nets or {
        anode_net: ("D1.2",),
        cathode_net: ("D1.1",),
    }
    return NetlistContract(
        components={"D1": ComponentContract(value="Synthetic diode", footprint="Synthetic:D")},
        nets=assignments,
        dnp_components=dnp,
        component_symbols={"D1": symbol},
        pin_functions=functions,
        component_pin_numbers={"D1": pin_numbers},
    )
