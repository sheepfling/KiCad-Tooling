"""Synthetic cases for design-lint catalog reachability checks."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines
from tests.connector_footprint_peer_support import (
    named_passive_contact_divergence_netlist,
    named_passive_contact_open_netlist,
    named_power_output_all_open_netlist,
    named_signal_all_open_netlist,
    named_signal_mode_dependent_open_netlist,
    peer_metadata_divergence_netlist,
)
from tests.design_lint_fixtures import observed, schematic_geometry_fixtures
from tests.test_connector_mapped_interface_signal_unassigned import _coverage, _netlist
from tests.test_oscillator_output_paths import (
    oscillator_output_netlist,
    oscillator_output_path_map,
)

TESTS = Path(__file__).resolve().parents[1]


def catalog_reachability_rule_ids() -> set[str]:
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
    result.update(
        item.rule_id
        for item in candidates(
            oscillator_output_netlist(resistor_value="1k"),
            oscillator_output_path_map=oscillator_output_path_map(),
        )
    )
    for source in (
        named_signal_all_open_netlist(),
        named_power_output_all_open_netlist(),
        named_signal_mode_dependent_open_netlist(),
        named_passive_contact_open_netlist(),
        named_passive_contact_divergence_netlist(),
    ):
        result.update(item.rule_id for item in candidates(source))
    result.update(item.rule_id for item in candidates(peer_metadata_divergence_netlist()))
    result.update(
        item.rule_id
        for item in candidates(
            peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None))
        )
    )
    mapped_signal_source = _netlist()
    mapped_signal_coverage = _coverage(mapped_signal_source)
    result.update(
        item.rule_id
        for item in candidates(mapped_signal_source, connector_coverage=mapped_signal_coverage)
    )
    mapped_shield_source = _netlist()
    result.update(
        item.rule_id
        for item in candidates(
            mapped_shield_source,
            connector_coverage=_coverage(mapped_shield_source, target_role="shield"),
        )
    )
    return result
