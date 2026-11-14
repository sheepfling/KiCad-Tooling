"""Review fitted enable inputs assigned to explicit return-like net labels."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_power_control_return_evidence import EnableControlReturnEvidence
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .return_nets import is_return_like_net_name, is_vss_prefixed_net_name


def enable_control_tied_to_return_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review exact simple EN/ENABLE inputs on return-like labels.

    The native function string is deliberately limited to ``EN`` and ``ENABLE``.
    Polarity-marked or compound functions are excluded because names alone do not
    establish their active state. VSS-prefixed labels are also excluded because
    VSS can identify a negative supply rather than a return domain.
    """
    dnp = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin = netlist_pin_net_index(observed)
    candidates: list[PowerCandidate] = []
    for pin, function in sorted(
        observed.pin_functions.items(), key=lambda item: item[0].casefold()
    ):
        if lookup_unique_casefold(observed.pin_functions, pin) != function:
            continue
        if function.strip().casefold() not in {"en", "enable"}:
            continue
        reference, separator, _ = pin.rpartition(".")
        if not separator or reference.startswith("#") or reference.casefold() in dnp:
            continue
        if lookup_unique_casefold(observed.components, reference) is None:
            continue
        if lookup_unique_casefold(observed.pin_electrical_types, pin) != "input":
            continue
        assigned_nets = nets_by_pin.get(pin.casefold(), set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        if not is_return_like_net_name(net) or is_vss_prefixed_net_name(net):
            continue
        source = EnableControlReturnEvidence(
            observed=observed,
            pin=pin,
            function=function,
            net=net,
        )
        candidates.append(
            PowerCandidate.from_source_evidence(
                source,
                subject=f"{pin}: {function} control input assigned to {net}",
                message=(
                    "This fitted native input has a simple enable-like function and is assigned "
                    "to a return-like schematic net label. Review whether holding this control "
                    "at the label-indicated level is intentional. The pin name and net label do "
                    "not establish active polarity, logic state, component behavior, or required "
                    "connectivity; a deliberately fixed or isolated control may be valid."
                ),
            )
        )
    return tuple(candidates)
