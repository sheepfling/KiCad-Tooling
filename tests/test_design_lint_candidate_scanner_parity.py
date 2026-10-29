"""Fault/control parity between the compatibility adapter and typed scanner."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from kicad_tooling.hwrepo import (
    design_lint_candidate_aggregation,
    design_lint_evaluation_candidates,
)
from kicad_tooling.hwrepo.connector_peer_pin_candidate_results import (
    ConnectorPeerPinFindingCounts,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_bus_candidates import (
    BusCandidateResult,
    scan_bus_candidates,
)
from kicad_tooling.hwrepo.design_lint_bus_inputs import BusCandidateInputs
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import (
    candidates,
    fingerprint,
    scan_candidate_result,
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
from kicad_tooling.hwrepo.design_lint_candidate_results import DesignLintCandidateScanResult
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.external_protection_models import ExternalProtectionCoverageReport
from kicad_tooling.hwrepo.i2c_address_inputs import I2cAddressCandidateInput
from kicad_tooling.hwrepo.i2c_pullup_inputs import I2cPullupSnifferInput
from kicad_tooling.hwrepo.models import DesignLintPolicy, NetlistContract
from kicad_tooling.hwrepo.pcb_drc_rule_coverage import compare_native_rules
from kicad_tooling.hwrepo.peer_reference_candidate_keys import PeerReferenceCandidateKeys
from kicad_tooling.hwrepo.power_path_models import PowerPathMap
from kicad_tooling.hwrepo.power_sequence_models import PowerSequenceMap
from kicad_tooling.hwrepo.spi_participants import SpiRosterContext
from kicad_tooling.hwrepo.usb_data_path_models import UsbDataPathMap
from tests.design_lint_fixtures import coach, control_input_pins, i2c_netlist
from tests.i2c_peer_reference_support import i2c_peer_netlist
from tests.test_pcb_drc_coverage import incomplete_report, pair_map, rules_text

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
        control=ControlCandidateInputs.from_legacy_arguments(observed, None),
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


def _legacy_scan_result(
    inputs: DesignLintCandidateInputs,
) -> DesignLintCandidateScanResult:
    items = _legacy_scan(inputs)
    return DesignLintCandidateScanResult(
        candidates=items,
        peer_reference_keys=PeerReferenceCandidateKeys.from_candidates(items),
        connector_peer_pin_finding_counts=ConnectorPeerPinFindingCounts.from_candidates(items),
    )


def test_scanner_rejects_conflicting_shared_bus_inputs() -> None:
    inputs = _candidate_inputs(i2c_netlist(pullups=()))
    other = i2c_netlist(pullups=("SDA", "SCL"))
    other_bus = _candidate_inputs(other).bus
    with pytest.raises(ValueError, match="one observed native netlist"):
        replace(inputs, bus=other_bus)
    with pytest.raises(ValueError, match="one observed native netlist"):
        replace(inputs, control=_candidate_inputs(other).control)
    with pytest.raises(ValueError, match="reviewed connector references"):
        replace(inputs, bus=replace(inputs.bus, reviewed_connector_references=("J1",)))
    with pytest.raises(ValueError, match="computed by the candidate scanner"):
        replace(
            inputs, bus=replace(inputs.bus, component_peer_findings=candidates(inputs.observed))
        )


def test_scanner_passes_extended_bus_input_to_its_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    @dataclass(frozen=True, slots=True)
    class ExtendedBusInputs(BusCandidateInputs):
        extension_marker: str = "new theme evidence"

    inputs = _candidate_inputs(i2c_netlist(pullups=()))
    extended = ExtendedBusInputs(
        observed=inputs.observed,
        i2c_address=inputs.bus.i2c_address,
        i2c_pullup=inputs.bus.i2c_pullup,
    )
    inputs = replace(inputs, bus=extended)
    received: list[BusCandidateInputs] = []
    original = design_lint_candidate_aggregation.scan_bus_candidates

    def capture(bus: BusCandidateInputs) -> BusCandidateResult:
        received.append(bus)
        return original(bus)

    monkeypatch.setattr(design_lint_candidate_aggregation, "scan_bus_candidates", capture)
    assert scan_candidates(inputs) == candidates(inputs.observed)
    assert len(received) == 2
    assert isinstance(received[0], ExtendedBusInputs)
    assert received[0].extension_marker == "new theme evidence"
    assert received[0].i2c_address is extended.i2c_address
    assert received[0].i2c_pullup is extended.i2c_pullup


def test_bus_scan_returns_typed_peer_identity_alongside_findings() -> None:
    inputs = _candidate_inputs(i2c_peer_netlist())

    result = scan_bus_candidates(inputs.bus)

    assert any(item.rule_id == "bus.i2c_peer_reference_review" for item in result.candidates)
    assert result.peer_reference_keys.i2c_buses == frozenset({("i2c_sda", "i2c_scl")})


def test_candidate_scan_result_preserves_typed_bus_output() -> None:
    inputs = _candidate_inputs(i2c_peer_netlist())

    result = scan_candidate_result(inputs)

    assert isinstance(result, DesignLintCandidateScanResult)
    assert result.candidates == scan_candidates(inputs)
    assert result.peer_reference_keys.i2c_buses == frozenset({("i2c_sda", "i2c_scl")})


def test_scanner_passes_extended_peer_input_to_its_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    @dataclass(frozen=True, slots=True)
    class ExtendedPeerInputs(PeerCandidateInputs):
        extension_marker: str = "new peer evidence"

    inputs = _candidate_inputs(i2c_netlist(pullups=()))
    extended = ExtendedPeerInputs(
        digital_voltage_context=None,
        digital_voltage_scan=None,
        usb_reference_scan=None,
        serial_reference_scan=None,
        serial_roster=None,
        usb_c_port_roster=None,
    )
    inputs = replace(inputs, peer=extended)
    received: list[PeerCandidateInputs] = []
    original = design_lint_candidate_aggregation.peer_candidates

    def capture(
        observed: NetlistContract,
        peer: PeerCandidateInputs,
        *,
        reviewed_connector_references: tuple[str, ...] = (),
        spi_roster: SpiRosterContext | None = None,
        usb_data_path_map: UsbDataPathMap | None = None,
        usb_data_map_sha256: str | None = None,
    ) -> tuple[Candidate, ...]:
        received.append(peer)
        return original(
            observed,
            peer,
            reviewed_connector_references=reviewed_connector_references,
            spi_roster=spi_roster,
            usb_data_path_map=usb_data_path_map,
            usb_data_map_sha256=usb_data_map_sha256,
        )

    monkeypatch.setattr(design_lint_candidate_aggregation, "peer_candidates", capture)
    assert scan_candidates(inputs) == candidates(inputs.observed)
    assert received[0] is extended
    assert isinstance(received[0], ExtendedPeerInputs)
    assert received[0].extension_marker == "new peer evidence"


def test_scanner_passes_extended_mapped_input_to_its_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    @dataclass(frozen=True, slots=True)
    class ExtendedMappedInputs(MappedCandidateInputs):
        extension_marker: str = "new mapped evidence"

    inputs = _candidate_inputs(i2c_netlist(pullups=()))
    protection = ExternalProtectionCoverageReport()
    extended = ExtendedMappedInputs(
        external_protection=protection,
        crystal_network=None,
        regulator_feedback=None,
        rc_filter=None,
    )
    inputs = replace(inputs, mapped=extended)
    received: list[MappedCandidateInputs] = []
    original = design_lint_candidate_aggregation.mapped_coverage_candidates

    def capture(
        observed: NetlistContract,
        mapped: MappedCandidateInputs,
        *,
        usb_data_path_map: UsbDataPathMap | None = None,
        usb_data_map_sha256: str | None = None,
        power_path_map: PowerPathMap | None = None,
        power_sequence_map: PowerSequenceMap | None = None,
    ) -> tuple[Candidate, ...]:
        received.append(mapped)
        return original(
            observed,
            mapped,
            usb_data_path_map=usb_data_path_map,
            usb_data_map_sha256=usb_data_map_sha256,
            power_path_map=power_path_map,
            power_sequence_map=power_sequence_map,
        )

    monkeypatch.setattr(design_lint_candidate_aggregation, "mapped_coverage_candidates", capture)
    assert scan_candidates(inputs) == candidates(
        inputs.observed, external_protection_coverage=protection
    )
    assert received[0] is extended
    assert received[0].external_protection is protection
    assert isinstance(received[0], ExtendedMappedInputs)
    assert received[0].extension_marker == "new mapped evidence"


@pytest.mark.pcb_lint
@pytest.mark.parametrize("incomplete", [True, False], ids=["fault", "valid-control"])
def test_pcb_group_reaches_both_owners_and_preserves_legacy_findings(
    monkeypatch: pytest.MonkeyPatch, incomplete: bool
) -> None:
    inputs = _candidate_inputs(i2c_netlist(pullups=()))
    coverage = incomplete_report()
    if not incomplete:
        coverage = type(coverage).model_validate_json(
            coverage.model_copy(
                update={
                    "status": "COMPLETE",
                    "entries": compare_native_rules(pair_map(), rules_text(), frozenset()),
                }
            ).model_dump_json()
        )
    inputs = replace(inputs, pcb=replace(inputs.pcb, differential_pair=coverage))
    measurement = design_lint_candidate_aggregation.scan_pcb_measurement_candidates
    requirements = design_lint_candidate_aggregation.scan_pcb_requirement_candidates
    received: list[PcbCandidateInputs] = []

    def capture_measurements(pcb: PcbCandidateInputs) -> tuple[Candidate, ...]:
        received.append(pcb)
        return measurement(pcb)

    def capture_requirements(pcb: PcbCandidateInputs) -> tuple[Candidate, ...]:
        received.append(pcb)
        return requirements(pcb)

    monkeypatch.setattr(
        design_lint_candidate_aggregation, "scan_pcb_measurement_candidates", capture_measurements
    )
    monkeypatch.setattr(
        design_lint_candidate_aggregation, "scan_pcb_requirement_candidates", capture_requirements
    )
    typed = scan_candidates(inputs)
    legacy = _legacy_scan(inputs)
    assert received[:2] == [inputs.pcb, inputs.pcb]
    assert all(item is inputs.pcb for item in received[:2])
    assert typed == legacy
    assert tuple(map(fingerprint, typed)) == tuple(map(fingerprint, legacy))
    assert (
        any(item.rule_id == "pcb.differential_pair_rule_coverage" for item in typed) is incomplete
    )


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
    monkeypatch.setattr(
        design_lint_evaluation_candidates, "scan_candidate_result", _legacy_scan_result
    )
    legacy_report = evaluate("synthetic-scanner-parity", coach(observed), DesignLintPolicy())

    assert legacy_report.model_dump_json() == typed_report.model_dump_json()


@pytest.mark.parametrize(
    ("connected", "visible_bias"),
    ((False, False), (True, False), (True, True)),
    ids=("unconnected", "missing-bias", "valid-bias"),
)
def test_control_route_preserves_candidates_fingerprints_and_report(
    monkeypatch: pytest.MonkeyPatch, connected: bool, visible_bias: bool
) -> None:
    observed = control_input_pins(connected=connected, visible_bias=visible_bias)
    inputs = _candidate_inputs(observed)
    legacy_items = candidates(observed)
    typed_items = scan_candidates(inputs)
    assert typed_items == legacy_items
    assert tuple(map(fingerprint, typed_items)) == tuple(map(fingerprint, legacy_items))

    typed_report = evaluate("control-route-parity", coach(observed), DesignLintPolicy())
    monkeypatch.setattr(
        design_lint_evaluation_candidates, "scan_candidate_result", _legacy_scan_result
    )
    legacy_report = evaluate("control-route-parity", coach(observed), DesignLintPolicy())
    assert typed_report.model_dump_json() == legacy_report.model_dump_json()
