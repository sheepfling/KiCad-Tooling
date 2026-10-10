"""Synthetic schematic inputs for the clock-output cohort trial."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

_NAMESPACE = uuid.UUID("2e37d07b-0e6a-5094-92b3-73e7789c63b1")
_PROJECT = "LINT-075 synthetic clock series trial"


@dataclass(frozen=True)
class Pin:
    number: str
    name: str
    electrical_type: str
    x: float


@dataclass(frozen=True)
class Part:
    reference: str
    library_id: str
    value: str
    x: float
    y: float
    pin_nets: tuple[str, ...]
    dnp: bool = False


@dataclass(frozen=True)
class Case:
    parts: tuple[Part, ...]
    candidate_finding: bool
    disposition: str


_PIN_LIBRARY = {
    "Synthetic:ClockSource": (Pin("1", "OUT", "output", -5.08),),
    "Oscillator:DirectDriver": (Pin("1", "OUT", "output", -5.08),),
    "Synthetic:ClockInput": (Pin("1", "CLK_IN", "input", -5.08),),
    "Synthetic:SeriesResistor": (
        Pin("1", "~", "passive", -5.08),
        Pin("2", "~", "passive", 5.08),
    ),
    "Synthetic:SeriesBead": (
        Pin("1", "~", "passive", -5.08),
        Pin("2", "~", "passive", 5.08),
    ),
    "Synthetic:TestPoint": (Pin("1", "TP", "passive", -5.08),),
}


def _part(
    reference: str,
    library_id: str,
    value: str,
    x: float,
    y: float,
    *pin_nets: str,
    dnp: bool = False,
) -> Part:
    if len(pin_nets) != len(_PIN_LIBRARY[library_id]):
        raise ValueError(f"{reference}: expected {len(_PIN_LIBRARY[library_id])} pin nets")
    return Part(reference, library_id, value, x, y, tuple(pin_nets), dnp)


CASES = {
    "series-control": Case(
        (
            _part("X1", "Synthetic:ClockSource", "Synthetic clock source", 101.6, 101.6, "OSC_SRC"),
            _part("R1", "Synthetic:SeriesResistor", "33R", 121.92, 101.6, "OSC_SRC", "CLK_LOAD"),
            _part("U1", "Synthetic:ClockInput", "Synthetic clock input", 147.32, 101.6, "CLK_LOAD"),
        ),
        False,
        "valid-series-control",
    ),
    "series-testpoint-control": Case(
        (
            _part("X1", "Synthetic:ClockSource", "Synthetic clock source", 101.6, 101.6, "OSC_SRC"),
            _part("R1", "Synthetic:SeriesResistor", "33R", 121.92, 101.6, "OSC_SRC", "CLK_LOAD"),
            _part("U1", "Synthetic:ClockInput", "Synthetic clock input", 147.32, 101.6, "CLK_LOAD"),
            _part("TP1", "Synthetic:TestPoint", "TestPoint", 121.92, 127.0, "OSC_SRC"),
        ),
        False,
        "valid-series-with-test-point-on-source-side",
    ),
    "direct-load-fault": Case(
        (
            _part(
                "X1", "Synthetic:ClockSource", "Synthetic clock source", 101.6, 101.6, "CLK_DIRECT"
            ),
            _part(
                "U1", "Synthetic:ClockInput", "Synthetic clock input", 147.32, 101.6, "CLK_DIRECT"
            ),
        ),
        True,
        "direct-load-fault",
    ),
    "direct-testpoint-fault": Case(
        (
            _part(
                "X1", "Synthetic:ClockSource", "Synthetic clock source", 101.6, 101.6, "CLK_DIRECT"
            ),
            _part(
                "U1", "Synthetic:ClockInput", "Synthetic clock input", 147.32, 101.6, "CLK_DIRECT"
            ),
            _part("TP1", "Synthetic:TestPoint", "TestPoint", 121.92, 127.0, "CLK_DIRECT"),
        ),
        True,
        "direct-load-fault-with-test-point",
    ),
    "direct-pull-fault": Case(
        (
            _part(
                "X1", "Synthetic:ClockSource", "Synthetic clock source", 101.6, 101.6, "CLK_DIRECT"
            ),
            _part("R1", "Synthetic:SeriesResistor", "10k", 121.92, 127.0, "CLK_DIRECT", "GND"),
            _part(
                "U1", "Synthetic:ClockInput", "Synthetic clock input", 147.32, 101.6, "CLK_DIRECT"
            ),
            _part(
                "J1", "Synthetic:ClockInput", "Synthetic reference contact", 147.32, 152.4, "GND"
            ),
        ),
        True,
        "pull-resistor-does-not-count-as-series",
    ),
    "wrong-net-fault": Case(
        (
            _part(
                "X1", "Synthetic:ClockSource", "Synthetic clock source", 101.6, 101.6, "CLK_DIRECT"
            ),
            _part(
                "U1", "Synthetic:ClockInput", "Synthetic clock input", 147.32, 101.6, "CLK_DIRECT"
            ),
            _part(
                "X2",
                "Synthetic:ClockSource",
                "Other synthetic clock source",
                101.6,
                177.8,
                "AUX_SRC",
            ),
            _part("R1", "Synthetic:SeriesResistor", "33R", 121.92, 177.8, "AUX_SRC", "AUX_LOAD"),
            _part(
                "U2",
                "Synthetic:ClockInput",
                "Other synthetic clock input",
                147.32,
                177.8,
                "AUX_LOAD",
            ),
        ),
        True,
        "only-resistor-is-on-an-unrelated-clock-net",
    ),
    "bypass-fault": Case(
        (
            _part("X1", "Synthetic:ClockSource", "Synthetic clock source", 101.6, 101.6, "OSC_SRC"),
            _part("R1", "Synthetic:SeriesResistor", "33R", 121.92, 152.4, "OSC_SRC", "DAMPED"),
            _part(
                "U1", "Synthetic:ClockInput", "Directly connected input", 147.32, 101.6, "OSC_SRC"
            ),
            _part("U2", "Synthetic:ClockInput", "Downstream input", 147.32, 152.4, "DAMPED"),
        ),
        True,
        "direct-bypass-around-series-resistor",
    ),
    "wrong-part-miss": Case(
        (
            _part("X1", "Synthetic:ClockSource", "Synthetic clock source", 101.6, 101.6, "OSC_SRC"),
            _part(
                "R1", "Synthetic:SeriesBead", "Ferrite bead", 121.92, 101.6, "OSC_SRC", "CLK_LOAD"
            ),
            _part("U1", "Synthetic:ClockInput", "Synthetic clock input", 147.32, 101.6, "CLK_LOAD"),
        ),
        False,
        "candidate-uses-reference-prefix-and-misses-wrong-part",
    ),
    "dnp-series-miss": Case(
        (
            _part("X1", "Synthetic:ClockSource", "Synthetic clock source", 101.6, 101.6, "OSC_SRC"),
            _part(
                "R1",
                "Synthetic:SeriesResistor",
                "33R",
                121.92,
                101.6,
                "OSC_SRC",
                "CLK_LOAD",
                dnp=True,
            ),
            _part("U1", "Synthetic:ClockInput", "Synthetic clock input", 147.32, 101.6, "CLK_LOAD"),
        ),
        False,
        "candidate-ignores-dnp-state",
    ),
    "wrong-value-series-miss": Case(
        (
            _part("X1", "Synthetic:ClockSource", "Synthetic clock source", 101.6, 101.6, "OSC_SRC"),
            _part("R1", "Synthetic:SeriesResistor", "1M", 121.92, 101.6, "OSC_SRC", "CLK_LOAD"),
            _part("U1", "Synthetic:ClockInput", "Synthetic clock input", 147.32, 101.6, "CLK_LOAD"),
        ),
        False,
        "candidate-ignores-resistor-value",
    ),
    "direct-drive-control": Case(
        (
            _part(
                "U1",
                "Oscillator:DirectDriver",
                "Synthetic approved direct driver",
                101.6,
                101.6,
                "CLK_DIRECT",
            ),
            _part(
                "U2", "Synthetic:ClockInput", "Synthetic clock input", 147.32, 101.6, "CLK_DIRECT"
            ),
        ),
        True,
        "candidate-overprompts-on-authored-direct-drive-control",
    ),
}


def _uid(case: str, name: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{case}/{name}"))


def _font() -> str:
    return "(effects (font (size 1.27 1.27)))"


def _pin(pin: Pin) -> str:
    return (
        f"(pin {pin.electrical_type} line (at {pin.x:g} 0 0) (length 2.54) "
        f'(name "{pin.name}" {_font()}) (number "{pin.number}" {_font()}))'
    )


def _library_symbol(library_id: str) -> str:
    _namespace, name = library_id.split(":", 1)
    reference = (
        "X"
        if name == "ClockSource"
        else "U"
        if name == "DirectDriver"
        else ("R" if "Resistor" in name else "TP" if name == "TestPoint" else "U")
    )
    value = {
        "ClockSource": "Synthetic clock source",
        "DirectDriver": "Synthetic direct driver",
        "ClockInput": "Synthetic clock input",
        "SeriesResistor": "33R",
        "SeriesBead": "Ferrite bead",
        "TestPoint": "TestPoint",
    }[name]
    pins = "\n".join(f"   {_pin(pin)}" for pin in _PIN_LIBRARY[library_id])
    return f'''(symbol "{library_id}"
 (pin_names (offset 0)) (in_bom yes) (on_board yes)
 (property "Reference" "{reference}" (at 0 -7.62 0) {_font()})
 (property "Value" "{value}" (at 0 7.62 0) {_font()})
 (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
 (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
 (symbol "{name}_0_1" (rectangle (start -2.54 -2.54) (end 2.54 2.54)
  (stroke (width 0.254) (type default)) (fill (type none))))
 (symbol "{name}_1_1"
{pins}
 ))'''


def render_case(case_name: str, case: Case) -> str:
    """Render one deterministic, label-connected schematic for native review."""
    sheet_uuid = _uid(case_name, "sheet")
    libraries = "\n".join(
        _library_symbol(lib_id) for lib_id in sorted({p.library_id for p in case.parts})
    )
    blocks: list[str] = []
    for part in case.parts:
        ref_y = part.y - 10.16
        value_y = part.y - 7.62
        pin_instances = " ".join(
            f'(pin "{pin.number}" (uuid "{_uid(case_name, part.reference + "/pin" + pin.number)}"))'
            for pin in _PIN_LIBRARY[part.library_id]
        )
        block = f'''(symbol (lib_id "{part.library_id}") (at {part.x:g} {part.y:g} 0) (unit 1)
 (in_bom yes) (on_board yes) (dnp {"yes" if part.dnp else "no"}) (uuid "{_uid(case_name, part.reference)}")
 (property "Reference" "{part.reference}" (at {part.x:g} {ref_y:g} 0) {_font()})
 (property "Value" "{part.value}" (at {part.x:g} {value_y:g} 0) {_font()})
 (property "Footprint" "" (at {part.x:g} {part.y:g} 0) (effects (font (size 1.27 1.27)) hide))
 (property "Datasheet" "" (at {part.x:g} {part.y:g} 0) (effects (font (size 1.27 1.27)) hide))
 {pin_instances}
 (instances (project "{_PROJECT}" (path "/{sheet_uuid}" (reference "{part.reference}") (unit 1)))))'''
        blocks.append(block)

    wires: list[str] = []
    labels: list[str] = []
    for part in case.parts:
        for pin, net in zip(_PIN_LIBRARY[part.library_id], part.pin_nets, strict=True):
            pin_x = part.x + pin.x
            end_x = pin_x - 6.35 if pin.x < 0 else pin_x + 6.35
            y = part.y
            wire_id = _uid(case_name, f"wire/{part.reference}/{pin.number}")
            wires.append(
                f"(wire (pts (xy {pin_x:g} {y:g}) (xy {end_x:g} {y:g})) "
                f'(stroke (width 0) (type default)) (uuid "{wire_id}"))'
            )
            labels.append(
                f'(label "{net}" (at {end_x:g} {y:g} 0) '
                f"(effects (font (size 1.27 1.27)) (justify left bottom)) "
                f'(uuid "{_uid(case_name, "label/" + part.reference + "/" + pin.number)}"))'
            )

    title = case_name.replace("-", " ")
    part_blocks = "\n".join(blocks)
    wire_blocks = "\n".join(wires)
    label_blocks = "\n".join(labels)
    return f'''(kicad_sch (version 20231120) (generator "eeschema") (uuid "{sheet_uuid}") (paper "A4")
(title_block (title "LINT-075 {title}") (comment 1 "SYNTHETIC TOOLING FIXTURE - NOT FOR MANUFACTURE"))
(lib_symbols
{libraries}
)
{part_blocks}
{wire_blocks}
{label_blocks}
(sheet_instances (path "/" (page "1")))
)
'''


def write_cases(destination: Path) -> tuple[Path, ...]:
    """Write the checked-in cohort fixtures using stable UUIDs."""
    destination.mkdir(parents=True, exist_ok=True)
    written = []
    for case_name, case in CASES.items():
        path = destination / f"{case_name}.kicad_sch"
        path.write_text(render_case(case_name, case), encoding="utf-8")
        written.append(path)
    expectations = {
        "schema_version": 1,
        "cases": {
            name: {
                "candidate_finding": case.candidate_finding,
                "disposition": case.disposition,
            }
            for name, case in CASES.items()
        },
    }
    (destination / "expectations.json").write_text(
        json.dumps(expectations, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return tuple(written)


if __name__ == "__main__":
    repository_root = Path(__file__).resolve().parents[2]
    fixture_dir = repository_root / "tests/fixtures/design_lint/cohort-clock-series-native"
    for fixture in write_cases(fixture_dir):
        print(fixture.relative_to(repository_root))
