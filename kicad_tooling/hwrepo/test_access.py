"""Project-authored test and service access checks against native netlists."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import kicad_sexpr as sx
from .electrical_report_models import ElectricalCheck
from .netlist_contract_models import NetlistContract
from .pcb_test_access_models import (
    PcbAccessAnalysis,
    TestAccessAnalysis,
    TestAccessEndpointRequirement,
)
from .test_access_probe_envelope import (
    pcb_access_probe_request_set,
    pcb_probe_envelope_checks,
)

__all__ = [
    "evaluate_test_access_checks",
    "pcb_access_probe_request_set",
    "pcb_accessibility_checks",
    "pcb_probe_envelope_checks",
]


@dataclass(frozen=True, slots=True)
class _BoardPad:
    number: str
    net: str | None
    layers: frozenset[str]


@dataclass(frozen=True, slots=True)
class _BoardFootprint:
    identity: str
    dnp: bool
    pads: dict[str, tuple[_BoardPad, ...]]


def _exposed_outer_sides(pads: tuple[_BoardPad, ...]) -> tuple[str, ...]:
    """Return outer pad sides with both copper and solder-mask declarations."""
    sides: set[str] = set()
    for pad in pads:
        layers = {layer.casefold() for layer in pad.layers}
        if ("f.cu" in layers or "*.cu" in layers) and ("f.mask" in layers or "*.mask" in layers):
            sides.add("front")
        if ("b.cu" in layers or "*.cu" in layers) and ("b.mask" in layers or "*.mask" in layers):
            sides.add("back")
    return tuple(side for side in ("front", "back") if side in sides)


def _board_footprints(path: Path) -> dict[str, _BoardFootprint]:
    """Read only KiCad 10 board footprints and pad net/mask declarations."""
    source = path.read_text(encoding="utf-8")
    roots = sx.sexpr_children(source, 0, len(source))
    if len(roots) != 1 or sx.sexpr_atoms(source, roots[0])[:1] != ("kicad_pcb",):
        raise ValueError("PCB source does not have one native kicad_pcb root")
    root = roots[0]
    net_ids: dict[str, str] = {}
    for span in sx.sexpr_nodes(source, root, "net"):
        atoms = sx.sexpr_atoms(source, span)
        if len(atoms) != 3 or not atoms[1].isdigit() or atoms[1] in net_ids:
            raise ValueError("PCB source contains a malformed or duplicate net identity")
        net_ids[atoms[1]] = atoms[2]

    footprints: dict[str, _BoardFootprint] = {}
    for span in sx.sexpr_nodes(source, root, "footprint"):
        header = sx.sexpr_atoms(source, span)
        if len(header) != 2:
            raise ValueError("PCB footprint has no exact library identity")
        properties: dict[str, str] = {}
        for property_span in sx.sexpr_nodes(source, span, "property"):
            atoms = sx.sexpr_atoms(source, property_span)
            if len(atoms) != 3 or atoms[1] in properties:
                raise ValueError("PCB footprint has malformed or duplicate properties")
            properties[atoms[1]] = atoms[2]
        reference = properties.get("Reference")
        if not reference:
            legacy = tuple(
                item
                for item in sx.sexpr_nodes(source, span, "fp_text")
                if sx.sexpr_atoms(source, item)[:2] == ("fp_text", "reference")
            )
            if len(legacy) == 1:
                atoms = sx.sexpr_atoms(source, legacy[0])
                reference = atoms[2] if len(atoms) >= 3 else None
            elif len(legacy) > 1:
                raise ValueError("PCB footprint has duplicate legacy reference text")
        if not reference or reference.casefold() in footprints:
            raise ValueError("PCB footprint has no reference or duplicates another footprint")

        grouped_pads: dict[str, list[_BoardPad]] = {}
        for pad_span in sx.sexpr_nodes(source, span, "pad"):
            pad_header = sx.sexpr_atoms(source, pad_span)
            if len(pad_header) < 3:
                raise ValueError(f"{reference}: malformed PCB pad")
            number = pad_header[1]
            net_nodes = sx.sexpr_nodes(source, pad_span, "net")
            if len(net_nodes) > 1:
                raise ValueError(f"{reference}.{number}: duplicate pad net assignments")
            net: str | None = None
            if net_nodes:
                net_atoms = sx.sexpr_atoms(source, net_nodes[0])
                if len(net_atoms) != 3 or not net_atoms[1].isdigit():
                    raise ValueError(f"{reference}.{number}: malformed pad net assignment")
                if net_ids.get(net_atoms[1]) != net_atoms[2]:
                    raise ValueError(
                        f"{reference}.{number}: pad net identity differs from board net table"
                    )
                net = net_atoms[2]
            layer_nodes = sx.sexpr_nodes(source, pad_span, "layers")
            if len(layer_nodes) != 1:
                raise ValueError(f"{reference}.{number}: expected one pad layer declaration")
            layer_atoms = sx.sexpr_atoms(source, layer_nodes[0])
            if len(layer_atoms) < 2:
                raise ValueError(f"{reference}.{number}: pad has no assigned layers")
            grouped_pads.setdefault(number, []).append(
                _BoardPad(number=number, net=net, layers=frozenset(layer_atoms[1:]))
            )
        attr = sx.sexpr_nodes(source, span, "attr")
        if len(attr) > 1:
            raise ValueError(f"{reference}: duplicate PCB footprint attributes")
        attributes: set[str] = set(sx.sexpr_atoms(source, attr[0])[1:]) if attr else set()
        dnp_property = next(
            (value.casefold() for key, value in properties.items() if key.casefold() == "dnp"),
            "",
        )
        dnp = "dnp" in attributes or dnp_property in {"yes", "true", "1"}
        footprints[reference.casefold()] = _BoardFootprint(
            identity=header[1],
            dnp=dnp,
            pads={number: tuple(items) for number, items in grouped_pads.items()},
        )
    return footprints


def pcb_accessibility_checks(
    spec: TestAccessAnalysis, board: PcbAccessAnalysis, board_path: Path
) -> tuple[ElectricalCheck, ...]:
    """Check exact placed pad/net and outer mask-layer declaration."""
    try:
        footprints = _board_footprints(board_path)
    except (OSError, ValueError) as exc:
        return (
            ElectricalCheck(
                id="test-access/pcb-accessibility/source",
                status="FAIL",
                detail=f"Could not inspect the configured KiCad 10 PCB source: {exc}",
            ),
        )

    def endpoint_issues(
        endpoint: TestAccessEndpointRequirement, expected_net: str
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        footprint = footprints.get(endpoint.reference.casefold())
        if footprint is None:
            return (f"{endpoint.reference} has no placed footprint on the PCB",), ()
        issues: list[str] = []
        if footprint.dnp:
            issues.append(f"{endpoint.reference} is marked DNP on the PCB")
        if footprint.identity != endpoint.footprint:
            issues.append(
                f"{endpoint.reference} PCB footprint is {footprint.identity}; "
                f"expected {endpoint.footprint}"
            )
        pads = footprint.pads.get(endpoint.pin.rsplit(".", 1)[1], ())
        if not pads:
            issues.append(f"{endpoint.pin} has no matching pad on the PCB")
            return tuple(issues), ()
        assigned = [pad for pad in pads if pad.net == expected_net]
        if not assigned:
            nets = ", ".join(sorted({pad.net or "unconnected" for pad in pads}))
            issues.append(f"{endpoint.pin} PCB pad is on {nets}; expected {expected_net}")
            return tuple(issues), ()
        exposed_sides = _exposed_outer_sides(tuple(assigned))
        if not exposed_sides:
            issues.append(
                f"{endpoint.pin} is on {expected_net} but has no outer copper and solder-mask layer declaration"
            )
        elif endpoint.approach_side != "either" and endpoint.approach_side not in exposed_sides:
            exposed = ", ".join(exposed_sides)
            issues.append(
                f"{endpoint.pin} exposes {exposed}; expected a {endpoint.approach_side}-side approach"
            )
        return tuple(issues), exposed_sides

    checks: list[ElectricalCheck] = []
    for decision in spec.decisions:
        check_id = f"test-access/pcb-accessibility/{decision.id}"
        if decision.mode != "required":
            checks.append(
                ElectricalCheck(
                    id=check_id,
                    status="NOT_APPLICABLE",
                    detail=f"Net {decision.net} is explicitly excluded: {decision.reason}",
                )
            )
            continue
        results = [
            (endpoint, *endpoint_issues(endpoint, decision.net)) for endpoint in decision.endpoints
        ]
        matching = [(endpoint, sides) for endpoint, issues, sides in results if not issues]
        failures = [
            f"{endpoint.pin}: {'; '.join(issues)}" for endpoint, issues, _sides in results if issues
        ]
        passed = not failures if decision.selection == "all" else bool(matching)
        if passed:
            matched_surfaces = ", ".join(
                f"{endpoint.pin} ({', '.join(sides)})" for endpoint, sides in matching
            )
            detail = (
                f"PCB pad(s) for net {decision.net} match the declared footprint and expose "
                f"the requested outer copper and solder-mask layer declarations: {matched_surfaces}. "
                f"Basis: {board.basis}. "
                "Pad aperture geometry, probe clearance and obstruction are not checked."
            )
        else:
            detail = "; ".join(failures)
        checks.append(
            ElectricalCheck(
                id=check_id,
                status="PASS" if passed else "FAIL",
                detail=detail,
            )
        )
    return tuple(checks)


def evaluate_test_access_checks(
    spec: TestAccessAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Compare required access endpoints with exact component and netlist evidence."""
    components = {
        reference.casefold(): (reference, item) for reference, item in observed.components.items()
    }
    symbols = {
        reference.casefold(): value for reference, value in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    pin_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    known_pins = {
        f"{reference}.{number}".casefold()
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    }
    known_pins.update(pin.casefold() for pin in observed.pin_functions)
    known_pins.update(pin.casefold() for pin in observed.pin_electrical_types)
    known_pins.update(pin.casefold() for pins in observed.nets.values() for pin in pins)

    def endpoint_issues(endpoint: TestAccessEndpointRequirement, expected_net: str) -> list[str]:
        reference_key = endpoint.reference.casefold()
        component_entry = components.get(reference_key)
        if component_entry is None:
            return [f"{endpoint.reference} is absent from the native netlist"]
        actual_reference, component = component_entry
        issues: list[str] = []
        if reference_key in dnp:
            issues.append(f"{actual_reference} is marked DNP")
        actual_symbol = symbols.get(reference_key)
        if actual_symbol != endpoint.symbol:
            issues.append(
                f"{actual_reference} symbol is {actual_symbol or 'unknown'}; expected {endpoint.symbol}"
            )
        if component.footprint != endpoint.footprint:
            issues.append(
                f"{actual_reference} footprint is {component.footprint or 'empty'}; expected {endpoint.footprint}"
            )
        pin_key = endpoint.pin.casefold()
        reference, number = endpoint.pin.rsplit(".", 1)
        inventory = pin_numbers.get(reference.casefold())
        if inventory is None or number.casefold() not in inventory or pin_key not in known_pins:
            issues.append(f"{endpoint.pin} is absent from the native symbol pin inventory")
        actual_nets = pin_nets.get(pin_key, set())
        if actual_nets != {expected_net}:
            assigned = ", ".join(sorted(actual_nets)) if actual_nets else "unconnected"
            issues.append(f"{endpoint.pin} is assigned to {assigned}; expected {expected_net}")
        actual_type = pin_types.get(pin_key)
        if actual_type != endpoint.electrical_type.casefold():
            issues.append(
                f"{endpoint.pin} electrical type is {actual_type or 'unavailable'}; "
                f"expected {endpoint.electrical_type}"
            )
        return issues

    checks: list[ElectricalCheck] = []
    for decision in spec.decisions:
        check_id = f"test-access/schematic/{decision.id}"
        if decision.mode != "required":
            if decision.net not in observed.nets:
                checks.append(
                    ElectricalCheck(
                        id=check_id,
                        status="FAIL",
                        detail=(
                            f"Explicitly scoped net {decision.net} is absent from the native netlist; "
                            "review whether the exclusion is stale."
                        ),
                    )
                )
                continue
            checks.append(
                ElectricalCheck(
                    id=check_id,
                    status="NOT_APPLICABLE",
                    detail=(
                        f"Net {decision.net} is explicitly excluded from test-access coverage: "
                        f"{decision.reason} Basis: {decision.basis}."
                    ),
                )
            )
            continue

        findings = [
            (endpoint, endpoint_issues(endpoint, decision.net)) for endpoint in decision.endpoints
        ]
        matches = [endpoint for endpoint, issues in findings if not issues]
        if decision.selection == "all":
            failures = [
                f"{endpoint.reference}.{endpoint.pin.rsplit('.', 1)[1]} ({endpoint.kind}): "
                + "; ".join(issues)
                for endpoint, issues in findings
                if issues
            ]
            passed = not failures
            detail = (
                f"All {len(decision.endpoints)} declared access endpoint(s) match net {decision.net}. "
                f"Basis: {decision.basis}."
                if passed
                else "; ".join(failures)
            )
        else:
            passed = bool(matches)
            detail = (
                f"At least one of {len(decision.endpoints)} declared access endpoint(s) matches "
                f"net {decision.net}: {', '.join(item.pin for item in matches)}. Basis: {decision.basis}."
                if passed
                else "; ".join(
                    f"{endpoint.pin}: {'; '.join(issues)}" for endpoint, issues in findings
                )
            )
        checks.append(
            ElectricalCheck(
                id=check_id,
                status="PASS" if passed else "FAIL",
                detail=detail,
            )
        )
    return tuple(checks)
