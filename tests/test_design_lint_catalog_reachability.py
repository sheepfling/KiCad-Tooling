"""Active rules must be emitted by synthetic reachability cases."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import tests.component_peer_pin_support as _component_peer_pin_support
import tests.component_peer_power_input_support as _component_peer_power_input_support
import tests.connector_footprint_peer_support as _connector_footprint_peer_support
import tests.design_lint_fixtures as _tests_design_lint_fixtures
import tests.design_lint_fixtures.component_peer_pin_all_open as _component_peer_pin_all_open
import tests.design_lint_fixtures.component_return_domains as _component_return_domains
import tests.design_lint_fixtures.connector_mapped_supply_return_net as _mapped_supply_return_net
import tests.design_lint_fixtures.connector_named_power_aliases as _connector_named_power_aliases
import tests.design_lint_fixtures.connector_peer_pin_all_open as _connector_peer_pin_all_open
import tests.design_lint_fixtures.connector_return_supply as _connector_return_supply_fixtures
import tests.design_lint_fixtures.i2c_addresses as _tests_i2c_address_fixtures
import tests.design_lint_fixtures.i2c_signal_label as _i2c_signal_label_fixtures
import tests.design_lint_fixtures.ic_decoupling as _ic_decoupling_fixtures
import tests.design_lint_fixtures.mosfet_gate_source_bias as _mosfet_gate_source_bias_fixtures
import tests.design_lint_fixtures.mosfet_terminal_same_net as _mosfet_terminal_same_net_fixtures
import tests.design_lint_fixtures.power_input_paths as _power_input_paths
import tests.design_lint_fixtures.power_pin_net_roles as _power_pin_net_roles
import tests.design_lint_fixtures.repeated_signal_pin_functions as _repeated_signal_pin_fixtures
import tests.external_protection_support as _external_protection_support
import tests.rs485_peer_reference_support as _rs485_peer_reference_support
import tests.test_can_excess_termination as _tests_test_can_excess_termination
import tests.test_connector_mapped_interface_other_named_rail as _tests_test_mapped_other_rail
import tests.test_connector_mapped_interface_other_unassigned as _tests_test_mapped_other_contact
import tests.test_connector_mapped_interface_power_contact_unassigned as _tests_test_mapped_power_contact
import tests.test_connector_mapped_interface_shield_on_return_net as _tests_test_mapped_shield_return
import tests.test_connector_mapped_interface_shield_on_supply_rail as _tests_test_mapped_shield_supply
import tests.test_connector_mapped_interface_signal_on_named_rail as _tests_test_mapped_signal_rail
import tests.test_connector_peer_comparison_scope_singleton as _tests_test_scope_singleton
import tests.test_connector_return_distribution as _tests_test_connector_return_distribution
import tests.test_crystal_networks as _tests_test_crystal_networks
import tests.test_led_output_heuristics as _tests_test_led_output_heuristics
import tests.test_mosfet_gate_connectivity as _tests_test_mosfet_gate_connectivity
import tests.test_open_drain_heuristics as _tests_test_open_drain_heuristics
import tests.test_power_paths as _tests_test_power_paths
import tests.test_rc_filters as _tests_test_rc_filters
import tests.test_regulator_feedback as _tests_test_regulator_feedback
import tests.test_stm32_pin_map as _tests_test_stm32_pin_map
import tests.test_usb_c_ports as _tests_test_usb_c_ports
import tests.usb_data_path_support as _usb_data_path_support
import tests.usb_peer_reference_support as _usb_peer_reference_support
from kicad_tooling.hwrepo.design_lint import candidates, evaluate, rule_catalog
from kicad_tooling.hwrepo.external_protection import evaluate as evaluate_external_protection
from kicad_tooling.hwrepo.i2c_addressing import scan_i2c_address_map
from kicad_tooling.hwrepo.i2c_pullup_heuristics import i2c_pullup_heuristic_coverage
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    NetlistContract,
)
from kicad_tooling.hwrepo.rs485_peer_reference_scan import scan_rs485_peer_references
from kicad_tooling.hwrepo.serial_participants import SerialPeerRosterContext
from kicad_tooling.hwrepo.stm32_pin_map import parse_cubemx_ioc, stm32_pin_map_mismatches
from kicad_tooling.hwrepo.stm32_pin_map_models import Stm32PinMapCoverageReport
from kicad_tooling.hwrepo.usb_c_ports import UsbCPortRosterContext
from tests.design_lint_fixtures.catalog_reachability import (
    catalog_reachability_rule_ids,
    protocol_peer_candidate_rule_ids,
)
from tests.design_lint_fixtures.catalog_reachability_pcb import pcb_rule_ids
from tests.design_lint_fixtures.component_catalog_reachability import (
    reachable_component_rule_ids,
)
from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)
from tests.electrical_i2c_support import i2c_series_pullup_netlist
from tests.power_sequence_support import (
    power_sequence_map as synthetic_power_sequence_map,
)
from tests.power_sequence_support import (
    power_sequence_netlist as synthetic_power_sequence_netlist,
)
from tests.serial_participant_support import serial_netlist as serial_participant_netlist

pytestmark = pytest.mark.design_lint


def test_every_active_rule_is_reachable_from_synthetic_cases() -> None:
    component_pins = NetlistContract(
        components={},
        nets={"DATA": ("J1.2",)},
        component_symbols={"J1": "Synthetic:Port"},
        pin_functions={"J1.1": "VCC", "J1.2": "TX", "J1.3": "GND"},
    )
    unroled_return_labels = NetlistContract(
        components={},
        nets={"USB_GND": ("J1.7",), "SERIAL_RETURN": ("J2.7",)},
        component_symbols={"J1": "Synthetic:DB9-A", "J2": "Synthetic:DB9-B"},
        pin_functions={"J1.7": "7", "J2.7": "7"},
    )
    numbered_power_rails = NetlistContract(
        components={},
        nets={"+5V_1": ("J1.1",), "5V-2": ("J2.1",)},
        component_symbols={"J1": "Synthetic:PowerIn", "J2": "Synthetic:PowerOut"},
        pin_functions={"J1.1": "1", "J2.1": "1"},
    )
    no_can_assignments = _tests_design_lint_fixtures.can_netlist().model_copy(update={"nets": {}})
    cases = (
        _tests_design_lint_fixtures.observed(),
        _tests_design_lint_fixtures.generic_connector_power_input_netlist(),
        _tests_design_lint_fixtures.generic_connector_power_output_netlist(),
        _tests_design_lint_fixtures.connector_capacitor_only_netlist(),
        _power_input_paths.source_path_netlist(wrong_rail=True),
        _tests_design_lint_fixtures.peer_connector_pin_assignments(),
        *_connector_footprint_peer_support.peer_pin_reachability_netlists(),
        _connector_named_power_aliases.named_connector_power_alias_netlist(),
        _connector_named_power_aliases.named_connector_power_alias_netlist(
            assignments=(None, None)
        ),
        _connector_named_power_aliases.named_connector_power_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
        ),
        _connector_named_power_aliases.named_connector_power_alias_netlist(
            assignments=(None, None),
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
        ),
        _connector_named_power_aliases.named_connector_power_alias_netlist(
            assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"),
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
        ),
        _connector_named_power_aliases.named_connector_power_alias_netlist(
            assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"),
            target_functions=("BIAS_IN", "BIAS_IN"),
            target_types=("power_in", "power_in"),
        ),
        _connector_peer_pin_all_open.generic_open_peer_netlist(),
        _component_peer_pin_all_open.generic_component_peer_netlist(),
        _component_peer_pin_all_open.generic_component_peer_mixed_netlist(),
        _component_peer_pin_support.peer_component_pin_netlist(
            references=("U1", "U2", "U3"),
            pin_nets=("DATA_A", "DATA_A", "DATA_B"),
            default_symbol="Synthetic:GenericPeer",
            pin_electrical_types=("passive", "passive", "passive"),
            pin_function="Pin_2",
        ),
        _tests_design_lint_fixtures.peer_connector_pin_assignments(("PORT_A", "PORT_B")),
        unroled_return_labels,
        numbered_power_rails,
        _tests_design_lint_fixtures.multiconductor_connector(return_named=False),
        _connector_return_supply_fixtures.return_pin_positive_rail_netlist(),
        component_pins,
        _tests_design_lint_fixtures.unconnected_component_power_pins(),
        _tests_design_lint_fixtures.ic_power_decoupling_fixture(),
        _tests_design_lint_fixtures.led_rail_bridge_netlist(),
        _tests_test_led_output_heuristics.output_led_netlist(),
        _tests_design_lint_fixtures.repeated_component_supply_pins(),
        _component_return_domains.component_return_pin_domains(),
        _repeated_signal_pin_fixtures.repeated_signal_pin_component(),
        _repeated_signal_pin_fixtures.repeated_signal_pin_with_unassigned_member(),
        _repeated_signal_pin_fixtures.repeated_signal_pin_split_assignments_with_open_member(),
        _tests_design_lint_fixtures.peer_component_power_pins(),
        _component_peer_power_input_support.generic_peer_power_input_netlist(),
        _component_peer_power_input_support.named_peer_power_input_netlist(),
        _component_peer_power_input_support.named_peer_power_input_netlist(
            assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B")
        ),
        _component_peer_power_input_support.named_peer_power_input_netlist(
            assignments=(None, None)
        ),
        _power_pin_net_roles.positive_supply_on_return_netlist(),
        _power_pin_net_roles.supply_pin_on_rail_netlist("-5V"),
        no_can_assignments,
        _i2c_signal_label_fixtures.i2c_signal_same_net_netlist(),
        _tests_design_lint_fixtures.can_peer_netlist(divergent_peer=True),
        _tests_test_can_excess_termination._can_netlist_with_direct_terminators(
            ("108R", "120R", "132R")
        ),
        _usb_peer_reference_support.usb_peer_netlist(),
    )
    emitted = {item.rule_id for source in cases for item in candidates(source)}
    mapped_supply_source = _mapped_supply_return_net.mapped_supply_return_net_netlist()
    mapped_supply_report, _ = _mapped_supply_return_net.mapped_supply_return_net_report(
        mapped_supply_source
    )
    emitted.update(item.rule_id for item in mapped_supply_report.findings)
    emitted.update(protocol_peer_candidate_rule_ids())
    emitted.update(item.rule_id for item in candidates(_mosfet_gate_source_bias_fixtures.netlist()))
    emitted.update(
        item.rule_id
        for item in candidates(
            _mosfet_terminal_same_net_fixtures.mosfet_terminal_same_net_netlist(pair="gate-source")
        )
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            _mosfet_terminal_same_net_fixtures.mosfet_terminal_same_net_netlist(pair="gate-drain")
        )
    )
    emitted.update(
        item.rule_id for item in candidates(_tests_test_mosfet_gate_connectivity.mosfet_netlist())
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            _usb_data_path_support.usb_netlist(fault="missing-dp-resistor"),
            usb_data_path_map=_usb_data_path_support.usb_data_map(),
        )
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            _tests_test_power_paths.power_path_netlist(fault="open-element"),
            power_path_map=_tests_test_power_paths.power_path_map(),
        )
    )
    emitted.update(_ic_decoupling_fixtures.catalog_reachability_rule_ids())
    emitted.update(
        item.rule_id
        for item in candidates(
            synthetic_power_sequence_netlist(fault="open-enable"),
            power_sequence_map=synthetic_power_sequence_map(),
        )
    )
    stm32_ioc = (
        (Path(__file__).parent / "fixtures/design_lint/stm32-pin-map/valid.ioc")
        .read_bytes()
        .replace(b"PB6.Signal=I2C1_SCL", b"PB6.Signal=I2C1_SDA")
    )
    stm32_map = _tests_test_stm32_pin_map.sample_map()
    stm32_netlist = _tests_test_stm32_pin_map.sample_netlist()
    stm32_ioc_sha256 = hashlib.sha256(stm32_ioc).hexdigest()
    stm32_coverage = Stm32PinMapCoverageReport(
        status="COMPLETE",
        mode="review",
        map_sha256="b" * 64,
        netlist_sha256="a" * 64,
        ioc_source_hashes={"firmware/controller.ioc": stm32_ioc_sha256},
        mapped_pin_count=len(stm32_map.pins),
        excluded_pin_count=len(stm32_map.exclusions),
        mismatches=stm32_pin_map_mismatches(
            stm32_map,
            stm32_netlist,
            parse_cubemx_ioc(stm32_ioc),
            ioc_sha256=stm32_ioc_sha256,
            map_sha256="b" * 64,
            netlist_sha256="a" * 64,
        ),
    )
    emitted.update(
        item.rule_id for item in candidates(stm32_netlist, stm32_pin_map_coverage=stm32_coverage)
    )
    for source, signal_names in (
        (signal_sharing_netlist(), ("CONTROL_A", "CONTROL_B")),
        (
            signal_sharing_netlist(first_net="CONTACT_NET_A", second_net="CONTACT_NET_B"),
            ("CONTROL_A", "control_a"),
        ),
    ):
        mapped_coverage = signal_sharing_coverage(source, signal_names=signal_names)
        mapped_report, _ = signal_sharing_report(source, coverage=mapped_coverage)
        emitted.update(item.rule_id for item in mapped_report.findings)
    i2c_pullup_source = i2c_series_pullup_netlist()
    i2c_pullup_coverage = i2c_pullup_heuristic_coverage(
        i2c_pullup_source,
        netlist_sha256="a" * 64,
        source_path="projects/synthetic/electrical.json",
        source_sha256="b" * 64,
        state="not_configured",
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            i2c_pullup_source,
            i2c_pullup_heuristic_coverage=i2c_pullup_coverage,
        )
    )
    emitted.update(pcb_rule_ids())
    mapped_power_report, _ = _tests_test_mapped_power_contact._report(
        _tests_test_mapped_power_contact._source(), role="supply"
    )
    emitted.update(item.rule_id for item in mapped_power_report.findings)
    mapped_other_report, _ = _tests_test_mapped_other_contact._report()
    emitted.update(item.rule_id for item in mapped_other_report.findings)
    mapped_other_rail_report, _ = _tests_test_mapped_other_rail._report(
        _tests_test_mapped_other_rail._netlist()
    )
    emitted.update(item.rule_id for item in mapped_other_rail_report.findings)
    mapped_signal_rail_report, _ = _tests_test_mapped_signal_rail._report(
        _tests_test_mapped_signal_rail.mapped_named_rail_netlist(target_net="GND")
    )
    emitted.update(item.rule_id for item in mapped_signal_rail_report.findings)
    mapped_shield_return_report, _ = _tests_test_mapped_shield_return._report(
        _tests_test_mapped_shield_return.mapped_named_rail_netlist(target_net="RET")
    )
    emitted.update(item.rule_id for item in mapped_shield_return_report.findings)
    mapped_shield_supply_report, _ = _tests_test_mapped_shield_supply._report(
        _tests_test_mapped_shield_supply.mapped_named_rail_netlist(target_net="+5V")
    )
    emitted.update(item.rule_id for item in mapped_shield_supply_report.findings)
    scoped_returns, scoped_coverage = _tests_test_scope_singleton.two_usb_one_serial_return_case(
        common_return=True,
        return_comparison_groups={
            "J1": "usb-returns",
            "J2": "serial-return",
            "J3": "usb-returns",
        },
    )
    scoped_report = _tests_test_scope_singleton._report(scoped_returns, scoped_coverage)
    emitted.update(item.rule_id for item in scoped_report.findings)
    i2c_specification = _tests_i2c_address_fixtures.address_map(
        _tests_i2c_address_fixtures.responder("U1", address=80),
        _tests_i2c_address_fixtures.responder("U2", address=81, strap=False),
    )
    i2c_observed = _tests_i2c_address_fixtures.address_netlist(
        i2c_specification, strap_values={"U1": 1}
    )
    i2c_coverage = scan_i2c_address_map(i2c_specification, i2c_observed, "b" * 64)
    emitted.update(
        item.rule_id for item in candidates(i2c_observed, i2c_address_coverage=i2c_coverage)
    )
    emitted.update(catalog_reachability_rule_ids())
    unreviewed_protection = evaluate_external_protection(
        None,
        _external_protection_support.observed_netlist(),
        _external_protection_support.connector_coverage(),
        "a" * 64,
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            _external_protection_support.observed_netlist(),
            external_protection_coverage=unreviewed_protection,
        )
    )
    mismatched_protection = evaluate_external_protection(
        _external_protection_support.protection_map(),
        _external_protection_support.observed_netlist(fault="protector-wrong-net"),
        _external_protection_support.connector_coverage(),
        "b" * 64,
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            _external_protection_support.observed_netlist(fault="protector-wrong-net"),
            external_protection_coverage=mismatched_protection,
        )
    )
    crystal_fault = _tests_test_crystal_networks.crystal_netlist(c1_value="47pF", c2_value="47pF")
    crystal_report = evaluate(
        "synthetic-crystal",
        _tests_design_lint_fixtures.coach(crystal_fault),
        DesignLintPolicy(crystal_network_map=_tests_test_crystal_networks.crystal_map()),
    )
    emitted.update(item.rule_id for item in crystal_report.findings)
    feedback_result = _tests_test_regulator_feedback.report(
        _tests_test_regulator_feedback.regulator_netlist(fault="upper-resistor-outside-range"),
        _tests_test_regulator_feedback.regulator_feedback_map(),
    )
    emitted.update(item.rule_id for item in feedback_result.findings)
    rc_filter_result = evaluate(
        "synthetic-rc-filter",
        _tests_design_lint_fixtures.coach(
            _tests_test_rc_filters.rc_filter_netlist(capacitor_value="220nF")
        ),
        DesignLintPolicy(rc_filter_map=_tests_test_rc_filters.rc_filter_map()),
    )
    emitted.update(item.rule_id for item in rc_filter_result.findings)
    connector_distribution_result = _tests_test_connector_return_distribution.lint_report(
        ("signal",) * 6 + ("return", "supply", "shield"),
        policy=DesignLintPolicy(
            connector_return_distribution_map=_tests_test_connector_return_distribution.distribution_map()
        ),
    )
    emitted.update(item.rule_id for item in connector_distribution_result.findings)
    emitted.update(reachable_component_rule_ids())
    peer_power_output_result = _component_peer_pin_support.lint_report(
        _component_peer_pin_support.peer_power_output_netlist()
    )
    emitted.update(item.rule_id for item in peer_power_output_result.findings)
    peer_signal_output_result = _component_peer_pin_support.lint_report(
        _component_peer_pin_support.peer_power_output_netlist(
            output_electrical_types=("output", "output")
        )
    )
    emitted.update(item.rule_id for item in peer_signal_output_result.findings)
    peer_signal_input_result = _component_peer_pin_support.lint_report(
        _component_peer_pin_support.peer_signal_input_netlist()
    )
    emitted.update(item.rule_id for item in peer_signal_input_result.findings)
    peer_bidirectional_result = _component_peer_pin_support.lint_report(
        _component_peer_pin_support.peer_bidirectional_netlist()
    )
    emitted.update(item.rule_id for item in peer_bidirectional_result.findings)
    emitted.update(
        item.rule_id
        for item in candidates(_tests_design_lint_fixtures.generic_component_power_input_netlist())
    )
    emitted.update(
        item.rule_id
        for item in candidates(_tests_design_lint_fixtures.generic_component_power_output_netlist())
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            _tests_test_usb_c_ports.usb_c_netlist(),
            usb_c_port_roster=UsbCPortRosterContext(state="not_configured"),
        )
    )
    emitted.update(
        item.rule_id for item in candidates(_tests_test_open_drain_heuristics.signal_netlist())
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            _tests_test_open_drain_heuristics.signal_netlist(output_type="open_emitter")
        )
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            serial_participant_netlist(),
            serial_peer_roster=SerialPeerRosterContext(state="not_configured"),
        )
    )
    _, rs485_context, rs485_source = _rs485_peer_reference_support.rs485_peer_reference_fixture(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_A"}
    )
    rs485_scan = scan_rs485_peer_references(rs485_context, rs485_source)
    emitted.update(
        item.rule_id for item in candidates(rs485_source, rs485_peer_reference_scan=rs485_scan)
    )
    active = {item.rule_id for item in rule_catalog().rules if item.status == "active"}
    assert emitted == active
