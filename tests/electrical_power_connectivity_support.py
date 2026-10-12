"""Synthetic power-connectivity contract fixtures."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    NetlistContract,
)
from kicad_tooling.hwrepo.power_connectivity_models import (
    PowerConnectivityAnalysis,
    PowerConnectivityRailRequirement,
    PowerLoadConnectivityRequirement,
    PowerPinEndpointRequirement,
    PowerSourceGroupRequirement,
)


def power_connectivity_requirement(
    *, source_selection: Literal["all", "any"] = "all"
) -> PowerConnectivityAnalysis:
    source_endpoints = (
        PowerPinEndpointRequirement(
            id="barrel-input",
            reference="J40",
            symbol="Synthetic:PowerInput",
            footprint="Connector_BarrelJack:BarrelJack_Horizontal",
            pins=("J40.1",),
        ),
        PowerPinEndpointRequirement(
            id="terminal-input",
            reference="J41",
            symbol="Synthetic:PowerInput",
            footprint="Connector_Generic:Conn_01x02",
            pins=("J41.1",),
        ),
    )
    return PowerConnectivityAnalysis(
        basis="Synthetic reviewed source and load pin map",
        rails=(
            PowerConnectivityRailRequirement(
                id="supply",
                basis="Reviewed unregulated input rail",
                net="VIN_IN",
                source_groups=(
                    PowerSourceGroupRequirement(
                        id="approved-inputs",
                        basis="At least one approved input connector is populated",
                        selection=source_selection,
                        endpoints=source_endpoints,
                    ),
                ),
                loads=(
                    PowerLoadConnectivityRequirement(
                        id="load",
                        basis="Budgeted input load includes regulator and monitor pins",
                        endpoints=(
                            PowerPinEndpointRequirement(
                                id="regulator",
                                reference="U40",
                                symbol="Synthetic:PowerRegulator",
                                footprint="Package_SO:SOIC-8",
                                pins=("U40.1",),
                            ),
                            PowerPinEndpointRequirement(
                                id="monitor",
                                reference="U41",
                                symbol="Synthetic:VoltageMonitor",
                                footprint="Package_SOT:SOT-23-5",
                                pins=("U41.1",),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def power_connectivity_netlist(
    *,
    fault: Literal[
        "source-wrong-net",
        "load-wrong-net",
        "source-dnp",
        "all-sources-dnp",
        "source-identity-wrong",
    ]
    | None = None,
) -> NetlistContract:
    components = {
        "J40": ComponentContract(
            value="Synthetic barrel input", footprint="Connector_BarrelJack:BarrelJack_Horizontal"
        ),
        "J41": ComponentContract(
            value="Synthetic terminal input", footprint="Connector_Generic:Conn_01x02"
        ),
        "U40": ComponentContract(value="Synthetic regulator", footprint="Package_SO:SOIC-8"),
        "U41": ComponentContract(value="Synthetic monitor", footprint="Package_SOT:SOT-23-5"),
    }
    symbols = {
        "J40": "Synthetic:PowerInput",
        "J41": "Synthetic:PowerInput",
        "U40": "Synthetic:PowerRegulator",
        "U41": "Synthetic:VoltageMonitor",
    }
    assignments = {
        "J40.1": "VIN_IN",
        "J41.1": "VIN_IN",
        "U40.1": "VIN_IN",
        "U41.1": "VIN_IN",
    }
    dnp: set[str] = set()
    if fault == "source-wrong-net":
        assignments["J40.1"] = "WRONG_INPUT"
    elif fault == "load-wrong-net":
        assignments["U40.1"] = "WRONG_INPUT"
    elif fault == "source-dnp":
        dnp.add("J40")
    elif fault == "all-sources-dnp":
        dnp.update(("J40", "J41"))
    elif fault == "source-identity-wrong":
        symbols["J40"] = "Synthetic:DifferentConnector"
    nets: dict[str, list[str]] = {}
    for pin, net in assignments.items():
        nets.setdefault(net, []).append(pin)
    return NetlistContract(
        components=components,
        nets={net: tuple(sorted(pins)) for net, pins in nets.items()},
        dnp_components=tuple(sorted(dnp)),
        component_symbols=symbols,
        pin_functions={pin: pin.rsplit(".", 1)[1] for pin in assignments},
        component_pin_numbers={reference: ("1",) for reference in components},
    )
