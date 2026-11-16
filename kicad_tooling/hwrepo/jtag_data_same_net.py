"""Review a fitted JTAG endpoint whose TDI and TDO share one schematic net."""

from __future__ import annotations

from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .jtag_signal_inventory import JtagEndpointInventory
from .netlist_contract_models import NetlistContract
from .return_nets import is_return_like_net_name

RULE_ID = "bus.jtag_tdi_tdo_same_net"
_TDI_ROLE = "test_data_in"
_TDO_ROLE = "test_data_out"


def jtag_tdi_tdo_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review one complete fitted IC whose unique JTAG data pins share a net.

    Native functions identify the two roles only when the endpoint inventory
    independently identifies JTAG. The prompt does not establish that JTAG is
    active or that a loopback assignment is invalid.
    """
    inventory = JtagEndpointInventory.from_netlist(observed)
    candidates: list[Candidate] = []
    for key in sorted(inventory.components):
        reference = inventory.reference_spellings.get(key)
        if reference is None or not is_integrated_circuit_reference(reference):
            continue
        pins = inventory.named_rail_signal_pins(reference)
        tdi_pins = tuple(pin for pin in pins if pin.role == _TDI_ROLE)
        tdo_pins = tuple(pin for pin in pins if pin.role == _TDO_ROLE)
        if len(tdi_pins) != 1 or len(tdo_pins) != 1:
            continue

        tdi = tdi_pins[0]
        tdo = tdo_pins[0]
        tdi_nets = inventory.assignments.get(tdi.pin.casefold(), frozenset())
        tdo_nets = inventory.assignments.get(tdo.pin.casefold(), frozenset())
        if len(tdi_nets) != 1 or len(tdo_nets) != 1:
            continue
        tdi_net = next(iter(tdi_nets))
        tdo_net = next(iter(tdo_nets))
        if (
            tdi_net.casefold() != tdo_net.casefold()
            or tdi_net != tdo_net
            or is_return_like_net_name(tdi_net)
        ):
            continue

        tdi_type = inventory.electrical_types[tdi.pin.casefold()]
        tdo_type = inventory.electrical_types[tdo.pin.casefold()]
        if tdi_type == "output" and tdo_type == "output":
            continue

        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(f"{reference}: JTAG TDI {tdi.pin} and TDO {tdo.pin} share {tdi_net}"),
                message=(
                    f"Fitted IC {reference} has native JTAG test-data-in pin {tdi.pin} "
                    f"({tdi.function}) and test-data-out pin {tdo.pin} ({tdo.function}) "
                    f"assigned to the same schematic net ({tdi_net}). Review whether this "
                    "loopback is intentional. Pin functions and schematic nets do not establish "
                    "debug use, scan-chain topology, or board copper continuity."
                ),
                evidence={
                    "component": (reference,),
                    "TDI_pin": (tdi.pin,),
                    "TDI_function": (tdi.function,),
                    "TDI_electrical_type": (tdi_type,),
                    "TDO_pin": (tdo.pin,),
                    "TDO_function": (tdo.function,),
                    "TDO_electrical_type": (tdo_type,),
                    "shared_net": (tdi_net,),
                    "identity_basis": (tdi.identity_basis, tdo.identity_basis),
                },
            )
        )
    return tuple(candidates)
