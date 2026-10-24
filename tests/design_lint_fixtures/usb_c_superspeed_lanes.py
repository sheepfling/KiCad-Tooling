"""Small typed-netlist fixtures for lane-indexed USB-C SuperSpeed pairs."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import NetlistContract

_LANE_FUNCTIONS = {
    "J1.1": "StdA_SSTX1+",
    "J1.2": "StdA_SSTX1−",
    "J1.3": "StdA_SSTX2+",
    "J1.4": "StdA_SSTX2−",
    "J1.5": "StdA_SSRX1+",
    "J1.6": "StdA_SSRX1−",
    "J1.7": "StdA_SSRX2+",
    "J1.8": "StdA_SSRX2−",
}


def usb_c_superspeed_lane_netlist(
    *,
    shared_pair: str | None = None,
    open_pin: str | None = None,
    dnp: bool = False,
) -> NetlistContract:
    """Build four explicit lane/direction pairs, optionally mutating one pair."""
    nets: dict[str, tuple[str, ...]] = {}
    assignments: dict[str, str] = {}
    for pin, function in _LANE_FUNCTIONS.items():
        match = function.replace("−", "-")
        direction = "TX" if "SSTX" in match else "RX"
        lane = "1" if "1" in match else "2"
        side = "P" if match.endswith("+") else "N"
        pair_key = f"{direction}{lane}"
        net = f"USB_{pair_key}_{side}"
        if shared_pair == pair_key:
            net = f"USB_{pair_key}_SHORT"
        if pin != open_pin:
            assignments[pin] = net
    for pin, net in assignments.items():
        nets[net] = (*nets.get(net, ()), pin)
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={"J1": "Connector:USB_C_Receptacle_24P"},
        pin_functions=dict(_LANE_FUNCTIONS),
        component_pin_numbers={"J1": tuple(str(index) for index in range(1, 9))},
        dnp_components=("J1",) if dnp else (),
    )


def usb_c_superspeed_lane_fault_netlist() -> NetlistContract:
    """Expose a neutral-named shared TX1 lane while other lanes stay valid."""
    return usb_c_superspeed_lane_netlist(shared_pair="TX1")
