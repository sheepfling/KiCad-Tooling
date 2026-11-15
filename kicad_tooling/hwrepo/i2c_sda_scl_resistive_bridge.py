"""Review fitted resistors directly bridging recognized I2C SDA/SCL nets."""

from __future__ import annotations

from .design_lint_types import Candidate
from .i2c_connector_signal_endpoints import i2c_connector_signal_endpoints
from .i2c_signal_endpoints import i2c_signal_endpoints
from .netlist_contract_models import NetlistContract
from .resistor_paths import direct_resistors

RULE_ID = "bus.i2c_sda_scl_resistive_bridge"


def i2c_sda_scl_resistive_bridge_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Prompt review when a fitted two-terminal resistor bridges an I2C pair.

    A resistor can be part of an intentional circuit, so this deterministic
    topology clue does not assert that a bridge is electrically incorrect.
    """
    resistors = direct_resistors(
        observed,
        include_zero_ohm=True,
        include_device_r_symbol=True,
    )
    findings: list[Candidate] = []
    ic_endpoints = i2c_signal_endpoints(observed)
    ic_net_pairs = {
        frozenset((endpoint.sda_net.casefold(), endpoint.scl_net.casefold()))
        for endpoint in ic_endpoints
    }
    endpoints = [*ic_endpoints]
    reviewed_connector_pairs: set[frozenset[str]] = set()
    for endpoint in i2c_connector_signal_endpoints(observed):
        net_pair = frozenset((endpoint.sda_net.casefold(), endpoint.scl_net.casefold()))
        if net_pair in ic_net_pairs or net_pair in reviewed_connector_pairs:
            continue
        reviewed_connector_pairs.add(net_pair)
        endpoints.append(endpoint)
    for endpoint in endpoints:
        if endpoint.sda_net.casefold() == endpoint.scl_net.casefold():
            continue
        signal_nets = {endpoint.sda_net.casefold(), endpoint.scl_net.casefold()}
        for resistor in resistors:
            if {resistor.first_net.casefold(), resistor.second_net.casefold()} != signal_nets:
                continue
            value = f"{resistor.resistance_ohms:g}Ω"
            findings.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=(
                        f"{endpoint.reference}: I2C SDA/SCL nets {endpoint.sda_net} and "
                        f"{endpoint.scl_net} are bridged by {resistor.reference}"
                    ),
                    message=(
                        f"A fitted two-terminal resistor {resistor.reference} ({value}) directly "
                        f"bridges the schematic nets assigned to SDA ({endpoint.sda_pin}) and "
                        f"SCL ({endpoint.scl_pin}) on {endpoint.reference}. Review whether this "
                        "coupling is intentional; a designed resistor network may be valid. "
                        "Function names do not prove I2C use, required topology, PCB copper, or "
                        "off-board connectivity."
                    ),
                    evidence={
                        "component": (endpoint.reference,),
                        "SDA_pin": (endpoint.sda_pin,),
                        "SCL_pin": (endpoint.scl_pin,),
                        "SDA_net": (endpoint.sda_net,),
                        "SCL_net": (endpoint.scl_net,),
                        "resistor": (resistor.reference,),
                        "resistance_ohms": (value,),
                    },
                )
            )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
