"""Synthetic source factory for guarded connector PART_ID peer tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)

PART_ID_PEER_PIN_OUTLIER_RULE_ID = "connector.peer_pin_assignment_outlier"
PART_ID_PEER_PIN_DIVERGENCE_RULE_ID = "connector.peer_pin_assignment_divergence"
NETLIST_SHA256 = "b" * 64


def connector_netlist(
    *,
    references: tuple[str, ...] = ("J1", "J2"),
    symbols: dict[str, str] | None = None,
    part_ids: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
    pin_two_nets: tuple[str | None, ...] = ("GND", None),
    pin_functions: dict[str, str | None] | None = None,
    pin_electrical_types: dict[str, str | None] | None = None,
    pin_inventories: dict[str, tuple[str, ...] | None] | None = None,
    ambiguous_pin: str | None = None,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    if len(references) != len(pin_two_nets):
        raise ValueError("Each connector needs one pin-two net case")
    symbols = symbols or {
        reference: f"Synthetic:PortAlias{index}"
        for index, reference in enumerate(references, start=1)
    }
    part_ids = (
        {reference: "SYNTHETIC-PORT-001" for reference in references}
        if part_ids is None
        else part_ids
    )
    values = values or {reference: "Synthetic two-contact port" for reference in references}
    footprints = footprints or {reference: "Synthetic:Port_2x1" for reference in references}
    pin_functions = pin_functions or {
        f"{reference}.{number}": f"Pin_{number}"
        for reference in references
        for number in ("1", "2")
    }
    pin_electrical_types = pin_electrical_types or {
        f"{reference}.{number}": "passive" for reference in references for number in ("1", "2")
    }
    pin_inventories = pin_inventories or {reference: ("1", "2") for reference in references}

    nets: dict[str, tuple[str, ...]] = {"DATA": tuple(f"{reference}.1" for reference in references)}
    for reference, net in zip(references, pin_two_nets, strict=True):
        if net is not None:
            nets[net] = (*nets.get(net, ()), f"{reference}.2")
    if ambiguous_pin is not None:
        nets["ALSO_ASSIGNED"] = (*nets.get("ALSO_ASSIGNED", ()), ambiguous_pin)

    components = {
        reference: ComponentContract(
            value=values.get(reference, "Synthetic two-contact port"),
            footprint=footprints.get(reference, "Synthetic:Port_2x1"),
            part_id=part_ids.get(reference),
        )
        for reference in references
    }
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions={
            pin: function for pin, function in pin_functions.items() if function is not None
        },
        pin_electrical_types={
            pin: electrical_type
            for pin, electrical_type in pin_electrical_types.items()
            if electrical_type is not None
        },
        component_pin_numbers={
            reference: inventory
            for reference, inventory in pin_inventories.items()
            if inventory is not None
        },
    )


def lint_report(
    observed: NetlistContract, policy: DesignLintPolicy | None = None
) -> DesignLintReport:
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-connector-part-id-peers",
        observed=observed,
        netlist_sha256=NETLIST_SHA256,
    )
    return evaluate("synthetic-connector-part-id-peers", coach, policy or DesignLintPolicy())
