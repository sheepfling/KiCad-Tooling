"""Active rules must be emitted by synthetic reachability cases."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import tests.component_peer_pin_support as _component_peer_pin_support
import tests.design_lint_fixtures as _tests_design_lint_fixtures
import tests.design_lint_fixtures.i2c_addresses as _tests_i2c_address_fixtures
import tests.design_lint_fixtures.pcb_reference_planes as _pcb_reference_plane_fixtures
import tests.design_lint_fixtures.pcb_switching_loop as _pcb_switching_loop_fixtures
import tests.design_lint_fixtures.power_input_paths as _power_input_paths
import tests.external_protection_support as _external_protection_support
import tests.pcb_decoupling_support as _pcb_decoupling_support
import tests.pcb_rf_antenna_support as _pcb_rf_antenna_support
import tests.serial_peer_reference_support as _serial_peer_reference_support
import tests.test_connector_return_distribution as _tests_test_connector_return_distribution
import tests.test_crystal_networks as _tests_test_crystal_networks
import tests.test_led_output_heuristics as _tests_test_led_output_heuristics
import tests.test_open_drain_heuristics as _tests_test_open_drain_heuristics
import tests.test_pcb_drc_coverage as _tests_test_pcb_drc_coverage
import tests.test_pcb_keepouts as _tests_test_pcb_keepouts
import tests.test_pcb_protection_path as _tests_test_pcb_protection_path
import tests.test_pcb_track_width as _tests_test_pcb_track_width
import tests.test_power_paths as _tests_test_power_paths
import tests.test_rc_filters as _tests_test_rc_filters
import tests.test_regulator_feedback as _tests_test_regulator_feedback
import tests.test_spi_participants as _tests_test_spi_participants
import tests.test_stm32_pin_map as _tests_test_stm32_pin_map
import tests.test_two_pin_crystals as _tests_test_two_pin_crystals
import tests.test_two_pin_diodes as _tests_test_two_pin_diodes
import tests.test_two_pin_ferrites as _tests_test_two_pin_ferrites
import tests.test_two_pin_fuses as _tests_test_two_pin_fuses
import tests.test_two_pin_passives as _tests_test_two_pin_passives
import tests.test_two_pin_switches as _tests_test_two_pin_switches
import tests.test_usb_c_ports as _tests_test_usb_c_ports
import tests.usb_data_path_support as _usb_data_path_support
import tests.usb_peer_reference_support as _usb_peer_reference_support
from kicad_tooling.hwrepo.design_lint import candidates, evaluate, rule_catalog
from kicad_tooling.hwrepo.external_protection import evaluate as evaluate_external_protection
from kicad_tooling.hwrepo.i2c_addressing import scan_i2c_address_map
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    NetlistContract,
    PcbRfModuleAntennaMap,
    Stm32PinMapCoverageReport,
)
from kicad_tooling.hwrepo.serial_participants import SerialPeerRosterContext
from kicad_tooling.hwrepo.stm32_pin_map import parse_cubemx_ioc, stm32_pin_map_mismatches
from kicad_tooling.hwrepo.usb_c_ports import UsbCPortRosterContext
from tests.design_lint_fixtures.catalog_reachability import schematic_geometry_rule_ids
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
        _tests_design_lint_fixtures.connector_capacitor_only_netlist(),
        _power_input_paths.source_path_netlist(wrong_rail=True),
        _tests_design_lint_fixtures.peer_connector_pin_assignments(),
        _tests_design_lint_fixtures.peer_connector_pin_assignments(("PORT_A", "PORT_B")),
        unroled_return_labels,
        numbered_power_rails,
        _tests_design_lint_fixtures.multiconductor_connector(return_named=False),
        component_pins,
        _tests_design_lint_fixtures.unconnected_component_power_pins(),
        _tests_design_lint_fixtures.ic_power_decoupling_fixture(),
        _tests_design_lint_fixtures.led_rail_bridge_netlist(),
        _tests_test_led_output_heuristics.output_led_netlist(),
        _tests_design_lint_fixtures.repeated_component_supply_pins(),
        _tests_design_lint_fixtures.peer_component_power_pins(),
        _tests_design_lint_fixtures.control_input_pins(),
        _tests_design_lint_fixtures.control_input_pins(connected=True, visible_bias=False),
        _tests_design_lint_fixtures.unconnected_protocol_pins(),
        _tests_test_spi_participants.spi_netlist(),
        _tests_design_lint_fixtures.spi_peer_voltage_netlist(),
        _tests_design_lint_fixtures.serial_peer_voltage_netlist(),
        _serial_peer_reference_support.serial_reference_netlist(),
        _usb_peer_reference_support.usb_peer_netlist(),
        _tests_design_lint_fixtures.i2c_netlist(),
        _tests_design_lint_fixtures.i2c_netlist_with_parallel_sda(),
        _tests_design_lint_fixtures.i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",)),
        _tests_design_lint_fixtures.spi_active_low_select_netlist(),
        _tests_design_lint_fixtures.can_netlist(),
        _tests_design_lint_fixtures.can_peer_netlist(divergent_peer=True),
        no_can_assignments,
        _tests_design_lint_fixtures.complementary_usb_netlist(negative_net=None),
        _tests_design_lint_fixtures.complementary_usb_netlist(),
    )
    emitted = {item.rule_id for source in cases for item in candidates(source)}
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
    emitted.update(schematic_geometry_rule_ids())
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
    decoupling_map = _pcb_decoupling_support.mapping(
        _pcb_decoupling_support.requirement(maximum_um=None)
    )
    decoupling_result = evaluate(
        "synthetic-decoupling",
        _tests_design_lint_fixtures.coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_decoupling_map=decoupling_map),
        pcb_decoupling_coverage=_pcb_decoupling_support.coverage_report(
            decoupling_map, _pcb_decoupling_support.snapshot()
        ),
    )
    emitted.update(item.rule_id for item in decoupling_result.findings)
    protection_path_map = _tests_test_pcb_protection_path.mapping()
    protection_path_result = evaluate(
        "synthetic-protection-path",
        _tests_design_lint_fixtures.coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_protection_path_map=protection_path_map),
        pcb_protection_path_coverage=_tests_test_pcb_protection_path.coverage_report(
            protection_path_map,
            _tests_test_pcb_protection_path.snapshot(
                entry_distance_nm=100001, via_offsets_nm=(2900000,)
            ),
        ),
    )
    emitted.update(item.rule_id for item in protection_path_result.findings)
    track_width_map = _tests_test_pcb_track_width.mapping(
        _tests_test_pcb_track_width.requirement(minimum_um=251)
    )
    track_width_result = evaluate(
        "synthetic-track-width",
        _tests_design_lint_fixtures.coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_track_width_map=track_width_map),
        pcb_track_width_coverage=_tests_test_pcb_track_width.coverage(
            track_width_map,
            _tests_test_pcb_track_width.snapshot(
                _tests_test_pcb_track_width.track("001", "VDD", 250000)
            ),
        ),
    )
    emitted.update(item.rule_id for item in track_width_result.findings)
    reference_hole = (
        (4000000, 4000000),
        (6000000, 4000000),
        (6000000, 6000000),
        (4000000, 6000000),
    )
    reference_map = _pcb_reference_plane_fixtures.mapping()
    reference_result = evaluate(
        "synthetic-reference-plane",
        _tests_design_lint_fixtures.coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_reference_plane_map=reference_map),
        pcb_reference_plane_coverage=_pcb_reference_plane_fixtures.report(
            reference_map,
            _pcb_reference_plane_fixtures.snapshot(
                _pcb_reference_plane_fixtures.track(),
                zones=(
                    _pcb_reference_plane_fixtures.zone(
                        "00000000-0000-0000-0000-000000000001", holes=(reference_hole,)
                    ),
                ),
            ),
        ),
    )
    emitted.update(item.rule_id for item in reference_result.findings)
    switching_loop_map = _pcb_switching_loop_fixtures.mapping()
    switching_loop_result = evaluate(
        "synthetic-switching-loop",
        _tests_design_lint_fixtures.coach(_tests_design_lint_fixtures.observed()),
        DesignLintPolicy(pcb_switching_loop_map=switching_loop_map),
        pcb_switching_loop_coverage=_pcb_switching_loop_fixtures.coverage(
            switching_loop_map, _pcb_switching_loop_fixtures.snapshot(expanded=True)
        ),
    )
    emitted.update(item.rule_id for item in switching_loop_result.findings)
    pair_result = evaluate(
        "synthetic-differential-pair",
        _tests_design_lint_fixtures.coach(_tests_design_lint_fixtures.observed()),
        DesignLintPolicy(pcb_differential_pair_rule_map=_tests_test_pcb_drc_coverage.pair_map()),
        pcb_differential_pair_coverage=_tests_test_pcb_drc_coverage.incomplete_report(),
    )
    emitted.update(item.rule_id for item in pair_result.findings)
    from tests.design_lint_fixtures.pcb_signal_path import incomplete_signal_report, path_map

    emitted.update(
        item.rule_id
        for item in candidates(
            _tests_design_lint_fixtures.observed(),
            pcb_signal_path_coverage=incomplete_signal_report(path_map()),
        )
    )
    keepout_map = _tests_test_pcb_keepouts.mapping_for()
    keepout_result = evaluate(
        "synthetic-keepout",
        _tests_design_lint_fixtures.coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_keepout_map=keepout_map),
        pcb_keepout_coverage=_tests_test_pcb_keepouts.incomplete_report(keepout_map),
    )
    emitted.update(item.rule_id for item in keepout_result.findings)
    rf_antenna_map = PcbRfModuleAntennaMap(
        basis="Synthetic catalog reachability requirement",
        requirements=(_pcb_rf_antenna_support.requirement(),),
    )
    rf_antenna_result = _pcb_rf_antenna_support.lint_report(
        policy=DesignLintPolicy(pcb_rf_module_antenna_map=rf_antenna_map),
        source_netlist=_pcb_rf_antenna_support.netlist(symbol="RF_Module:Other"),
        observed_board=_pcb_rf_antenna_support.snapshot(),
    )
    emitted.update(item.rule_id for item in rf_antenna_result.findings)
    passive_result = _tests_test_two_pin_passives.lint_report(
        _tests_test_two_pin_passives.passive_netlist()
    )
    emitted.update(item.rule_id for item in passive_result.findings)
    diode_result = _tests_test_two_pin_diodes.lint_report(
        _tests_test_two_pin_diodes.diode_netlist()
    )
    emitted.update(item.rule_id for item in diode_result.findings)
    crystal_result = _tests_test_two_pin_crystals.lint_report(
        _tests_test_two_pin_crystals.crystal_netlist()
    )
    emitted.update(item.rule_id for item in crystal_result.findings)
    fuse_result = _tests_test_two_pin_fuses.lint_report(_tests_test_two_pin_fuses.fuse_netlist())
    emitted.update(item.rule_id for item in fuse_result.findings)
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
    ferrite_result = _tests_test_two_pin_ferrites.lint_report(
        _tests_test_two_pin_ferrites.ferrite_netlist()
    )
    emitted.update(item.rule_id for item in ferrite_result.findings)
    emitted.update(
        item.rule_id for item in candidates(_tests_test_two_pin_switches.switch_netlist())
    )
    emitted.update(
        item.rule_id
        for item in candidates(_tests_design_lint_fixtures.generic_component_power_input_netlist())
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
    active = {item.rule_id for item in rule_catalog().rules if item.status == "active"}
    assert emitted == active
