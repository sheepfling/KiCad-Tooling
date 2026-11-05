"""Review one fitted SPI IC's data-input and data-output pins on one net."""

from __future__ import annotations

from .design_lint_spi_same_net_candidate_evidence import (
    SpiDataRolesSameNetEvidence,
    SpiSameNetCandidate,
)
from .netlist_contract_models import NetlistContract
from .spi_role_assignments import spi_role_assignment_groups

RULE_ID = "bus.spi_data_input_output_same_net"


def spi_data_input_output_same_net_candidates(
    observed: NetlistContract,
) -> tuple[SpiSameNetCandidate, ...]:
    """Find one uniquely assigned SPI data-input/output pair on the same native net.

    This is a review clue: loopback, single-wire, and part-specific modes can
    intentionally join the pins. Open or duplicate role pins, missing pin
    inventory, DNP parts, and ambiguous assignments are left unclassified.
    """
    findings: list[SpiSameNetCandidate] = []
    groups = spi_role_assignment_groups(observed)
    for group in groups:
        inputs = group.roles.get("data_input", ())
        outputs = group.roles.get("data_output", ())
        if len(inputs) != 1 or len(outputs) != 1:
            continue
        input_endpoint, output_endpoint = inputs[0], outputs[0]
        if not input_endpoint.in_component_inventory or not output_endpoint.in_component_inventory:
            continue
        if len(input_endpoint.nets) != 1 or len(output_endpoint.nets) != 1:
            continue
        if input_endpoint.nets[0].casefold() != output_endpoint.nets[0].casefold():
            continue
        if input_endpoint.electrical_type == output_endpoint.electrical_type == "output":
            continue

        reference = group.reference
        net = input_endpoint.nets[0]
        channel_label = (
            "SPI"
            if group.channel == "default"
            else f"SPI channel {group.channel.removeprefix('index')}"
        )
        source_evidence = SpiDataRolesSameNetEvidence(
            observed=observed,
            group=group,
            input_data=input_endpoint,
            output_data=output_endpoint,
            net=net,
        )
        findings.append(
            SpiSameNetCandidate.from_source_evidence(
                source_evidence,
                subject=f"{reference}: {channel_label} data-role pins share {net}",
                message=(
                    f"Fitted IC {reference} has controller-to-peripheral SPI data-role pin "
                    f"{input_endpoint.pin} ({input_endpoint.function}) and peripheral-to-controller "
                    f"data-role pin {output_endpoint.pin} ({output_endpoint.function}) on one "
                    f"schematic net ({net}); native pin types are {input_endpoint.electrical_type} "
                    f"and {output_endpoint.electrical_type}. Review whether this is intentional "
                    "loopback, single-wire operation, or a pin-assignment mistake. Function names "
                    "do not establish this IC's configured direction or the intended topology."
                ),
            )
        )
    return tuple(findings)
