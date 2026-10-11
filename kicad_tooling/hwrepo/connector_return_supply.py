"""Identify connector return pins assigned to recognized positive rails."""

from __future__ import annotations

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_identity import (
    connector_candidate_references,
    is_return_function,
    is_shield_function,
    pin_function_is_generic,
)
from .design_lint_types import Candidate
from .models import ConnectorCoverageReport, NetlistContract
from .resistor_paths import positive_power_nets


def return_pin_positive_rail_candidates(
    observed: NetlistContract,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Review connected return-role connector pins assigned to a recognized positive rail."""
    mapped_pins = source_matched_connector_pin_evidence(observed, connector_coverage)
    mapped_references = tuple(pin.rsplit(".", 1)[0] for pin in mapped_pins)
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(
            observed,
            (*reviewed_connector_references, *mapped_references),
        )
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    positive_nets = positive_power_nets(observed)
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin, set()).add(net)

    findings: list[Candidate] = []
    for pin in sorted(set(observed.pin_functions) | set(mapped_pins)):
        reference = pin.rsplit(".", 1)[0]
        if reference.casefold() not in connector_references:
            continue
        if reference.casefold() in dnp_references:
            continue

        function = observed.pin_functions.get(pin)
        if is_shield_function(function or ""):
            continue
        mapped = mapped_pins.get(pin)
        native_return = is_return_function(function or "")
        mapped_return = (
            mapped is not None and mapped.role == "return" and pin_function_is_generic(function)
        )
        if not native_return and not mapped_return:
            continue

        assigned_nets = tuple(sorted(nets_by_pin.get(pin, ())))
        if len(assigned_nets) != 1:
            continue
        net = assigned_nets[0]
        if net not in positive_nets:
            continue

        role_evidence = (
            f"native_function={function}"
            if native_return
            else (
                f"source_matched_interface_role=return;interface_pin={mapped.interface_pin_number};"
                f"signal={mapped.interface_signal}"
            )
        )
        findings.append(
            Candidate(
                rule_id="connector.return_pin_on_positive_rail",
                subject=f"{pin}: return assigned to {net}",
                message=(
                    "This connector pin is identified as a ground/return and is assigned to a "
                    "net recognized as a positive supply. Review the approved connector pinout "
                    "and net intent; native names and source-matched roles are review evidence, "
                    "not proof of electrical potential or required connectivity."
                ),
                evidence={
                    pin: (
                        role_evidence,
                        f"assigned_net={net}",
                        "positive_rail=recognized_by_net_name_or_attached_pin_function",
                    )
                },
            )
        )
    return tuple(findings)
