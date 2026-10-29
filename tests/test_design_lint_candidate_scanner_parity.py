"""Fault/control parity between the compatibility adapter and typed scanner."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo import design_lint_evaluation_candidates
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_bus_inputs import BusCandidateInputs
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import (
    candidates,
    fingerprint,
    scan_candidates,
    validate_catalogued_candidates,
)
from kicad_tooling.hwrepo.design_lint_candidate_inputs import (
    ComponentCandidateInputs,
    ConnectorCandidateInputs,
    ControlCandidateInputs,
    DesignLintCandidateInputs,
    MappedCandidateInputs,
    PcbCandidateInputs,
    PeerCandidateInputs,
    PowerCandidateInputs,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.i2c_address_inputs import I2cAddressCandidateInput
from kicad_tooling.hwrepo.i2c_pullup_inputs import I2cPullupSnifferInput
from kicad_tooling.hwrepo.models import DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures import coach, i2c_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]


def _candidate_inputs(observed: NetlistContract) -> DesignLintCandidateInputs:
    return DesignLintCandidateInputs(
        observed=observed,
        catalog=None,
        schematic_geometry=None,
        reviewed_connector_references=(),
        connector=ConnectorCandidateInputs(
            coverage=None,
            return_distribution=None,
            stateful_contact_map=None,
            power_output_review_enabled=True,
        ),
        component=ComponentCandidateInputs(
            peer_pin_assignment_scans=None,
            peer_power_output_review_enabled=True,
        ),
        control=ControlCandidateInputs(
            input_bias_coverage=None,
        ),
        power=PowerCandidateInputs(
            component_role_map=None,
            power_path_map=None,
            power_sequence_map=None,
            oscillator_output_path_map=None,
            ic_decoupling_map=None,
        ),
        bus=BusCandidateInputs(
            observed=observed,
            i2c_address=I2cAddressCandidateInput.from_candidate_arguments(observed, None, None),
            i2c_pullup=I2cPullupSnifferInput.from_legacy_arguments(observed, None),
        ),
        peer=PeerCandidateInputs(
            digital_voltage_context=None,
            digital_voltage_scan=None,
            usb_reference_scan=None,
            serial_reference_scan=None,
            serial_roster=None,
            usb_c_port_roster=None,
        ),
        mapped=MappedCandidateInputs(
            external_protection=None,
            crystal_network=None,
            regulator_feedback=None,
            rc_filter=None,
        ),
        pcb=PcbCandidateInputs(
            component_inventory=None,
            decoupling=None,
            protection_path=None,
            track_width=None,
            reference_plane=None,
            switching_loop=None,
            differential_pair=None,
            signal_path=None,
            keepout=None,
            rf_antenna=None,
            touch_pad_clearance=None,
            stm32_pin_map=None,
        ),
        usb_data_path_map=None,
    )


def _legacy_scan(inputs: DesignLintCandidateInputs) -> tuple[Candidate, ...]:
    """Run the old public adapter from the exact typed inputs used by evaluation."""
    items = candidates(
        observed=inputs.observed,
        catalog=inputs.catalog,
        schematic_geometry=inputs.schematic_geometry,
        i2c_address_coverage=inputs.bus.i2c_address.coverage,
        external_protection_coverage=inputs.mapped.external_protection,
        crystal_network_coverage=inputs.mapped.crystal_network,
        regulator_feedback_coverage=inputs.mapped.regulator_feedback,
        rc_filter_coverage=inputs.mapped.rc_filter,
        connector_return_distribution=inputs.connector.return_distribution,
        pcb_decoupling_coverage=inputs.pcb.decoupling,
        pcb_protection_path_coverage=inputs.pcb.protection_path,
        pcb_track_width_coverage=inputs.pcb.track_width,
        pcb_switching_loop_coverage=inputs.pcb.switching_loop,
        pcb_differential_pair_coverage=inputs.pcb.differential_pair,
        pcb_differential_pair_rule_map=inputs.bus.pcb_differential_pair_rule_map,
        i2c_address_map=inputs.bus.i2c_address.address_map,
        usb_data_path_map=inputs.usb_data_path_map,
        stm32_pin_map_coverage=inputs.pcb.stm32_pin_map,
        spi_roster=inputs.bus.spi_roster,
        usb_c_port_roster=inputs.peer.usb_c_port_roster,
        power_path_map=inputs.power.power_path_map,
        power_sequence_map=inputs.power.power_sequence_map,
        pcb_reference_plane_coverage=inputs.pcb.reference_plane,
        control_input_bias_coverage=inputs.control.input_bias_coverage,
        i2c_pullup_heuristic_coverage=inputs.bus.i2c_pullup.coverage,
        digital_peer_voltage_context=inputs.peer.digital_voltage_context,
        component_role_map=inputs.power.component_role_map,
        serial_peer_roster=inputs.peer.serial_roster,
        reviewed_connector_references=inputs.reviewed_connector_references,
        complementary_alias_resolution=inputs.bus.complementary_alias_resolution,
        connector_coverage=inputs.connector.coverage,
        digital_peer_voltage_scan=inputs.peer.digital_voltage_scan,
        usb_peer_reference_scan=inputs.peer.usb_reference_scan,
        serial_peer_reference_scan=inputs.peer.serial_reference_scan,
        pcb_signal_path_coverage=inputs.pcb.signal_path,
        pcb_keepout_coverage=inputs.pcb.keepout,
        pcb_rf_module_antenna_coverage=inputs.pcb.rf_antenna,
        pcb_touch_pad_clearance_coverage=inputs.pcb.touch_pad_clearance,
        peer_pin_assignment_scans=inputs.component.peer_pin_assignment_scans,
        pcb_component_inventory_coverage=inputs.pcb.component_inventory,
        i2c_peer_reference_scan=inputs.bus.i2c_peer_reference_scan,
        spi_peer_reference_scan=inputs.bus.spi_peer_reference_scan,
        can_peer_reference_scan=inputs.bus.can_peer_reference_scan,
        rs485_peer_reference_scan=inputs.bus.rs485_peer_reference_scan,
        peer_power_output_review_enabled=(inputs.component.peer_power_output_review_enabled),
        connector_power_output_review_enabled=(inputs.connector.power_output_review_enabled),
        ic_decoupling_map=inputs.power.ic_decoupling_map,
        oscillator_output_path_map=inputs.power.oscillator_output_path_map,
        connector_stateful_contact_map=inputs.connector.stateful_contact_map,
    )
    all_items = tuple(
        sorted(
            (*items, *inputs.additional_candidates),
            key=lambda item: (item.rule_id, item.subject),
        )
    )
    validate_catalogued_candidates(all_items, inputs.catalog)
    return all_items


@pytest.mark.parametrize(
    ("pullups", "missing_pullup_expected"),
    (((), True), (("SDA", "SCL"), False)),
    ids=("fault", "valid-control"),
)
def test_legacy_and_typed_scanner_match_candidate_and_report_evidence(
    monkeypatch: pytest.MonkeyPatch,
    pullups: tuple[str, ...],
    missing_pullup_expected: bool,
) -> None:
    observed = i2c_netlist(pullups=pullups)
    typed_inputs = _candidate_inputs(observed)
    legacy_items = candidates(observed)
    typed_items = scan_candidates(typed_inputs)

    assert legacy_items == typed_items
    assert tuple(map(fingerprint, legacy_items)) == tuple(map(fingerprint, typed_items))
    assert any(item.rule_id == "bus.i2c_missing_pullup" for item in legacy_items) is (
        missing_pullup_expected
    )
    assert any(item.rule_id == "bus.i2c_missing_pullup" for item in typed_items) is (
        missing_pullup_expected
    )

    typed_report = evaluate("synthetic-scanner-parity", coach(observed), DesignLintPolicy())
    monkeypatch.setattr(design_lint_evaluation_candidates, "scan_candidates", _legacy_scan)
    legacy_report = evaluate("synthetic-scanner-parity", coach(observed), DesignLintPolicy())

    assert legacy_report.model_dump_json() == typed_report.model_dump_json()
