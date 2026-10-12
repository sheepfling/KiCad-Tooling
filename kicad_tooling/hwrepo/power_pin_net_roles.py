"""Review named power-pin functions assigned to conflicting named net roles."""

from __future__ import annotations

from typing import Literal

from .connector_identity import (
    connector_candidate_references,
    is_return_function,
    power_function_key,
)
from .design_lint_types import Candidate
from .models import NetlistContract
from .return_nets import is_return_like_net_name


def _net_role_sources(
    observed: NetlistContract,
    net: str,
    *,
    role: Literal["return", "positive"],
    exclude_pin: str,
) -> tuple[str, ...]:
    """Return bounded label and peer-pin evidence for one apparent net role."""
    if role == "return":
        if power_function_key(net) is not None:
            return ()
        if is_return_like_net_name(net):
            return ("net_name=return_like",)
        matches = tuple(
            sorted(
                f"{pin}:native_function={observed.pin_functions[pin]}"
                for pin in observed.nets.get(net, ())
                if pin.casefold() != exclude_pin.casefold()
                and is_return_function(observed.pin_functions.get(pin, ""))
            )
        )
        return matches
    if is_return_like_net_name(net):
        return ()
    if power_function_key(net) is not None:
        return (f"net_name=positive_supply:{power_function_key(net)}",)
    matches = tuple(
        sorted(
            f"{pin}:native_function={observed.pin_functions[pin]}"
            for pin in observed.nets.get(net, ())
            if pin.casefold() != exclude_pin.casefold()
            and power_function_key(observed.pin_functions.get(pin, "")) is not None
        )
    )
    return matches


def named_power_pin_net_role_conflicts(
    observed: NetlistContract,
    *,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Prompt review when a named power pin conflicts with its assigned net role.

    Positive-supply pin functions on return-like nets and return pin functions on
    positive-supply nets are recognized from native names only. A recognized net
    label takes precedence over peer pin functions; peer functions classify only
    otherwise unnamed rails. The target pin's function is excluded when collecting
    peer evidence, so it cannot classify its own net. This remains a review hint;
    labels and symbol pin functions do not establish electrical potential or intent.
    """
    connectors = {
        reference.casefold()
        for reference in connector_candidate_references(
            observed,
            reviewed_connector_references,
        )
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    findings: list[Candidate] = []
    for pin, function in sorted(observed.pin_functions.items()):
        reference = pin.rsplit(".", 1)[0]
        if reference.startswith("#") or reference.casefold() in dnp:
            continue
        supply_key = power_function_key(function)
        is_return = is_return_function(function)
        if is_return and reference.casefold() in connectors:
            # The connector-specific rule also honors complete project interface maps.
            continue
        if supply_key is None and not is_return:
            continue
        assigned_nets = nets_by_pin.get(pin.casefold(), set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        opposite_role = "return" if supply_key is not None else "positive"
        role_sources = _net_role_sources(
            observed,
            net,
            role=opposite_role,
            exclude_pin=pin,
        )
        if not role_sources:
            continue
        pin_role = f"positive_supply:{supply_key}" if supply_key is not None else "return"
        findings.append(
            Candidate(
                rule_id="power.pin_function_net_role_conflict",
                subject=f"{pin}: {function} pin assigned to {net}",
                message=(
                    "This component pin's named power or return function appears to conflict "
                    "with the assigned net's recognized name or another pin function. Review "
                    "the approved symbol pinout and rail intent; these names are review clues, "
                    "not proof of electrical potential or required connectivity."
                ),
                evidence={
                    pin: (f"native_function={function}", f"pin_role={pin_role}"),
                    "assigned_net": (net,),
                    "opposite_net_role_sources": role_sources,
                },
            )
        )
    return tuple(findings)
