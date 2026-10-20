"""Synthetic typed-netlist fixtures shared by footprint-alias peer regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)

FOOTPRINT_PEER_RULE_ID = "connector.footprint_peer_pin_assignment_divergence"
FOOTPRINT_OPEN_RULE_ID = "connector.footprint_peer_pin_open_outlier"
FOOTPRINT_ALL_OPEN_RULE_ID = "connector.footprint_peer_pin_all_open"
NETLIST_SHA256 = "a" * 64


def peer_netlist(
    *,
    assignments: tuple[tuple[str | None, str | None], ...] = (
        ("GND", "GND"),
        ("DATA_A", "DATA_B"),
    ),
    functions: tuple[str, str] = ("Pin_1", "Pin_2"),
    electrical_types: tuple[str, str] = ("passive", "passive"),
    part_id: str | None = None,
    dnp: tuple[str, ...] = (),
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    open_pin: str | None = None,
    ambiguous_pin: str | None = None,
) -> NetlistContract:
    """Build two native-metadata-matched alias peers with controlled assignments."""
    components = {
        reference: ComponentContract(
            value="Synthetic two-contact connector",
            footprint="Synthetic:Connector_2x1",
            part_id=part_id,
        )
        for reference in ("J1", "J2")
    }
    nets: dict[str, tuple[str, ...]] = {}
    for number, pair in enumerate(assignments, start=1):
        for reference, net in zip(("J1", "J2"), pair, strict=True):
            pin = f"{reference}.{number}"
            if net is not None and pin != open_pin:
                nets[net] = (*nets.get(net, ()), pin)
    if ambiguous_pin is not None:
        nets["SYNTHETIC_AMBIGUOUS_NET"] = (
            *nets.get("SYNTHETIC_AMBIGUOUS_NET", ()),
            ambiguous_pin,
        )
    pin_numbers = {reference: ("1", "2") for reference in ("J1", "J2")}
    if incomplete_inventory:
        pin_numbers["J2"] = ("1",)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols={"J1": "Synthetic:GenericPort", "J2": "Synthetic:GenericPortAlias"},
        component_pin_numbers=pin_numbers,
        pin_functions={
            f"{reference}.{number}": function
            for reference in ("J1", "J2")
            for number, function in enumerate(functions, start=1)
        },
        pin_electrical_types={
            f"{reference}.{number}": electrical_types[int(number) - 1]
            for reference in ("J1", "J2")
            for number in ("1", "2")
            if f"{reference}.{number}" != missing_metadata_pin
        },
    )


def peer_pin_reachability_netlists() -> tuple[NetlistContract, ...]:
    """Provide synthetic alias cases for footprint-peer rule reachability."""
    return (
        peer_netlist(assignments=(("GND", "GND"), ("DATA_A", "DATA_B"))),
        peer_netlist(assignments=(("GND", "GND"), ("DATA_A", None))),
        peer_netlist(
            assignments=(("GND", "GND"), ("BIAS_IN", None)),
            functions=("GND", "BIAS_IN"),
            electrical_types=("passive", "power_in"),
        ),
        peer_netlist(
            assignments=(("GND", "GND"), ("UART_RX", None)),
            functions=("GND", "UART_RX"),
            electrical_types=("passive", "input"),
        ),
        peer_netlist(assignments=(("GND", "GND"), (None, None))),
    )


def lint_report(
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    """Evaluate one synthetic connector observation with the supplied policy."""
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-footprint-alias-peer-pins",
        observed=observed,
        netlist_sha256=NETLIST_SHA256,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())
