"""Review native SPI data-pin functions against explicit net labels."""

from __future__ import annotations

from .design_lint_signal_label_role_candidate_evidence import (
    SignalLabelRoleMismatchCandidate,
    SpiDataLabelRoleMismatchEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .spi_participants import spi_data_label_role

RULE_ID = "bus.spi_data_polarity_label_mismatch"


def spi_data_polarity_label_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find fitted SPI data pins whose native function conflicts with a recognized net name."""
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin, set()).add(net)

    functions = {
        pin: role
        for pin, function in observed.pin_functions.items()
        if (role := spi_data_label_role(function)) is not None
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for pin in sorted(functions):
        reference, separator, _number = pin.rpartition(".")
        if not separator or reference.casefold() in dnp_references:
            continue
        assigned_nets = nets_by_pin.get(pin, set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        net_role = spi_data_label_role(net)
        pin_role = functions[pin]
        if net_role is None or net_role == pin_role:
            continue

        function = observed.pin_functions[pin]
        findings.append(
            SignalLabelRoleMismatchCandidate.from_source_evidence(
                SpiDataLabelRoleMismatchEvidence(
                    observed=observed,
                    pin=pin,
                    pin_function=function,
                    pin_role=pin_role,
                    net=net,
                    net_role=net_role,
                ),
                subject=f"{pin}: {function} on {net}",
                message=(
                    f"Native SPI data-pin function is {pin_role}, but the assigned net name "
                    f"{net!r} identifies {net_role}. Review the part-specific interface "
                    "naming and endpoint map; names alone do not establish bus intent or routing."
                ),
            )
        )
    return tuple(findings)
