"""Review a supported transformer winding whose terminals share one net."""

from __future__ import annotations

from types import MappingProxyType

from .design_lint_component_transformer_candidate_evidence import (
    TransformerCandidate,
    TransformerWindingGroupsShareNetEvidence,
    TransformerWindingSameNetEvidence,
)
from .design_lint_component_transformer_models import (
    SupportedTransformerObservation,
    TransformerPinNetAssignment,
    TransformerWindingPinGroup,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

_SUPPORTED_WINDINGS = MappingProxyType(
    {
        "transformer:transf1": (
            TransformerWindingPinGroup(name="winding_1", pin_numbers=("1", "2")),
            TransformerWindingPinGroup(name="winding_2", pin_numbers=("3", "4")),
        )
    }
)


def _supported_transformers(
    observed: NetlistContract,
) -> tuple[SupportedTransformerObservation, ...]:
    """Return exact, fitted TRANSF1 records with complete unambiguous pin nets."""
    dnp = {reference.casefold() for reference in observed.dnp_components}
    component_by_reference = {
        reference.casefold(): component for reference, component in observed.components.items()
    }
    pins_by_reference = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    transformers: list[SupportedTransformerObservation] = []
    for reference, symbol in observed.component_symbols.items():
        reference_key = reference.casefold()
        winding_groups = _SUPPORTED_WINDINGS.get(symbol.casefold())
        component = component_by_reference.get(reference_key)
        pin_numbers = pins_by_reference.get(reference_key)
        if (
            winding_groups is None
            or reference_key in dnp
            or component is None
            or pin_numbers is None
            or len(pin_numbers) != 4
            or {number.casefold() for number in pin_numbers} != {"1", "2", "3", "4"}
        ):
            continue

        assigned_nets = {
            number: nets_by_pin.get(f"{reference}.{number}".casefold(), set())
            for number in ("1", "2", "3", "4")
        }
        if any(len(nets) != 1 for nets in assigned_nets.values()):
            continue
        transformers.append(
            SupportedTransformerObservation(
                observed=observed,
                reference=reference,
                symbol=symbol,
                value=component.value,
                winding_groups=winding_groups,
                pin_assignments=tuple(
                    TransformerPinNetAssignment(
                        pin_number=number,
                        net=next(iter(assigned_nets[number])),
                    )
                    for number in ("1", "2", "3", "4")
                ),
            )
        )
    return tuple(transformers)


def transformer_winding_same_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Return review candidates for complete TRANSF1 windings assigned to one net.

    The allowlist is deliberately exact. KiCad 10.0.5 defines TRANSF1 as a
    four-terminal symbol with winding pin groups 1/2 and 3/4; other symbols
    need their own reviewed pin-group definition.
    """
    found: list[Candidate] = []
    for transformer in _supported_transformers(observed):
        pin_nets = {item.pin_number: item.net for item in transformer.pin_assignments}
        for winding in transformer.winding_groups:
            first_net = pin_nets[winding.pin_numbers[0]]
            second_net = pin_nets[winding.pin_numbers[1]]
            if first_net != second_net:
                continue
            source_evidence = TransformerWindingSameNetEvidence(
                transformer=transformer,
                winding=winding,
                net=first_net,
            )
            found.append(
                TransformerCandidate.from_source_evidence(
                    source_evidence,
                    subject=(
                        f"{transformer.reference}: {winding.name.replace('_', ' ')} pins "
                        f"{winding.pin_numbers[0]}/{winding.pin_numbers[1]} "
                        f"share {first_net}"
                    ),
                    message=(
                        f"The supported TRANSF1 {winding.name.replace('_', ' ')} terminals are assigned to "
                        "one native schematic net, leaving no netlist voltage across that "
                        "winding. Review whether this is intentional or a connection is missing. "
                        "This prompt does not establish transformer operation, isolation rating, "
                        "winding polarity, physical connectivity, copper continuity, or assembly "
                        "state."
                    ),
                )
            )
    return tuple(sorted(found, key=lambda item: (item.subject.casefold(), item.subject)))


def transformer_winding_groups_share_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review a native schematic net shared by both exact TRANSF1 winding groups."""
    found: list[Candidate] = []
    for transformer in _supported_transformers(observed):
        first_group = transformer.winding_groups[0]
        second_group = transformer.winding_groups[1]
        assignments_by_number = {item.pin_number: item for item in transformer.pin_assignments}
        first_nets = {assignments_by_number[number].net for number in first_group.pin_numbers}
        second_nets = {assignments_by_number[number].net for number in second_group.pin_numbers}
        for net in sorted(first_nets & second_nets, key=str.casefold):
            first_assignments = tuple(
                assignments_by_number[number]
                for number in first_group.pin_numbers
                if assignments_by_number[number].net == net
            )
            second_assignments = tuple(
                assignments_by_number[number]
                for number in second_group.pin_numbers
                if assignments_by_number[number].net == net
            )
            source_evidence = TransformerWindingGroupsShareNetEvidence(
                transformer=transformer,
                net=net,
                first_winding=first_group,
                second_winding=second_group,
                first_pin_assignments=first_assignments,
                second_pin_assignments=second_assignments,
            )
            found.append(
                TransformerCandidate.from_source_evidence(
                    source_evidence,
                    subject=(f"{transformer.reference}: winding groups share {net}"),
                    message=(
                        "Both supported TRANSF1 winding groups touch this native schematic net, "
                        "so those sides are not isolated in the netlist. Review whether the "
                        "cross-winding connection is intentional. This prompt does not infer "
                        "whether isolation is required or approved, or establish transformer "
                        "operation, physical connectivity, copper continuity, or assembly state."
                    ),
                )
            )
    return tuple(sorted(found, key=lambda item: (item.subject.casefold(), item.subject)))
