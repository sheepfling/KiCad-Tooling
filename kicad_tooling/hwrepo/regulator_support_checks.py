"""Compare authored active regulator-support pin roles with native metadata."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .netlist_contract_models import NetlistContract
from .regulator_component_checks import regulator_component_identity_issues
from .regulator_support_models import RegulatorSupportPinRoleMap


def regulator_support_pin_role_issues(
    requirements: RegulatorSupportPinRoleMap,
    observed: NetlistContract,
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Return exact identity, inventory, or authored pin-role mismatches."""
    results: list[tuple[str, str, tuple[str, ...]]] = []
    for topology in requirements.requirements:
        for component in topology.components:
            issues = list(regulator_component_identity_issues(component, observed))
            if not issues:
                for pin in component.pins:
                    if pin.expected_function is not None:
                        actual = lookup_unique_casefold(observed.pin_functions, pin.pin)
                        if actual is None:
                            issues.append(
                                f"{pin.pin} native pin function is unavailable or ambiguous"
                            )
                        elif actual.casefold() != pin.expected_function.casefold():
                            issues.append(
                                f"{pin.pin} native function is {actual!r}; "
                                f"expected {pin.expected_function!r}"
                            )
                    if pin.expected_electrical_type is not None:
                        actual = lookup_unique_casefold(observed.pin_electrical_types, pin.pin)
                        if actual is None:
                            issues.append(
                                f"{pin.pin} native electrical type is unavailable or ambiguous"
                            )
                        elif actual.casefold() != pin.expected_electrical_type.casefold():
                            issues.append(
                                f"{pin.pin} native electrical type is {actual!r}; "
                                f"expected {pin.expected_electrical_type!r}"
                            )
            if issues:
                results.append(
                    (
                        topology.id,
                        component.reference,
                        tuple(sorted(issues, key=str.casefold)),
                    )
                )
    return tuple(sorted(results, key=lambda item: (item[0].casefold(), item[1].casefold())))
