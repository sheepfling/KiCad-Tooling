"""Review USB data pin functions against explicit data-net name polarity."""

from __future__ import annotations

from .bus_signal_pairs import usb_data_function_identity
from .design_lint_types import Candidate
from .design_lint_usb_data_polarity_candidate_evidence import (
    USB_DATA_POLARITY_RULE_ID,
    UsbDataPolarityCandidate,
    UsbDataPolarityFindingEvidence,
    usb_data_polarity_side,
)
from .netlist_contract_models import NetlistContract

RULE_ID = USB_DATA_POLARITY_RULE_ID


def usb_data_polarity_label_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find fitted USB data pins whose native function conflicts with a recognized net name."""
    pins_by_net: dict[str, set[str]] = {}
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pins_by_net.setdefault(net, set()).add(pin)
            nets_by_pin.setdefault(pin, set()).add(net)

    functions = {
        pin: identity
        for pin, function in observed.pin_functions.items()
        if (identity := usb_data_function_identity(function)) is not None
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for pin in sorted(functions):
        reference, separator, _number = pin.rpartition(".")
        if not separator or reference.casefold() in dnp_references:
            continue
        pin_identity = functions[pin]
        assigned_nets = nets_by_pin.get(pin, set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        net_identity = usb_data_function_identity(net)
        if net_identity is None or net_identity[0] != pin_identity[0]:
            continue
        if net_identity[1] == pin_identity[1]:
            continue

        # A same-symbol pair short is already handled by the complementary-pair rule.
        same_symbol_opposite = any(
            other_pin != pin
            and other_pin.rpartition(".")[0] == reference
            and identity == (pin_identity[0], net_identity[1])
            for other_pin in pins_by_net.get(net, ())
            if (identity := functions.get(other_pin)) is not None
        )
        if same_symbol_opposite:
            continue

        function = observed.pin_functions[pin]
        source_evidence = UsbDataPolarityFindingEvidence(
            observed=observed,
            pin=pin,
            function=function,
            pin_side=usb_data_polarity_side(pin_identity[1]),
            net=net,
            net_side=usb_data_polarity_side(net_identity[1]),
            port_group=pin_identity[0],
        )
        findings.append(
            UsbDataPolarityCandidate.from_source_evidence(
                source_evidence,
                subject=f"{pin}: {function} on {net}",
                message=(
                    f"Native USB data pin function is {pin_identity[1]}, but the assigned net name "
                    f"{net!r} identifies {net_identity[1]}. Review the endpoint pin map and net "
                    "labels; names alone do not prove physical polarity or routing."
                ),
            )
        )
    return tuple(findings)
