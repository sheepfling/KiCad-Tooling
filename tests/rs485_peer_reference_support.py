"""Synthetic mapped RS-485 peers for design-lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.rs485_models import (
    Rs485Analysis,
    Rs485BusRequirement,
    Rs485EndpointPinRequirement,
    Rs485EndpointRequirement,
    Rs485NoBiasRequirement,
    Rs485SignalPairRequirement,
    Rs485TerminationEndpointRequirement,
)
from kicad_tooling.hwrepo.rs485_peer_reference_types import Rs485PeerReferenceContext


def rs485_peer_reference_fixture(
    *,
    references: tuple[str, ...] = ("U1", "U2", "U3"),
    reference_nets: dict[str, str] | None = None,
    incomplete_references: tuple[str, ...] = (),
    line_nets: dict[str, tuple[str, str]] | None = None,
    dnp: tuple[str, ...] = (),
) -> tuple[Rs485Analysis, Rs485PeerReferenceContext, NetlistContract]:
    """Build exact authored maps and native assignments for one synthetic RS-485 bus."""
    reference_nets = reference_nets or {reference: "GND_A" for reference in references}
    line_nets = line_nets or {reference: ("RS485_A", "RS485_B") for reference in references}
    endpoint_models: list[Rs485EndpointRequirement] = []
    components: dict[str, ComponentContract] = {}
    symbols: dict[str, str] = {}
    pin_numbers: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    nets: dict[str, list[str]] = {}
    for index, reference in enumerate(references, start=1):
        symbol = f"Synthetic:Rs485Transceiver{index}"
        components[reference] = ComponentContract(
            value=f"Synthetic RS-485 transceiver {index}",
            footprint="Synthetic:SOIC",
        )
        symbols[reference] = symbol
        pin_numbers[reference] = ("1", "2", "3", "4", "5")
        roles = (
            ("1", "bus_line_1", line_nets[reference][0], "pair-a"),
            ("2", "bus_line_2", line_nets[reference][1], "pair-a"),
            ("3", "driver_input", f"TX_{reference}", None),
            ("4", "receiver_output", f"RX_{reference}", None),
            ("5", "reference", reference_nets[reference], None),
        )
        endpoint_models.append(
            Rs485EndpointRequirement(
                id=f"endpoint-{reference.lower()}",
                kind="transceiver",
                reference=reference,
                symbol=symbol,
                footprint="Synthetic:SOIC",
                pins=tuple(
                    Rs485EndpointPinRequirement(
                        role=role,
                        pin=f"{reference}.{number}",
                        net=net,
                        pair_id=pair_id,
                    )
                    for number, role, net, pair_id in roles
                ),
            )
        )
        pin_functions.update(
            {
                f"{reference}.1": "A",
                f"{reference}.2": "B",
                f"{reference}.3": "DI",
                f"{reference}.4": "RO",
                f"{reference}.5": "REF",
            }
        )
        pin_types.update({f"{reference}.{number}": "passive" for number in pin_numbers[reference]})
        for number in ("1", "2"):
            nets.setdefault(line_nets[reference][int(number) - 1], []).append(
                f"{reference}.{number}"
            )
        nets.setdefault(f"TX_{reference}", []).append(f"{reference}.3")
        nets.setdefault(f"RX_{reference}", []).append(f"{reference}.4")
        if reference not in incomplete_references:
            nets.setdefault(reference_nets[reference], []).append(f"{reference}.5")

    analysis = Rs485Analysis(
        basis="Synthetic authored RS-485 peer map",
        buses=(
            Rs485BusRequirement(
                id="field-bus",
                basis="Synthetic shared RS-485 line pair",
                topology="two_wire_half_duplex",
                pairs=(
                    Rs485SignalPairRequirement(
                        id="pair-a",
                        basis="Synthetic A/B pair",
                        purpose="bidirectional",
                        line_1_net="RS485_A",
                        line_2_net="RS485_B",
                        terminations=(
                            Rs485TerminationEndpointRequirement(
                                id="termination-not-required",
                                basis="No local termination in the synthetic fixture",
                                topology="not_required",
                            ),
                        ),
                        bias=Rs485NoBiasRequirement(
                            mode="not_required",
                            basis="Synthetic bias decision",
                            reason="The fixture tests peer reference assignments only.",
                        ),
                    ),
                ),
                endpoints=tuple(endpoint_models),
            ),
        ),
    )
    context = Rs485PeerReferenceContext(
        state="required",
        analysis=analysis,
        source_path="contracts/electrical.json",
        source_sha256="a" * 64,
    )
    netlist = NetlistContract(
        components=components,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=dnp,
    )
    return analysis, context, netlist
