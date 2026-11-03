"""Parse native KiCad reports and netlists into typed evidence."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, cast

from pydantic import JsonValue

from .connector_pins import similar_connector_pin_groups
from .kicad_compatibility import require_cli_profile
from .models import NetlistContract
from .project_models import (
    ComponentContract,
    PcbValidationContract,
    ProjectConfig,
    ProjectKind,
    SchematicValidationContract,
)
from .return_nets import return_net_groups


def _mapping(value: JsonValue, label: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, dict):
        raise TypeError(f"{label}: expected object")
    return cast(Mapping[str, JsonValue], value)


def _sequence(value: JsonValue, label: str) -> tuple[JsonValue, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{label}: expected list")
    return tuple(cast(list[JsonValue], value))


def check_report(
    path: Path,
    kind: Literal["erc", "drc"],
    config: ProjectConfig | None = None,
) -> int:
    """Adapter: parse a third-party KiCad report to one typed count."""
    decoded: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    data = _mapping(decoded, "KiCad report")
    version = data.get("kicad_version")
    if not isinstance(version, str) or not version:
        raise ValueError("Missing KiCad report identity")
    if config is not None:
        require_cli_profile(config)
        if version != config.kicad_version:
            raise ValueError("Report toolchain identity differs")
        if data.get("$schema") != f"https://schemas.kicad.org/{kind}.v1.json":
            raise ValueError("Unexpected report schema")
        if data.get("included_severities") != ["error", "warning", "exclusion"]:
            raise ValueError("Report must include errors, warnings and exclusions")
        ignored = _sequence(data.get("ignored_checks"), "ignored-check inventory")
        keys = tuple(str(_mapping(item, "ignored check").get("key", "")) for item in ignored)
        expected = (
            config.validation.expected_ignored_checks.erc
            if kind == "erc"
            else config.validation.expected_ignored_checks.drc
        )
        if sorted(keys) != sorted(expected):
            raise ValueError(f"Disabled-check inventory changed: {keys}")
    if kind == "erc":
        sheets = _sequence(data.get("sheets"), "ERC sheets")
        if not sheets:
            raise ValueError("Missing ERC sheets")
        findings = tuple(
            _sequence(_mapping(sheet, "ERC sheet").get("violations"), "ERC findings")
            for sheet in sheets
        )
    else:
        drc_categories = ("violations", "unconnected_items")
        if config is None or config.kind is not ProjectKind.PCB_ONLY:
            drc_categories += ("schematic_parity",)
        findings = tuple(_sequence(data.get(key), f"DRC {key}") for key in drc_categories)
    return sum(len(items) for items in findings)


def native_report_examples(path: Path, kind: str) -> tuple[str, ...]:
    """Read a few rule descriptions from KiCad JSON for the repair coach."""
    try:
        data = _mapping(json.loads(path.read_text(encoding="utf-8")), "KiCad report")
        if kind == "erc":
            sheets = _sequence(data.get("sheets"), "ERC sheets")
            groups = tuple(
                _sequence(_mapping(sheet, "ERC sheet").get("violations"), "ERC findings")
                for sheet in sheets
            )
        else:
            groups = tuple(
                _sequence(data.get(key), f"DRC {key}")
                for key in ("violations", "unconnected_items", "schematic_parity")
                if data.get(key) is not None
            )
        examples: list[str] = []
        for group in groups:
            for item in group:
                record = _mapping(item, "KiCad finding")
                rule, description = record.get("type"), record.get("description")
                if isinstance(rule, str) and isinstance(description, str):
                    examples.append(f"{rule}: {description}")
                if len(examples) == 3:
                    return tuple(examples)
        return tuple(examples)
    except (OSError, ValueError, TypeError):
        return ()


def read_netlist(path: Path) -> NetlistContract:
    """Parse actual KiCad names, including hierarchical nets and unassigned footprints."""
    tree = ET.parse(path).getroot()
    library_pins: dict[tuple[str, str], dict[str, str]] = {}
    library_pin_types: dict[tuple[str, str], dict[str, str]] = {}
    library_pin_numbers: dict[tuple[str, str], tuple[str, ...]] = {}
    for part in tree.findall("./libparts/libpart"):
        identity = (part.get("lib", ""), part.get("part", ""))
        if all(identity):
            library_elements = part.findall("./pins/pin")
            library_pins[identity] = {
                pin.attrib["num"]: name
                for pin in library_elements
                if "num" in pin.attrib
                if (name := pin.get("name", "").strip()) and name != "~"
            }
            library_pin_numbers[identity] = tuple(
                sorted({pin.attrib["num"] for pin in library_elements if pin.get("num")})
            )
            library_pin_types[identity] = {
                pin.attrib["num"]: pin.get("type", "").strip().casefold()
                for pin in library_elements
                if pin.get("num") and pin.get("type", "").strip()
            }
    components: dict[str, ComponentContract] = {}
    dnp_components: list[str] = []
    component_symbols: dict[str, str] = {}
    pin_functions: dict[str, str] = {}
    pin_electrical_types: dict[str, str] = {}
    component_pin_numbers: dict[str, tuple[str, ...]] = {}
    for comp in tree.findall("./components/comp"):
        ref = comp.attrib["ref"]
        if ref in components:
            raise ValueError("Duplicate reference in netlist")
        dnp_properties = comp.findall("./property[@name='dnp']")
        if len(dnp_properties) > 1:
            raise ValueError(f"Repeated native dnp property at {ref}")
        if dnp_properties:
            property_ = dnp_properties[0]
            if len(property_):
                raise ValueError(f"Nested native dnp property at {ref}")
            dnp_value = property_.get("value", property_.text or "").strip().casefold()
            if dnp_value not in {"", "true", "yes", "1"}:
                raise ValueError(f"Ambiguous native dnp property at {ref}")
            dnp_components.append(ref)
        components[ref] = ComponentContract(
            value=comp.findtext("value", ""),
            footprint=comp.findtext("footprint", ""),
            part_id=comp.findtext("./fields/field[@name='PART_ID']") or None,
        )
        source = comp.find("libsource")
        if source is not None:
            identity = (source.get("lib", ""), source.get("part", ""))
            if all(identity):
                component_symbols[ref] = ":".join(identity)
                available = library_pins.get(identity, {})
                available_types = library_pin_types.get(identity, {})
                numbers = set(library_pin_numbers.get(identity, ()))
                numbers.update(
                    pin.attrib["num"]
                    for pin in comp.findall("./units/unit/pins/pin")
                    if pin.get("num")
                )
                component_pin_numbers[ref] = tuple(sorted(numbers))
                for number in sorted(numbers):
                    if function := available.get(number):
                        pin_functions[f"{ref}.{number}"] = function
                    if electrical_type := available_types.get(number):
                        pin_electrical_types[f"{ref}.{number}"] = electrical_type
    nets: dict[str, tuple[str, ...]] = {}
    for net in tree.findall("./nets/net"):
        name = net.attrib["name"].lstrip("/")
        if name in nets:
            raise ValueError("Duplicate normalized net name")
        pins: list[str] = []
        for node in net.findall("node"):
            pin = f"{node.attrib['ref']}.{node.attrib['pin']}"
            pins.append(pin)
            if pin not in pin_functions and (function := node.get("pinfunction", "")):
                normalized = function.removesuffix(f"_{node.attrib['pin']}").strip()
                if normalized and normalized != "~":
                    pin_functions[pin] = normalized
            reference, number = pin.rsplit(".", 1)
            if reference in components:
                component_pin_numbers[reference] = tuple(
                    sorted(set(component_pin_numbers.get(reference, ())) | {number})
                )
        nets[name] = tuple(sorted(pins))
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=tuple(sorted(dnp_components)),
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
        component_pin_numbers=component_pin_numbers,
    )


def check_netlist(
    path: Path, validation: PcbValidationContract | SchematicValidationContract
) -> NetlistContract:
    """Compare a native export with reviewed expectations, never an empty scaffold."""
    contract = read_netlist(path)
    groups = return_net_groups(contract)
    shown_groups = groups[:5]
    review = (
        " Possible split returns need connector-pinout review: "
        + ", ".join("/".join(group.nets) for group in shown_groups)
        + (f" (+{len(groups) - len(shown_groups)} more)" if len(groups) > len(shown_groups) else "")
        + "."
        if groups
        else ""
    )
    similar = similar_connector_pin_groups(contract)
    if similar:
        shown = similar[:5]
        review += (
            " Similar connector pin functions need review: "
            + ", ".join(f"{group.symbol} {group.function}" for group in shown)
            + (f" (+{len(similar) - len(shown)} more)" if len(similar) > len(shown) else "")
            + "."
        )
    if not validation.components:
        raise ValueError("Complete the component test contract before native validation." + review)
    compared = {
        reference: component
        if validation.components.get(reference) is not None
        and validation.components[reference].part_id is not None
        else component.model_copy(update={"part_id": None})
        for reference, component in contract.components.items()
    }
    if compared != validation.components or contract.nets != validation.nets:
        changed_components = sorted(
            key
            for key in set(contract.components) | set(validation.components)
            if compared.get(key) != validation.components.get(key)
        )
        changed_nets = sorted(
            key
            for key in set(contract.nets) | set(validation.nets)
            if contract.nets.get(key) != validation.nets.get(key)
        )
        raise ValueError(
            f"Independent netlist contract mismatch: components={changed_components}, "
            f"nets={changed_nets}.{review}"
        )
    return contract
