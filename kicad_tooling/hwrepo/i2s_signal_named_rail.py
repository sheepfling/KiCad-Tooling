"""Review recognized I2S pins assigned directly to named rails."""

from __future__ import annotations

from .design_lint_named_rail_candidate_evidence import (
    I2sSignalNamedRailEvidence,
    NamedRailSignalCandidate,
)
from .i2s_endpoint_inventory import I2sEndpointInventory
from .named_rail_pin_evidence import (
    NamedRailPinSource,
    assigned_named_rail_connector_pins,
    assigned_named_rail_ic_pins,
)
from .netlist_contract_models import NetlistContract


def i2s_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[NamedRailSignalCandidate, ...]:
    """Review fitted I2S signal pins whose assigned labels resemble power rails."""
    inventory = I2sEndpointInventory.from_netlist(observed)
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
        source = I2sSignalNamedRailEvidence(
            pin=NamedRailPinSource(observed=observed, evidence=pin),
            role=identity.role,
            identity_basis=identity.identity_basis,
        )
        candidates.append(
            NamedRailSignalCandidate.from_source_evidence(
                source,
                subject=f"{pin.pin}: {pin.function} on {pin.rail_role} net {pin.net_name}",
                message=(
                    f"Native I2S {identity.role.replace('_', ' ')} function {pin.function!r} "
                    f"is assigned to a net whose label is recognized as {pin.rail_role} "
                    f"({pin.net_name!r}); endpoint identity comes from {identity.identity_basis}. "
                    "Review whether this is intentional or a pin-assignment issue. Function "
                    "text and net labels do not prove I2S use, electrical potential, required "
                    "bus membership, or a defect; PCB copper and physical continuity are not assessed."
                ),
            )
        )
    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
