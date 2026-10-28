"""Synthetic native schematic sources for oscillator output path lint."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

_NAMESPACE = uuid.UUID("be987a5a-4fd7-4852-b8ad-03b90f41e1a3")
_PROJECT = "LINT-150 synthetic oscillator output path"


@dataclass(frozen=True, slots=True)
class Pin:
    number: str
    name: str
    electrical_type: str
    x: float


@dataclass(frozen=True, slots=True)
class Symbol:
    reference_prefix: str
    value: str
    pins: tuple[Pin, ...]


@dataclass(frozen=True, slots=True)
class Part:
    reference: str
    library_id: str
    value: str
    footprint: str
    x: float
    y: float
    pin_nets: tuple[str, ...]


_SYMBOLS = MappingProxyType(
    {
        "Synthetic:ClockModule": Symbol(
            "X", "Synthetic clock module", (Pin("1", "OUT", "output", -5.08),)
        ),
        "Synthetic:ReceiverA": Symbol(
            "U", "Synthetic receiver A", (Pin("2", "CLK", "input", -5.08),)
        ),
        "Synthetic:ReceiverB": Symbol(
            "U", "Synthetic receiver B", (Pin("3", "CLK", "input", -5.08),)
        ),
        "Device:R": Symbol(
            "R",
            "R",
            (Pin("1", "~", "passive", -5.08), Pin("2", "~", "passive", 5.08)),
        ),
    }
)


def _uid(case_name: str, name: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{case_name}/{name}"))


def _font() -> str:
    return "(effects (font (size 1.27 1.27)))"


def _library_symbol(library_id: str) -> str:
    _namespace, name = library_id.split(":", 1)
    symbol = _SYMBOLS[library_id]
    pins = "\n".join(
        f"   (pin {pin.electrical_type} line (at {pin.x:g} 0 0) (length 2.54) "
        f'(name "{pin.name}" {_font()}) (number "{pin.number}" {_font()}))'
        for pin in symbol.pins
    )
    return f'''(symbol "{library_id}"
 (pin_names (offset 0)) (in_bom yes) (on_board yes)
 (property "Reference" "{symbol.reference_prefix}" (at 0 -7.62 0) {_font()})
 (property "Value" "{symbol.value}" (at 0 7.62 0) {_font()})
 (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
 (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
 (symbol "{name}_0_1" (rectangle (start -2.54 -2.54) (end 2.54 2.54)
  (stroke (width 0.254) (type default)) (fill (type none))))
 (symbol "{name}_1_1"
{pins}
 ))'''


def _parts(resistor_value: str) -> tuple[Part, ...]:
    return (
        Part(
            "X1",
            "Synthetic:ClockModule",
            "Synthetic clock module",
            "Synthetic:ClockModule_4",
            101.6,
            101.6,
            ("CLK_SOURCE",),
        ),
        Part(
            "R1",
            "Device:R",
            resistor_value,
            "Synthetic:R_0603",
            121.92,
            101.6,
            ("CLK_SOURCE", "CLK_LOAD"),
        ),
        Part(
            "U2",
            "Synthetic:ReceiverA",
            "Synthetic receiver A",
            "Synthetic:SOIC8",
            147.32,
            101.6,
            ("CLK_LOAD",),
        ),
        Part(
            "U3",
            "Synthetic:ReceiverB",
            "Synthetic receiver B",
            "Synthetic:QFN16",
            147.32,
            127.0,
            ("CLK_LOAD",),
        ),
    )


def render_case(case_name: str, resistor_value: str) -> str:
    """Render a label-connected series path with a controlled resistor value."""
    parts = _parts(resistor_value)
    sheet_uuid = _uid(case_name, "sheet")
    libraries = "\n".join(
        _library_symbol(library_id) for library_id in sorted({part.library_id for part in parts})
    )
    blocks: list[str] = []
    wires: list[str] = []
    labels: list[str] = []
    for part in parts:
        symbol = _SYMBOLS[part.library_id]
        ref_y = part.y - 10.16
        value_y = part.y - 7.62
        pin_instances = " ".join(
            f'(pin "{pin.number}" (uuid "{_uid(case_name, part.reference + "/pin" + pin.number)}"))'
            for pin in symbol.pins
        )
        blocks.append(
            f'''(symbol (lib_id "{part.library_id}") (at {part.x:g} {part.y:g} 0) (unit 1)
 (in_bom yes) (on_board yes) (dnp no) (uuid "{_uid(case_name, part.reference)}")
 (property "Reference" "{part.reference}" (at {part.x:g} {ref_y:g} 0) {_font()})
 (property "Value" "{part.value}" (at {part.x:g} {value_y:g} 0) {_font()})
 (property "Footprint" "{part.footprint}" (at {part.x:g} {part.y:g} 0) (effects (font (size 1.27 1.27)) hide))
 (property "Datasheet" "" (at {part.x:g} {part.y:g} 0) (effects (font (size 1.27 1.27)) hide))
 {pin_instances}
 (instances (project "{_PROJECT}" (path "/{sheet_uuid}" (reference "{part.reference}") (unit 1)))))'''
        )
        for pin, net in zip(symbol.pins, part.pin_nets, strict=True):
            pin_x = part.x + pin.x
            end_x = pin_x - 6.35 if pin.x < 0 else pin_x + 6.35
            wires.append(
                f"(wire (pts (xy {pin_x:g} {part.y:g}) (xy {end_x:g} {part.y:g})) "
                f'(stroke (width 0) (type default)) (uuid "{_uid(case_name, f"wire/{part.reference}/{pin.number}")}"))'
            )
            labels.append(
                f'(label "{net}" (at {end_x:g} {part.y:g} 0) '
                f"(effects (font (size 1.27 1.27)) (justify left bottom)) "
                f'(uuid "{_uid(case_name, f"label/{part.reference}/{pin.number}")}"))'
            )
    title = case_name.replace("-", " ")
    part_blocks = "\n".join(blocks)
    wire_blocks = "\n".join(wires)
    label_blocks = "\n".join(labels)
    return f'''(kicad_sch (version 20231120) (generator "eeschema") (uuid "{sheet_uuid}") (paper "A4")
(title_block (title "LINT-150 {title}") (comment 1 "SYNTHETIC TOOLING FIXTURE - NOT FOR MANUFACTURE"))
(lib_symbols
{libraries}
)
{part_blocks}
{wire_blocks}
{label_blocks}
(sheet_instances (path "/" (page "1")))
)
'''


CASES = MappingProxyType(
    {
        "series-boundary-control": "47R",
        "wrong-value-fault": "1k",
    }
)


def write_cases(destination: Path) -> tuple[Path, ...]:
    """Write the stable native inputs for the boundary control and value fault."""
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for case_name, resistor_value in CASES.items():
        path = destination / f"{case_name}.kicad_sch"
        path.write_text(render_case(case_name, resistor_value), encoding="utf-8")
        paths.append(path)
    return tuple(paths)


if __name__ == "__main__":
    repository_root = Path(__file__).resolve().parents[2]
    fixture_root = repository_root / "tests/fixtures/design_lint/oscillator-output-native"
    for fixture in write_cases(fixture_root):
        print(fixture.relative_to(repository_root))
