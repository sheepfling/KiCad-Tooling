"""Review shared JTAG test-data outputs from fitted IC endpoints."""

from __future__ import annotations

import re

from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .jtag_signal_inventory import JtagEndpointInventory, jtag_signal_roles
from .netlist_contract_models import NetlistContract
from .signal_pair_output_sharing import signal_output_sharing_groups

RULE_ID = "bus.jtag_tdo_outputs_share_net"
_TDO_FUNCTIONS = frozenset({"tdo", "jtagtdo", "tdojtag"})
_TDO_ROLE = frozenset({"test_data_out"})


def jtag_tdo_output_role(_reference: str, function: str) -> tuple[str, str] | None:
    """Recognize only exact JTAG TDO aliases, excluding compound mux names."""
    normalized = re.sub(r"[^a-z0-9]", "", function.casefold())
    if normalized not in _TDO_FUNCTIONS or jtag_signal_roles(function) != _TDO_ROLE:
        return None
    return "jtag_tdo", "jtag-tap"


def jtag_tdo_outputs_share_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review fitted JTAG IC TDO pins sharing one exact, non-return net."""
    inventory = JtagEndpointInventory.from_netlist(observed)
    endpoint_pins: dict[str, frozenset[str]] = {}

    def role_and_channel(reference: str, function: str) -> tuple[str, str] | None:
        if not is_integrated_circuit_reference(reference):
            return None
        selected_role = jtag_tdo_output_role(reference, function)
        if selected_role is None:
            return None
        reference_key = reference.casefold()
        if reference_key not in endpoint_pins:
            endpoint_pins[reference_key] = frozenset(
                pin.pin.casefold()
                for pin in inventory.named_rail_signal_pins(reference)
                if pin.role == "test_data_out"
            )
        return selected_role if endpoint_pins[reference_key] else None

    groups = signal_output_sharing_groups(
        observed,
        role_and_channel=role_and_channel,
        expected_role="jtag_tdo",
        is_supported_reference=is_integrated_circuit_reference,
        require_pin_inventory=True,
        skip_return_like_nets=True,
        exclude_nets_with_incomplete_evidence=True,
    )
    findings: list[Candidate] = []
    for group in groups:
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{', '.join(group.components)}: JTAG TDO outputs share {group.net}",
                message=(
                    f"Fitted JTAG IC test-data-out pins {', '.join(group.pins)} share one "
                    f"schematic net ({group.net}) with native pin types "
                    f"{', '.join(group.pin_types)}. Review whether a mux or selected debug "
                    "topology makes the shared assignment intentional. Pin names and schematic "
                    "nets do not establish active output behavior or board copper continuity."
                ),
                evidence={
                    "components": group.components,
                    "functions": group.functions,
                    "pins": group.pins,
                    "pin_types": group.pin_types,
                    "net": (group.net,),
                },
            )
        )
    return tuple(findings)
