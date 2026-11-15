"""Review recognized JTAG signal pins assigned directly to named rails."""

from __future__ import annotations

from .design_lint_named_rail_candidate_evidence import (
    JtagSignalNamedRailEvidence,
    NamedRailSignalCandidate,
)
from .design_lint_rule_types import DesignLintRuleId
from .jtag_signal_inventory import JtagEndpointInventory
from .named_rail_pin_evidence import (
    NamedRailPinSource,
    assigned_named_rail_connector_pins,
    assigned_named_rail_ic_pins,
)
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.jtag_signal_on_named_rail"


def jtag_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[NamedRailSignalCandidate, ...]:
    """Review fitted JTAG signal pins whose assigned labels resemble power rails."""
    inventory = JtagEndpointInventory.from_netlist(observed)
    pins = (*assigned_named_rail_ic_pins(observed), *assigned_named_rail_connector_pins(observed))
    roles_by_pin = {
        item.pin.casefold(): item
        for reference in sorted({pin.reference for pin in pins}, key=str.casefold)
        for item in inventory.named_rail_signal_pins(reference)
    }
    candidates: list[NamedRailSignalCandidate] = []
    for pin in pins:
        identity = roles_by_pin.get(pin.pin.casefold())
        if identity is None:
            continue
        source = JtagSignalNamedRailEvidence(
            pin=NamedRailPinSource(observed=observed, evidence=pin),
            role=identity.role,
            identity_basis=identity.identity_basis,
        )
        candidates.append(
            NamedRailSignalCandidate.from_source_evidence(
                source,
                subject=f"{pin.pin}: {pin.function} on {pin.rail_role} net {pin.net_name}",
                message=(
                    f"Native JTAG {identity.role.replace('_', ' ')} function {pin.function!r} "
                    f"is assigned to a net whose label is recognized as {pin.rail_role} "
                    f"({pin.net_name!r}); endpoint identity comes from {identity.identity_basis}. "
                    "Review whether this is intentional or a pin-assignment issue. Function "
                    "text and net labels do not prove an active JTAG interface, electrical "
                    "potential, required bus membership, or a defect; PCB copper and physical "
                    "continuity are not assessed."
                ),
            )
        )
    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
