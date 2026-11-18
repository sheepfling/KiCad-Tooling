"""Source pad identity, copper access, net assignment, and transformed center extraction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .fabrication_artwork import UnsupportedFabricationFormat
from .kicad_sexpr import (
    SExprSpan,
    sexpr_atoms,
    sexpr_field,
    sexpr_nodes,
    sexpr_root,
    sexpr_scalar,
)
from .pcb_footprint_reference_inventory import pcb_footprint_reference


@dataclass(frozen=True, slots=True)
class SourceComponentPad:
    """One source footprint pad and its board-space contact and drill geometry."""

    reference: str
    number: str
    net_name: str | None
    contact_layer: Literal["top", "bottom", "through"] | None
    x_nm: int
    y_nm: int
    drill_nm: int | None = None
    drill_plating: Literal["plated", "nonplated"] | None = None
    drill_shape: Literal["circular", "oval", "unsupported"] | None = None
    drill_width_nm: int | None = None
    drill_height_nm: int | None = None
    pad_shape: str | None = None
    size_x_nm: int | None = None
    size_y_nm: int | None = None


def source_component_pads(board_text: str) -> tuple[SourceComponentPad, ...]:
    """Parse component-pad identity, net assignment, and native board-space center."""
    try:
        root = sexpr_root(board_text, "kicad_pcb")
        references: set[str] = set()
        assignments: dict[tuple[str, str], str | None] = {}
        result: list[SourceComponentPad] = []
        for footprint in sexpr_nodes(board_text, root, "footprint"):
            reference = pcb_footprint_reference(board_text, footprint)
            if reference is None or not reference.isascii():
                raise UnsupportedFabricationFormat(
                    "source board has a footprint with no unique ASCII reference"
                )
            reference_key = reference.casefold()
            if reference_key == "via" or reference_key in references:
                raise UnsupportedFabricationFormat(
                    "source board has a duplicate or reserved footprint reference"
                )
            references.add(reference_key)

            pads = sexpr_nodes(board_text, footprint, "pad")
            if not pads:
                continue
            placement = _placement(board_text, footprint, reference)
            angle = math.radians(placement[2])
            cosine, sine = math.cos(angle), math.sin(angle)
            for pad in pads:
                atoms = sexpr_atoms(board_text, pad)
                if len(atoms) < 4 or not atoms[1] or not atoms[1].isascii():
                    raise UnsupportedFabricationFormat(
                        f"source board has an unsupported pad identity on {reference}"
                    )
                number = atoms[1]
                key = (reference_key, number)
                net_name = _pad_net_name(board_text, pad, reference, number)
                if key in assignments and assignments[key] != net_name:
                    raise UnsupportedFabricationFormat(
                        f"source board assigns duplicate pad identity {reference}.{number} to different nets"
                    )
                assignments[key] = net_name
                contact_layer = _pad_contact_layer(board_text, pad)
                local = _pad_offset(board_text, pad, reference, number)
                size_x_nm, size_y_nm = _pad_size(board_text, pad, reference, number)
                x_nm = round(placement[0] + local[0] * cosine + local[1] * sine)
                y_nm = round(placement[1] - local[0] * sine + local[1] * cosine)
                drill_nm, drill_plating, drill_shape, drill_width_nm, drill_height_nm = _pad_drill(
                    board_text, pad, atoms[2]
                )
                result.append(
                    SourceComponentPad(
                        reference,
                        number,
                        net_name,
                        contact_layer,
                        x_nm,
                        y_nm,
                        drill_nm,
                        drill_plating,
                        drill_shape,
                        drill_width_nm,
                        drill_height_nm,
                        atoms[3],
                        size_x_nm,
                        size_y_nm,
                    )
                )
        return tuple(result)
    except UnsupportedFabricationFormat:
        raise
    except (OverflowError, ValueError) as exc:
        raise UnsupportedFabricationFormat("source board has malformed pad placement data") from exc


def _placement(document: str, footprint: SExprSpan, reference: str) -> tuple[float, float, float]:
    try:
        values = sexpr_field(document, footprint, "at")
        if len(values) not in {2, 3}:
            raise ValueError("malformed footprint placement")
        layer = sexpr_scalar(document, footprint, "layer")
        if layer.casefold() not in {"f.cu", "b.cu"}:
            raise UnsupportedFabricationFormat(
                f"source footprint {reference} is not placed on a board copper side"
            )
        return (
            millimeters_to_nanometers(values[0]),
            millimeters_to_nanometers(values[1]),
            _finite_number(values[2]) if len(values) == 3 else 0.0,
        )
    except ValueError as exc:
        if isinstance(exc, UnsupportedFabricationFormat):
            raise
        raise ValueError(f"malformed placement for {reference}") from exc


def _pad_offset(document: str, pad: SExprSpan, reference: str, number: str) -> tuple[float, float]:
    try:
        values = sexpr_field(document, pad, "at")
        if len(values) not in {2, 3}:
            raise ValueError("malformed pad position")
        _finite_number(values[2]) if len(values) == 3 else 0.0
        return millimeters_to_nanometers(values[0]), millimeters_to_nanometers(values[1])
    except ValueError as exc:
        raise ValueError(f"malformed pad position for {reference}.{number}") from exc


def _pad_size(document: str, pad: SExprSpan, reference: str, number: str) -> tuple[int, int]:
    values = sexpr_field(document, pad, "size")
    if len(values) != 2:
        raise UnsupportedFabricationFormat(f"source pad {reference}.{number} has no 2D size")
    size_x_nm = round(millimeters_to_nanometers(values[0]))
    size_y_nm = round(millimeters_to_nanometers(values[1]))
    if size_x_nm <= 0 or size_y_nm <= 0:
        raise UnsupportedFabricationFormat(f"source pad {reference}.{number} has non-positive size")
    return size_x_nm, size_y_nm


def _pad_net_name(document: str, pad: SExprSpan, reference: str, number: str) -> str | None:
    nodes = sexpr_nodes(document, pad, "net")
    if len(nodes) > 1:
        raise UnsupportedFabricationFormat(
            f"source board has multiple net assignments for {reference}.{number}"
        )
    if not nodes:
        return None
    atoms = sexpr_atoms(document, nodes[0])
    if len(atoms) != 3:
        raise UnsupportedFabricationFormat(
            f"source board has a malformed net assignment for {reference}.{number}"
        )
    try:
        net_code = int(atoms[1])
    except ValueError as exc:
        raise UnsupportedFabricationFormat(
            f"source board has a malformed net code for {reference}.{number}"
        ) from exc
    if net_code < 0 or (net_code == 0 and atoms[2]):
        raise UnsupportedFabricationFormat(
            f"source board has an unsupported net assignment for {reference}.{number}"
        )
    if not net_code:
        return None
    if not atoms[2]:
        raise UnsupportedFabricationFormat(
            f"source board has an unnamed net for {reference}.{number}"
        )
    return atoms[2]


def _pad_contact_layer(document: str, pad: SExprSpan) -> Literal["top", "bottom", "through"] | None:
    """Return the outer copper access for supported source pad types."""
    atoms = sexpr_atoms(document, pad)
    if len(atoms) < 3:
        return None
    if atoms[2] == "thru_hole":
        return "through"
    if atoms[2] != "smd":
        return None
    layer_nodes = sexpr_nodes(document, pad, "layers")
    if len(layer_nodes) != 1:
        return None
    layers = {value.casefold() for value in sexpr_atoms(document, layer_nodes[0])[1:]}
    if "*.cu" in layers:
        return None
    outer_copper = layers & {"f.cu", "b.cu"}
    if len(outer_copper) != 1 or any(
        layer.endswith(".cu") and layer not in outer_copper for layer in layers
    ):
        return None
    return "top" if "f.cu" in outer_copper else "bottom"


def _pad_drill(
    document: str, pad: SExprSpan, pad_type: str
) -> tuple[
    int | None,
    Literal["plated", "nonplated"] | None,
    Literal["circular", "oval", "unsupported"] | None,
    int | None,
    int | None,
]:
    drill_nodes = sexpr_nodes(document, pad, "drill")
    if pad_type not in {"thru_hole", "np_thru_hole"}:
        if drill_nodes:
            raise UnsupportedFabricationFormat("non-through-hole source pad declares a drill")
        return None, None, None, None, None
    plating: Literal["plated", "nonplated"] = "plated" if pad_type == "thru_hole" else "nonplated"
    if len(drill_nodes) != 1:
        raise UnsupportedFabricationFormat("source drilled pad has no unique drill definition")
    # KiCad stores copper pad-shape offset metadata inside the drill node.
    # It does not change the hole center exported to Excellon.
    values = sexpr_field(document, pad, "drill")
    if len(values) == 1:
        drill_nm = round(millimeters_to_nanometers(values[0]))
        if drill_nm <= 0:
            raise UnsupportedFabricationFormat("source drilled pad has a non-positive drill size")
        return drill_nm, plating, "circular", drill_nm, drill_nm
    if len(values) != 3 or values[0] != "oval":
        return None, plating, "unsupported", None, None
    drill_width_nm = round(millimeters_to_nanometers(values[1]))
    drill_height_nm = round(millimeters_to_nanometers(values[2]))
    if drill_width_nm <= 0 or drill_height_nm <= 0:
        raise UnsupportedFabricationFormat("source drilled pad has a non-positive drill size")
    shape: Literal["circular", "oval"] = "circular" if drill_width_nm == drill_height_nm else "oval"
    return (
        min(drill_width_nm, drill_height_nm),
        plating,
        shape,
        drill_width_nm,
        drill_height_nm,
    )


def _finite_number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite board coordinate")
    return number


def millimeters_to_nanometers(value: str) -> float:
    """Convert millimeters to nanometers while preserving source precision."""
    result = _finite_number(value) * 1_000_000
    if not math.isfinite(result):
        raise ValueError("coordinate outside supported numeric range")
    return result
