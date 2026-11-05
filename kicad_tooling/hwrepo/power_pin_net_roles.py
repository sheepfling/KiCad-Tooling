"""Review named power-pin functions assigned to conflicting named net roles."""

from __future__ import annotations

from .connector_identity import (
    connector_candidate_references,
    is_return_function,
    power_function_key,
)
from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_power_pin_role_evidence import (
    NamedPowerPinNetRoleConflictEvidence,
    opposite_net_role_sources,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index


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
    nets_by_pin = netlist_pin_net_index(observed)

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
        role_sources = opposite_net_role_sources(
            observed,
            net,
            role=opposite_role,
            exclude_pin=pin,
        )
        if not role_sources:
            continue
        source = NamedPowerPinNetRoleConflictEvidence(
            observed=observed,
            pin=pin,
            function=function,
            net=net,
            reviewed_connector_references=reviewed_connector_references,
            opposite_role_sources=role_sources,
        )
        findings.append(
            PowerCandidate.from_source_evidence(
                source,
                subject=f"{pin}: {function} pin assigned to {net}",
                message=(
                    "This component pin's named power or return function appears to conflict "
                    "with the assigned net's recognized name or another pin function. Review "
                    "the approved symbol pinout and rail intent; these names are review clues, "
                    "not proof of electrical potential or required connectivity."
                ),
            )
        )
    return tuple(findings)
