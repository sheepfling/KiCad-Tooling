"""Synthetic source-bound component peer power assignment support."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)

RULE_ID = "component.peer_power_pin_assignment_divergence"


def peer_power_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    symbols: dict[str, str] | None = None,
    part_ids: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
    supply_nets: tuple[str | None, ...] = ("+3V3", "+5V"),
    return_nets: tuple[str | None, ...] = ("GND", "AGND"),
    pin_functions: dict[str, tuple[str, str]] | None = None,
    pin_types: dict[str, tuple[str, str]] | None = None,
    incomplete_inventory: tuple[str, ...] = (),
    ambiguous_pins: tuple[str, ...] = (),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    if len(references) != len(supply_nets) or len(references) != len(return_nets):
        raise ValueError("Each component needs one supply and return assignment")
    symbols = symbols or {
        reference: f"Synthetic:PowerModuleAlias{index}"
        for index, reference in enumerate(references, start=1)
    }
    part_ids = part_ids or {}
    values = values or {}
    footprints = footprints or {}
    pin_functions = pin_functions or {reference: ("VDD", "GND") for reference in references}
    pin_types = pin_types or {reference: ("power_in", "power_in") for reference in references}
    components = {
        reference: ComponentContract(
            value=values.get(reference, "Synthetic power module"),
            footprint=footprints.get(reference, "Package:SyntheticPower"),
            part_id=part_ids.get(reference),
        )
        for reference in references
    }
    nets: dict[str, tuple[str, ...]] = {}
    for reference, supply_net, return_net in zip(references, supply_nets, return_nets, strict=True):
        for pin_number, net in (("1", supply_net), ("2", return_net)):
            pin = f"{reference}.{pin_number}"
            if net is not None:
                nets[net] = (*nets.get(net, ()), pin)
            if pin in ambiguous_pins:
                nets[f"ALSO_{pin}"] = (pin,)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers={
            reference: ("1", "2")
            for reference in references
            if reference not in incomplete_inventory
        },
        pin_functions={
            f"{reference}.{pin_number}": function
            for reference in references
            for pin_number, function in enumerate(pin_functions[reference], start=1)
        },
        pin_electrical_types={
            f"{reference}.{pin_number}": electrical_type
            for reference in references
            for pin_number, electrical_type in enumerate(pin_types[reference], start=1)
        },
    )


def lint_report(
    observed: NetlistContract, policy: DesignLintPolicy | None = None
) -> DesignLintReport:
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-peer-power-pin-assignment",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


def peer_pin_netlist_xml(observed: NetlistContract) -> str:
    root = ET.Element("export")
    components = ET.SubElement(root, "components")
    libparts: dict[tuple[str, str], dict[str, tuple[str, str]]] = {}
    for reference, component in sorted(observed.components.items()):
        library, part = observed.component_symbols[reference].split(":", maxsplit=1)
        entry = ET.SubElement(components, "comp", ref=reference)
        ET.SubElement(entry, "value").text = component.value
        ET.SubElement(entry, "footprint").text = component.footprint
        if component.part_id is not None:
            fields = ET.SubElement(entry, "fields")
            ET.SubElement(fields, "field", name="PART_ID").text = component.part_id
        ET.SubElement(entry, "libsource", lib=library, part=part)
        pins = ET.SubElement(ET.SubElement(ET.SubElement(entry, "units"), "unit", name="A"), "pins")
        libpart = libparts.setdefault((library, part), {})
        for number in observed.component_pin_numbers[reference]:
            ET.SubElement(pins, "pin", num=number)
            pin = f"{reference}.{number}"
            libpart[number] = (
                observed.pin_functions.get(pin, number),
                observed.pin_electrical_types.get(pin, "passive"),
            )

    libparts_element = ET.SubElement(root, "libparts")
    for (library, part), pins in sorted(libparts.items()):
        libpart = ET.SubElement(libparts_element, "libpart", lib=library, part=part)
        pin_elements = ET.SubElement(libpart, "pins")
        for number, (function, electrical_type) in sorted(pins.items()):
            ET.SubElement(
                pin_elements,
                "pin",
                num=number,
                name=function,
                type=electrical_type,
            )

    nets = ET.SubElement(root, "nets")
    for net_name, assignments in sorted(observed.nets.items()):
        net = ET.SubElement(nets, "net", name=net_name)
        for pin in assignments:
            reference, number = pin.rsplit(".", maxsplit=1)
            ET.SubElement(net, "node", ref=reference, pin=number)
    return ET.tostring(root, encoding="unicode")
