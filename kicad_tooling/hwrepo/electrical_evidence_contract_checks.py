"""Re-evaluate retained typed electrical requirements against source evidence."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeAlias

import kicad_tooling.hwrepo.electrical_analysis_contract_models as electrical_contracts
from kicad_tooling.hwrepo import pcb_test_access_models

from ..validate import read_netlist
from .can_termination_contract import can_termination_checks
from .component_power_ratings import component_power_rating_checks
from .component_voltage_ratings import component_voltage_rating_checks
from .connector_contact_ratings import connector_contact_rating_checks
from .contracts import read_model, repo_path
from .control_input_checks import control_input_checks
from .digital_peer_voltages import digital_peer_voltage_checks
from .electrical import grounding_checks, pin_relationship_checks, power_budget_checks
from .electrical_analysis_contract_models import ElectricalAnalysisContract
from .evidence import digest, evidence_path
from .i2c_pullup_contract import i2c_pullup_checks
from .models import (
    CommandEvidence,
    ElectricalAnalysisReport,
    ElectricalCheck,
    EvidenceFile,
    ProjectConfig,
    ProjectKind,
)
from .mosfet_stress import mosfet_stress_checks
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_return_path_capture import expected_probe_sha256, native_pcb_command_matches
from .pcb_return_path_checks import pcb_return_path_checks
from .pcb_test_access_models import PcbAccessProbeRequestSet
from .power_connectivity import power_connectivity_checks
from .rs485_heuristics import rs485_checks
from .serial_heuristics import serial_peer_checks
from .spi_contract import spi_checks
from .test_access import (
    evaluate_test_access_checks,
    pcb_access_probe_request_set,
    pcb_accessibility_checks,
    pcb_probe_envelope_checks,
)
from .usb_c_contract import usb_c_checks

ElectricalAnalysisState: TypeAlias = (
    electrical_contracts.AnalysisNotApplicable | electrical_contracts.AnalysisPending
)


def retained_electrical_contract_checks(
    root: Path,
    config: ProjectConfig,
    contract: ElectricalAnalysisContract,
    report: ElectricalAnalysisReport,
    native: EvidenceFile,
    artifact: Callable[[str], Path],
) -> tuple[tuple[ElectricalCheck, ...], bool]:
    """Compare retained contract dispositions and artifacts with native evidence."""
    grounding: (
        electrical_contracts.GroundingAnalysis
        | electrical_contracts.AnalysisNotApplicable
        | electrical_contracts.AnalysisPending
    ) = contract.grounding
    pcb_return_paths: (
        electrical_contracts.PcbReturnPathsAnalysis
        | electrical_contracts.AnalysisNotApplicable
        | electrical_contracts.AnalysisPending
    ) = contract.pcb_return_paths
    pin_connectivity: (
        electrical_contracts.PinConnectivityAnalysis | ElectricalAnalysisState | None
    ) = contract.pin_connectivity
    i2c_pullups: electrical_contracts.I2cPullupAnalysis | ElectricalAnalysisState | None = (
        contract.i2c_pullups
    )
    can_termination: (
        electrical_contracts.CanTerminationAnalysis | ElectricalAnalysisState | None
    ) = contract.can_termination
    usb_c: electrical_contracts.UsbCAnalysis | ElectricalAnalysisState | None = contract.usb_c
    spi: electrical_contracts.SpiAnalysis | ElectricalAnalysisState | None = contract.spi
    serial_peers: electrical_contracts.SerialPeerAnalysis | ElectricalAnalysisState | None = (
        contract.serial_peers
    )
    digital_peer_voltages: (
        electrical_contracts.DigitalPeerVoltageAnalysis | ElectricalAnalysisState | None
    ) = contract.digital_peer_voltages
    component_voltage_ratings: (
        electrical_contracts.ComponentVoltageRatingAnalysis | ElectricalAnalysisState | None
    ) = contract.component_voltage_ratings
    component_power_ratings: (
        electrical_contracts.ComponentPowerRatingAnalysis | ElectricalAnalysisState | None
    ) = contract.component_power_ratings
    connector_contact_ratings: (
        electrical_contracts.ConnectorContactRatingAnalysis | ElectricalAnalysisState | None
    ) = contract.connector_contact_ratings
    mosfet_stress: electrical_contracts.MosfetStressAnalysis | ElectricalAnalysisState | None = (
        contract.mosfet_stress
    )
    rs485: electrical_contracts.Rs485Analysis | ElectricalAnalysisState | None = contract.rs485
    control_inputs: electrical_contracts.ControlInputsAnalysis | ElectricalAnalysisState | None = (
        contract.control_inputs
    )
    power_connectivity: (
        electrical_contracts.PowerConnectivityAnalysis | ElectricalAnalysisState | None
    ) = contract.power_connectivity
    test_access: electrical_contracts.TestAccessAnalysis | ElectricalAnalysisState | None = (
        contract.test_access
    )
    high_frequency: electrical_contracts.HighFrequencyAnalysis | ElectricalAnalysisState = (
        contract.high_frequency
    )
    checks: list[ElectricalCheck] = []
    netlist = (
        read_netlist(evidence_path(root, native).parent / "netlist.xml")
        if isinstance(grounding, electrical_contracts.GroundingAnalysis)
        or isinstance(pin_connectivity, electrical_contracts.PinConnectivityAnalysis)
        or isinstance(i2c_pullups, electrical_contracts.I2cPullupAnalysis)
        or isinstance(can_termination, electrical_contracts.CanTerminationAnalysis)
        or isinstance(usb_c, electrical_contracts.UsbCAnalysis)
        or isinstance(spi, electrical_contracts.SpiAnalysis)
        or isinstance(serial_peers, electrical_contracts.SerialPeerAnalysis)
        or isinstance(digital_peer_voltages, electrical_contracts.DigitalPeerVoltageAnalysis)
        or isinstance(
            component_voltage_ratings, electrical_contracts.ComponentVoltageRatingAnalysis
        )
        or isinstance(component_power_ratings, electrical_contracts.ComponentPowerRatingAnalysis)
        or isinstance(
            connector_contact_ratings, electrical_contracts.ConnectorContactRatingAnalysis
        )
        or isinstance(mosfet_stress, electrical_contracts.MosfetStressAnalysis)
        or isinstance(rs485, electrical_contracts.Rs485Analysis)
        or isinstance(control_inputs, electrical_contracts.ControlInputsAnalysis)
        or isinstance(power_connectivity, electrical_contracts.PowerConnectivityAnalysis)
        or isinstance(test_access, electrical_contracts.TestAccessAnalysis)
        else None
    )
    if isinstance(grounding, electrical_contracts.GroundingAnalysis):
        assert netlist is not None
        checks.extend(grounding_checks(grounding, netlist))
    else:
        if not isinstance(grounding, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("Grounding requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(id="grounding", status="NOT_APPLICABLE", detail=grounding.reason)
        )
    if isinstance(pcb_return_paths, electrical_contracts.PcbReturnPathsAnalysis):
        if config.kind is not ProjectKind.PCB:
            raise ValueError("PCB return-path requirements need an authoritative PCB project")
        board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
        probe_path = artifact("pcb-connectivity/native_pcb_probe.py")
        snapshot = read_model(artifact("pcb-connectivity/snapshot.json"), PcbConnectivitySnapshot)
        command = read_model(artifact("pcb-connectivity/native.command.json"), CommandEvidence)
        if (
            report.commands.get("pcb-connectivity") != command
            or not native_pcb_command_matches(
                command,
                config,
                access_probes=(
                    isinstance(test_access, electrical_contracts.TestAccessAnalysis)
                    and pcb_access_probe_request_set(test_access) is not None
                ),
            )
            or digest(probe_path) != expected_probe_sha256()
            or digest(probe_path) != snapshot.probe_sha256
        ):
            raise ValueError("PCB connectivity command or probe source evidence differs")
        checks.extend(
            pcb_return_path_checks(
                pcb_return_paths,
                snapshot,
                board_sha256=digest(board_path),
                kicad_version=config.kicad_version,
                image=config.image,
                probe_sha256=expected_probe_sha256(),
            )
        )
    elif isinstance(pcb_return_paths, electrical_contracts.AnalysisNotApplicable):
        checks.append(
            ElectricalCheck(
                id="pcb-return-paths",
                status="NOT_APPLICABLE",
                detail=pcb_return_paths.reason,
            )
        )
    else:
        raise ValueError("PCB return-path requirements remain pending")  # noqa: TRY004
    access_probe_requests = (
        pcb_access_probe_request_set(test_access)
        if isinstance(test_access, electrical_contracts.TestAccessAnalysis)
        else None
    )
    access_probe_snapshot: PcbConnectivitySnapshot | None = None
    if access_probe_requests is not None:
        if config.kind is not ProjectKind.PCB:
            raise ValueError("PCB probe-envelope requirements need an authoritative PCB project")
        request_path = artifact("pcb-connectivity/access-probe-requests.json")
        if read_model(request_path, PcbAccessProbeRequestSet) != access_probe_requests:
            raise ValueError("Retained native PCB probe requests differ from current requirements")
        board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
        probe_path = artifact("pcb-connectivity/native_pcb_probe.py")
        snapshot = read_model(artifact("pcb-connectivity/snapshot.json"), PcbConnectivitySnapshot)
        command = read_model(artifact("pcb-connectivity/native.command.json"), CommandEvidence)
        if (
            report.commands.get("pcb-connectivity") != command
            or not native_pcb_command_matches(command, config, access_probes=True)
            or digest(probe_path) != expected_probe_sha256()
            or digest(probe_path) != snapshot.probe_sha256
            or snapshot.board_sha256 != digest(board_path)
            or snapshot.kicad_version != config.kicad_version
            or snapshot.image != config.image
            or not snapshot.zones_refilled
            or snapshot.access_probe_requests_sha256 != digest(request_path)
        ):
            raise ValueError(
                "PCB probe-envelope evidence differs from its board, request, or native toolchain"
            )
        access_probe_snapshot = snapshot
    if isinstance(pin_connectivity, electrical_contracts.PinConnectivityAnalysis):
        assert netlist is not None
        checks.extend(pin_relationship_checks(pin_connectivity, netlist))
    elif pin_connectivity is not None:
        if not isinstance(pin_connectivity, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("Pin connectivity requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="pin-connectivity",
                status="NOT_APPLICABLE",
                detail=pin_connectivity.reason,
            )
        )
    if isinstance(i2c_pullups, electrical_contracts.I2cPullupAnalysis):
        assert netlist is not None
        checks.extend(i2c_pullup_checks(i2c_pullups, netlist))
    elif i2c_pullups is not None:
        if not isinstance(i2c_pullups, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("I2C pull-up requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="i2c-pullups",
                status="NOT_APPLICABLE",
                detail=i2c_pullups.reason,
            )
        )
    if isinstance(can_termination, electrical_contracts.CanTerminationAnalysis):
        assert netlist is not None
        checks.extend(can_termination_checks(can_termination, netlist))
    elif can_termination is not None:
        if not isinstance(can_termination, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("CAN termination requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="can-termination",
                status="NOT_APPLICABLE",
                detail=can_termination.reason,
            )
        )
    if isinstance(usb_c, electrical_contracts.UsbCAnalysis):
        assert netlist is not None
        checks.extend(usb_c_checks(usb_c, netlist))
    elif usb_c is not None:
        if not isinstance(usb_c, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("USB-C requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(ElectricalCheck(id="usb-c", status="NOT_APPLICABLE", detail=usb_c.reason))
    if isinstance(spi, electrical_contracts.SpiAnalysis):
        assert netlist is not None
        checks.extend(spi_checks(spi, netlist))
    elif spi is not None:
        if not isinstance(spi, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("SPI requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(ElectricalCheck(id="spi", status="NOT_APPLICABLE", detail=spi.reason))
    if isinstance(serial_peers, electrical_contracts.SerialPeerAnalysis):
        assert netlist is not None
        checks.extend(serial_peer_checks(serial_peers, netlist))
    elif serial_peers is not None:
        if not isinstance(serial_peers, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("Serial peer requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="serial-peers",
                status="NOT_APPLICABLE",
                detail=serial_peers.reason,
            )
        )
    if isinstance(digital_peer_voltages, electrical_contracts.DigitalPeerVoltageAnalysis):
        assert netlist is not None
        checks.extend(digital_peer_voltage_checks(digital_peer_voltages, netlist))
    elif digital_peer_voltages is not None:
        if not isinstance(digital_peer_voltages, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("Digital peer voltage requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="digital-peer-voltages",
                status="NOT_APPLICABLE",
                detail=digital_peer_voltages.reason,
            )
        )
    if isinstance(component_voltage_ratings, electrical_contracts.ComponentVoltageRatingAnalysis):
        assert netlist is not None
        checks.extend(component_voltage_rating_checks(component_voltage_ratings, netlist))
    elif component_voltage_ratings is not None:
        if not isinstance(component_voltage_ratings, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("Component voltage-rating requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="component-voltage-ratings",
                status="NOT_APPLICABLE",
                detail=component_voltage_ratings.reason,
            )
        )
    if isinstance(component_power_ratings, electrical_contracts.ComponentPowerRatingAnalysis):
        assert netlist is not None
        checks.extend(component_power_rating_checks(component_power_ratings, netlist))
    elif component_power_ratings is not None:
        if not isinstance(component_power_ratings, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("Component power-rating requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="component-power-ratings",
                status="NOT_APPLICABLE",
                detail=component_power_ratings.reason,
            )
        )
    if isinstance(connector_contact_ratings, electrical_contracts.ConnectorContactRatingAnalysis):
        assert netlist is not None
        checks.extend(connector_contact_rating_checks(connector_contact_ratings, netlist))
    elif connector_contact_ratings is not None:
        if not isinstance(connector_contact_ratings, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("Connector contact rating requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="connector-contact-ratings",
                status="NOT_APPLICABLE",
                detail=connector_contact_ratings.reason,
            )
        )
    if isinstance(mosfet_stress, electrical_contracts.MosfetStressAnalysis):
        assert netlist is not None
        checks.extend(mosfet_stress_checks(mosfet_stress, netlist))
    elif mosfet_stress is not None:
        if not isinstance(mosfet_stress, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("MOSFET stress requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="mosfet-stress",
                status="NOT_APPLICABLE",
                detail=mosfet_stress.reason,
            )
        )
    if isinstance(rs485, electrical_contracts.Rs485Analysis):
        assert netlist is not None
        checks.extend(rs485_checks(rs485, netlist))
    elif rs485 is not None:
        if not isinstance(rs485, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("RS-485 requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(ElectricalCheck(id="rs485", status="NOT_APPLICABLE", detail=rs485.reason))
    if isinstance(control_inputs, electrical_contracts.ControlInputsAnalysis):
        assert netlist is not None
        checks.extend(control_input_checks(control_inputs, netlist))
    elif control_inputs is not None:
        if not isinstance(control_inputs, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("Control-input requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="control-inputs",
                status="NOT_APPLICABLE",
                detail=control_inputs.reason,
            )
        )
    if isinstance(power_connectivity, electrical_contracts.PowerConnectivityAnalysis):
        assert netlist is not None
        checks.extend(power_connectivity_checks(power_connectivity, netlist))
    elif power_connectivity is not None:
        if not isinstance(power_connectivity, electrical_contracts.AnalysisNotApplicable):
            raise ValueError("Power connectivity requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="power-connectivity",
                status="NOT_APPLICABLE",
                detail=power_connectivity.reason,
            )
        )
    if isinstance(test_access, electrical_contracts.TestAccessAnalysis):
        assert netlist is not None
        pcb_accessibility: pcb_test_access_models.PcbAccessAnalysis | ElectricalAnalysisState = (
            test_access.pcb_accessibility
        )
        checks.extend(evaluate_test_access_checks(test_access, netlist))
        if isinstance(pcb_accessibility, pcb_test_access_models.PcbAccessAnalysis):
            if config.kind is not ProjectKind.PCB:
                raise ValueError("PCB access requirements need an authoritative PCB project")
            board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
            checks.extend(
                pcb_accessibility_checks(
                    test_access,
                    pcb_accessibility,
                    board_path,
                )
            )
        elif isinstance(pcb_accessibility, electrical_contracts.AnalysisNotApplicable):
            checks.append(
                ElectricalCheck(
                    id="test-access/pcb-accessibility",
                    status="NOT_APPLICABLE",
                    detail=pcb_accessibility.reason,
                )
            )
        else:
            raise ValueError("PCB test-access requirements remain pending")  # noqa: TRY004
        if access_probe_requests is not None:
            if access_probe_snapshot is None:
                raise ValueError("Retained PCB probe-envelope observations are missing")
            checks.extend(pcb_probe_envelope_checks(test_access, access_probe_snapshot))
    elif isinstance(test_access, electrical_contracts.AnalysisNotApplicable):
        checks.append(
            ElectricalCheck(
                id="test-access/schematic",
                status="NOT_APPLICABLE",
                detail=test_access.reason,
            )
        )
        checks.append(
            ElectricalCheck(
                id="test-access/pcb-accessibility",
                status="NOT_APPLICABLE",
                detail=test_access.reason,
            )
        )
    else:
        raise ValueError("Test-access requirements remain pending")  # noqa: TRY004
    if isinstance(high_frequency, electrical_contracts.AnalysisNotApplicable):
        checks.append(
            ElectricalCheck(
                id="high-frequency", status="NOT_APPLICABLE", detail=high_frequency.reason
            )
        )
    checks.extend(power_budget_checks(contract.power))

    requires_pcb_connectivity = (
        isinstance(pcb_return_paths, electrical_contracts.PcbReturnPathsAnalysis)
        or access_probe_requests is not None
    )
    return tuple(checks), requires_pcb_connectivity
