"""Synthetic schematic-geometry cases used by catalog reachability checks."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines
from tests.design_lint_fixtures import observed, schematic_geometry_fixtures

TESTS = Path(__file__).resolve().parents[1]


def schematic_geometry_rule_ids() -> set[str]:
    cases = (
        (
            (TESTS / "fixtures/design_lint/near-miss-pin-line.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/near-miss-pin-line.kicad_sch",
            frozenset({"R1.1"}),
        ),
        (
            (TESTS / "fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch",
            frozenset({"R1.1"}),
        ),
        (
            (TESTS / "fixtures/design_lint/wire-end-near-pin-tip.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/wire-end-near-pin-tip.kicad_sch",
            frozenset({"R1.1"}),
        ),
        (
            (TESTS / "fixtures/design_lint/label-near-wire-endpoint.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/label-near-wire-endpoint.kicad_sch",
            frozenset(),
        ),
        (
            (TESTS / "fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch",
            frozenset(),
        ),
        (
            (TESTS / "fixtures/design_lint/t-junction/fault-no-junction.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/t-junction/fault-no-junction.kicad_sch",
            frozenset({"R1.2"}),
        ),
        (
            schematic_geometry_fixtures.free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4)),
            "synthetic/free-text-anchor.kicad_sch",
            frozenset(),
        ),
        (
            schematic_geometry_fixtures.free_text_objects_fixture(
                "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (29.0, 25.4)
            ),
            "synthetic/free-text-overlap.kicad_sch",
            frozenset(),
        ),
        (
            schematic_geometry_fixtures.free_text_wire_fixture(
                "WIRE CROSSING FAULT", (88.9, 71.12)
            ),
            "synthetic/free-text-wire.kicad_sch",
            frozenset(),
        ),
        (
            schematic_geometry_fixtures.free_text_symbol_body_fixture(),
            "synthetic/free-text-symbol-body.kicad_sch",
            frozenset(),
        ),
        (
            schematic_geometry_fixtures.symbol_body_wire_fixture(),
            "synthetic/symbol-body-wire.kicad_sch",
            frozenset(),
        ),
    )
    result: set[str] = set()
    for source_bytes, source_path, unconnected_pins in cases:
        coverage = scan_wire_ends_on_pin_lines(
            source_bytes,
            source_path=source_path,
            kicad_version="10.0.6",
            unconnected_pins=unconnected_pins,
        )
        result.update(item.rule_id for item in candidates(observed(), schematic_geometry=coverage))
    return result
