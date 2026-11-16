"""Synthetic cases for design-lint catalog reachability checks."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines
from tests.connector_footprint_peer_support import (
    named_passive_contact_divergence_netlist,
    named_passive_contact_open_netlist,
    named_power_output_all_open_netlist,
    named_signal_all_open_netlist,
    named_signal_mode_dependent_open_netlist,
    peer_metadata_divergence_netlist,
    peer_netlist,
)
from tests.connector_peer_unanchored_scope_support import (
    PEER_GROUP,
    lint_report,
    reviewed_coverage,
)
from tests.design_lint_fixtures import (
    observed,
    schematic_geometry_fixtures,
)
from tests.design_lint_fixtures.bjt_base_bias import bjt_base_bias_netlist
from tests.design_lint_fixtures.bjt_base_drive import bjt_base_drive_netlist
from tests.design_lint_fixtures.bjt_collector_emitter_same_net import (
    bjt_base_collector_netlist,
    bjt_base_emitter_netlist,
    bjt_collector_emitter_netlist,
)
from tests.design_lint_fixtures.bjt_terminal_order import bjt_terminal_order_netlist
from tests.design_lint_fixtures.catalog_reachability_mapped_connectors import (
    mapped_connector_rule_ids,  # noqa: F401
)
from tests.design_lint_fixtures.catalog_reachability_usb_c import (
    usb_c_vbus_and_connector_return_review_rule_ids,  # noqa: F401
)
from tests.design_lint_fixtures.component_supply_voltage_ranges import (
    supply_range_map,
    supply_range_map_coverage_netlist,
    supply_range_netlist,
)
from tests.design_lint_fixtures.connector_coverage import (
    connector_supply_role_catalog,
    connector_supply_role_netlist,
    connector_supply_role_reviews,
    inventory_review,
)
from tests.design_lint_fixtures.connector_return_catalog_reachability import (
    connector_return_catalog_rule_ids,
)
from tests.design_lint_fixtures.diode_rail_orientation import netlist as diode_rail_netlist
from tests.design_lint_fixtures.ethernet_data_labels import ethernet_data_label_netlist
from tests.design_lint_fixtures.ethernet_data_unconnected import (
    ethernet_data_unconnected_netlist,
)
from tests.design_lint_fixtures.ethernet_management_labels import ethernet_management_netlist
from tests.design_lint_fixtures.mosfet_drain_source_same_net import mosfet_drain_source_netlist
from tests.design_lint_fixtures.mosfet_gate_direct_drive import netlist as mosfet_gate_drive_netlist
from tests.design_lint_fixtures.mosfet_terminal_order import mosfet_terminal_order_netlist
from tests.design_lint_fixtures.pcb_differential_pair_reference_via import (
    reference_via_candidate_ids,
)
from tests.design_lint_fixtures.polarized_capacitor import netlist as polarized_capacitor_netlist
from tests.design_lint_fixtures.serial_endpoint_role_collision import (
    serial_endpoint_role_netlist,
)
from tests.design_lint_fixtures.usb_c_sbu_named_rail import usb_c_sbu_named_rail_netlist
from tests.schematic_erc_exclusion_support import source_bound_erc_exclusion_rule_ids
from tests.test_connector_mapped_interface_signal_unassigned import _coverage, _netlist
from tests.test_connector_stateful_contacts import _map as _stateful_contact_map
from tests.test_connector_stateful_contacts import _observed as _stateful_contact_netlist
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
    result.update(item.rule_id for item in candidates(serial_endpoint_role_netlist()))
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
    result.update(item.rule_id for item in candidates(polarized_capacitor_netlist()))
    result.update(item.rule_id for item in candidates(diode_rail_netlist()))
    result.update(item.rule_id for item in candidates(mosfet_terminal_order_netlist()))
    result.update(item.rule_id for item in candidates(bjt_terminal_order_netlist()))
    result.update(item.rule_id for item in candidates(bjt_collector_emitter_netlist()))
    result.update(item.rule_id for item in candidates(bjt_base_emitter_netlist()))
    result.update(item.rule_id for item in candidates(bjt_base_collector_netlist()))
    result.update(
        item.rule_id
        for item in candidates(
            supply_range_netlist(input_net="3V3"),
            component_supply_voltage_range_map=supply_range_map(),
        )
    )
    result.update(
        item.rule_id
        for item in candidates(
            supply_range_map_coverage_netlist(),
            component_supply_voltage_range_map=supply_range_map(),
        )
    )
    result.update(item.rule_id for item in candidates(bjt_base_drive_netlist()))
    result.update(item.rule_id for item in candidates(bjt_base_bias_netlist()))
    supply_domain_netlist = connector_supply_role_netlist(common_supply=True)
    supply_domain_catalog = connector_supply_role_catalog(serial_voltage_domain="serial-vbus")
    supply_domain_coverage = evaluate_connector_coverage(
        supply_domain_netlist,
        tuple(sorted(supply_domain_catalog)),
        connector_supply_role_reviews(),
        interfaces=supply_domain_catalog,
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="d" * 64,
        inventory_review=inventory_review(),
    )
    result.update(
        item.rule_id
        for item in candidates(
            supply_domain_netlist,
            connector_coverage=supply_domain_coverage,
        )
    )
    result.update(item.rule_id for item in candidates(mosfet_gate_drive_netlist()))
    result.update(item.rule_id for item in candidates(mosfet_drain_source_netlist()))
    result.update(
        item.rule_id
        for item in candidates(
            _stateful_contact_netlist(tip_pair_same_net=True),
            connector_stateful_contact_map=_stateful_contact_map(),
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
    mapped_power_source = _netlist()
    result.update(
        item.rule_id
        for item in candidates(
            mapped_power_source,
            connector_coverage=_coverage(mapped_power_source, target_role="return"),
        )
    )
    result.update(
        item.rule_id
        for item in candidates(
            ethernet_data_label_netlist(
                functions=("TDP", "TDN", "RDP", "RDN"),
                labels=("ETH_RX_P", "ETH_RX_N", "ETH_TX_P", "ETH_TX_N"),
            )
        )
    )
    result.update(
        item.rule_id for item in candidates(ethernet_data_unconnected_netlist(open_pins=("U1.1",)))
    )
    result.update(item.rule_id for item in candidates(ethernet_management_netlist()))
    result.update(
        item.rule_id
        for item in candidates(ethernet_management_netlist(reference="J1", labels=("GND", "+3V3")))
    )
    result.update(item.rule_id for item in candidates(usb_c_sbu_named_rail_netlist(reference="J1")))
    result.update(
        item.rule_id for item in candidates(ethernet_management_netlist(open_functions=("MDC",)))
    )
    result.update(
        item.rule_id for item in candidates(ethernet_management_netlist(labels=("GND", "ETH_MDIO")))
    )
    result.update(
        item.rule_id
        for item in candidates(ethernet_management_netlist(labels=("ETH_MDIO", "ETH_MDC")))
    )
    peer_assignments = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    peer_coverages = (
        None,
        reviewed_coverage(peer_assignments, (None, None)),
        reviewed_coverage(peer_assignments, (PEER_GROUP, PEER_GROUP)),
    )
    result.update(
        item.rule_id
        for coverage in peer_coverages
        for item in lint_report(peer_assignments, coverage).findings
    )
    result.update(connector_return_catalog_rule_ids())
    result.update(source_bound_erc_exclusion_rule_ids())
    result.update(reference_via_candidate_ids(Path(__file__).resolve().parent))
    return result
