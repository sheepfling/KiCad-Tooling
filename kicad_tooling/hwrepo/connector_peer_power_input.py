"""Review named power-input assignments across connector symbol aliases."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .connector_peer_pin_scan import scan_connector_part_id_peer_pins
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.peer_power_input_open_assignment"


def connector_named_power_input_open_assignments(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[Candidate, ...]:
    """Review a named power-input contact open on one PART_ID symbol alias peer.

    The shared connector scan supplies fitted peers only after matching native
    PART_ID, value, footprint, complete pin inventory, and every pin's function
    and electrical type. This rule narrows that evidence to native ``power_in``
    pins with explicit, unrecognized functions. It reports only mixed
    assigned/open groups spanning distinct symbols; it does not require a
    common net.
    """
    found: list[Candidate] = []
    scan = scan_connector_part_id_peer_pins(
        observed,
        declared_references,
        peer_assignment_groups,
    )
    symbols_by_reference = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    for group in scan.pin_groups:
        function = group.pin_function.strip()
        if (
            group.pin_electrical_type.strip().casefold() != "power_in"
            or pin_function_is_generic(function)
            or is_named_supply_function(function)
            or is_return_function(function)
        ):
            continue

        references = {pin.rsplit(".", 1)[0].casefold() for pin in group.assignments}
        peer_symbols = tuple(
            sorted(
                {
                    symbols_by_reference[reference]
                    for reference in references
                    if reference in symbols_by_reference
                },
                key=lambda item: (item.casefold(), item),
            )
        )
        symbols = {symbol.casefold() for symbol in peer_symbols}
        if len(symbols) < 2:
            continue
        if any(len(nets) > 1 for nets in group.assignments.values()):
            continue
        assigned_pins = tuple(pin for pin, nets in group.assignments.items() if len(nets) == 1)
        open_pins = tuple(pin for pin, nets in group.assignments.items() if not nets)
        if not assigned_pins or not open_pins:
            continue

        evidence: dict[str, tuple[str, ...]] = {
            **group.assignments,
            "peer_identity_basis": ("part_id",),
            "peer_identity": (group.part_id,),
            "peer_symbols": peer_symbols,
            "pin_number": (group.pin_number,),
            "pin_function": (function,),
            "pin_electrical_type": (group.pin_electrical_type,),
            "assigned_peer_pins": assigned_pins,
            "open_peer_pins": open_pins,
        }
        if group.peer_assignment_group is not None:
            evidence["peer_assignment_group"] = (group.peer_assignment_group,)
            evidence["peer_assignment_basis"] = group.peer_assignment_basis

        found.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"PART_ID {group.part_id} pin {group.pin_number} ({function}): "
                    "named connector power-input peer assignment is open"
                ),
                message=(
                    "Fitted connector symbols sharing this native PART_ID use the same explicit, "
                    "unrecognized power_in pin function, but at least one peer is open while "
                    "another has one net assignment. Review the approved interface pinout for a "
                    "missing connection or an intentionally unused contact; matching part identity "
                    "and pin metadata do not establish that the contacts should share a net."
                ),
                evidence=evidence,
            )
        )
    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted(item.evidence)),
            ),
        )
    )
