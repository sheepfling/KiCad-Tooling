"""Review a fitted JTAG endpoint whose TCK and TMS share one schematic net."""

from __future__ import annotations

from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .jtag_signal_inventory import JtagEndpointInventory
from .netlist_contract_models import NetlistContract
from .return_nets import is_return_like_net_name

RULE_ID = "bus.jtag_tck_tms_same_net"
_TCK_ROLE = "test_clock"
_TMS_ROLE = "test_mode_select"


def jtag_tck_tms_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review a complete fitted IC whose unique JTAG clock and mode pins share a net.

    This is a protocol-role review cue. It does not establish that JTAG is
    active, or exclude an intentionally multiplexed or test-only pin assignment.
    """
    inventory = JtagEndpointInventory.from_netlist(observed)
    candidates: list[Candidate] = []
    for key in sorted(inventory.components):
        reference = inventory.reference_spellings.get(key)
        if reference is None or not is_integrated_circuit_reference(reference):
            continue
        pins = inventory.named_rail_signal_pins(reference)
        tck_pins = tuple(pin for pin in pins if pin.role == _TCK_ROLE)
        tms_pins = tuple(pin for pin in pins if pin.role == _TMS_ROLE)
        if len(tck_pins) != 1 or len(tms_pins) != 1:
            continue

        tck = tck_pins[0]
        tms = tms_pins[0]
        tck_nets = inventory.assignments.get(tck.pin.casefold(), frozenset())
        tms_nets = inventory.assignments.get(tms.pin.casefold(), frozenset())
        if len(tck_nets) != 1 or len(tms_nets) != 1:
            continue
        tck_net = next(iter(tck_nets))
        tms_net = next(iter(tms_nets))
        if (
            tck_net.casefold() != tms_net.casefold()
            or tck_net != tms_net
            or is_return_like_net_name(tck_net)
        ):
            continue

        tck_type = inventory.electrical_types[tck.pin.casefold()]
        tms_type = inventory.electrical_types[tms.pin.casefold()]
        if tck_type == "output" and tms_type == "output":
            continue

        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(f"{reference}: JTAG TCK {tck.pin} and TMS {tms.pin} share {tck_net}"),
                message=(
                    f"Fitted IC {reference} has native JTAG test-clock pin {tck.pin} "
                    f"({tck.function}) and test-mode-select pin {tms.pin} ({tms.function}) "
                    f"assigned to the same schematic net ({tck_net}). Review whether this "
                    "clock and mode-control connection is intentional. Pin functions and "
                    "schematic nets do not establish active debug use, device configuration, "
                    "or board copper continuity."
                ),
                evidence={
                    "component": (reference,),
                    "TCK_pin": (tck.pin,),
                    "TCK_function": (tck.function,),
                    "TCK_electrical_type": (tck_type,),
                    "TMS_pin": (tms.pin,),
                    "TMS_function": (tms.function,),
                    "TMS_electrical_type": (tms_type,),
                    "shared_net": (tck_net,),
                    "identity_basis": (tck.identity_basis, tms.identity_basis),
                },
            )
        )
    return tuple(candidates)
