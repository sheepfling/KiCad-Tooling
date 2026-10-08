"""Recheck retained electrical evidence without executing a simulator or project code."""

from __future__ import annotations

from pathlib import Path

from .bus_heuristics import can_termination_checks, i2c_pullup_checks, spi_checks, usb_c_checks
from .component_power_ratings import component_power_rating_checks
from .component_voltage_ratings import component_voltage_rating_checks
from .connector_contact_ratings import connector_contact_rating_checks
from .contracts import read_model, repo_path
from .control_inputs import control_input_checks
from .digital_peer_voltages import digital_peer_voltage_checks
from .electrical import (
    bound_inputs,
    grounding_checks,
    load_analysis,
    pin_relationship_checks,
    policy_issues,
    power_budget_checks,
    selected_config,
    simulation_cases,
)
from .evidence import digest, evidence_path, verify_source
from .models import (
    AnalysisNotApplicable,
    CanTerminationAnalysis,
    CommandEvidence,
    ComponentPowerRatingAnalysis,
    ComponentVoltageRatingAnalysis,
    ConnectorContactRatingAnalysis,
    ControlInputsAnalysis,
    DigitalPeerVoltageAnalysis,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    ElectricalCheck,
    EvidenceFile,
    GroundingAnalysis,
    I2cPullupAnalysis,
    MosfetStressAnalysis,
    PcbAccessAnalysis,
    PcbAccessProbeRequestSet,
    PcbConnectivitySnapshot,
    PcbReturnPathsAnalysis,
    PinConnectivityAnalysis,
    PowerConnectivityAnalysis,
    ProjectKind,
    ProjectRecord,
    ReleaseClass,
    Rs485Analysis,
    SerialPeerAnalysis,
    SourceState,
    SpiAnalysis,
    TestAccessAnalysis,
    UsbCAnalysis,
)
from .mosfet_stress import mosfet_stress_checks
from .pcb_return_paths import (
    expected_probe_sha256,
    native_pcb_command_matches,
    pcb_return_path_checks,
)
from .power_connectivity import power_connectivity_checks
from .rs485_heuristics import rs485_checks
from .serial_heuristics import serial_peer_checks
from .spice import measured_checks, observed_versions, simulation_deck, waveform_checks
from .test_access import (
    evaluate_test_access_checks,
    pcb_access_probe_request_set,
    pcb_accessibility_checks,
    pcb_probe_envelope_checks,
)


def required_projects(
    root: Path, projects: tuple[ProjectRecord, ...], release_class: ReleaseClass
) -> tuple[str, ...]:
    """Declared contracts always gate releases; buildable boards must declare one."""
    required: list[str] = []
    for project in projects:
        config = selected_config(root, project.id)
        if config.electrical is not None:
            required.append(project.id)
        elif release_class is not ReleaseClass.ENGINEERING_REVIEW and config.kind in {
            ProjectKind.PCB,
            ProjectKind.SCHEMATIC,
        }:
            raise ValueError(
                f"{project.id}: build releases require reviewed electrical requirements; "
                f"run kicad-team electrical --project {project.id} --init and review applicability"
            )
    return tuple(required)


def verify_electrical(
    root: Path, reference: EvidenceFile, source: SourceState, project_id: str, native: EvidenceFile
) -> ElectricalAnalysisReport:
    """Check source, exact cases, logs, decks and waveform coverage, including after restore."""
    from ..validate import read_netlist

    path = evidence_path(root, reference)
    report = read_model(path, ElectricalAnalysisReport)
    verify_source(report.source, source)
    if report.project_id != project_id or report.status != "PASS":
        raise ValueError("Electrical report identifies a different project or did not pass")
    config = selected_config(root, project_id)
    contract = load_analysis(root, config)
    if contract is None:
        raise ValueError("Electrical requirements are missing")
    issues = policy_issues(root, config)
    if issues:
        raise ValueError("Electrical requirements are invalid: " + "; ".join(issues))
    if dict(report.input_sha256) != bound_inputs(root, config, contract):
        raise ValueError("Electrical evidence inputs differ from reviewed source/model bindings")
    for name, expected in report.artifacts_sha256.items():
        if digest(repo_path(path.parent, name)) != expected:
            raise ValueError(f"Missing or changed electrical artifact: {name}")

    def artifact(name: str) -> Path:
        if name not in report.artifacts_sha256:
            raise ValueError(f"Electrical evidence omits required artifact: {name}")
        return repo_path(path.parent, name)

    if read_model(artifact("requirements.json"), ElectricalAnalysisContract) != contract:
        raise ValueError("Retained electrical requirements differ from committed requirements")
    checks: list[ElectricalCheck] = []
    netlist = (
        read_netlist(evidence_path(root, native).parent / "netlist.xml")
        if isinstance(contract.grounding, GroundingAnalysis)
        or isinstance(contract.pin_connectivity, PinConnectivityAnalysis)
        or isinstance(contract.i2c_pullups, I2cPullupAnalysis)
        or isinstance(contract.can_termination, CanTerminationAnalysis)
        or isinstance(contract.usb_c, UsbCAnalysis)
        or isinstance(contract.spi, SpiAnalysis)
        or isinstance(contract.serial_peers, SerialPeerAnalysis)
        or isinstance(contract.digital_peer_voltages, DigitalPeerVoltageAnalysis)
        or isinstance(contract.component_voltage_ratings, ComponentVoltageRatingAnalysis)
        or isinstance(contract.component_power_ratings, ComponentPowerRatingAnalysis)
        or isinstance(contract.connector_contact_ratings, ConnectorContactRatingAnalysis)
        or isinstance(contract.mosfet_stress, MosfetStressAnalysis)
        or isinstance(contract.rs485, Rs485Analysis)
        or isinstance(contract.control_inputs, ControlInputsAnalysis)
        or isinstance(contract.power_connectivity, PowerConnectivityAnalysis)
        or isinstance(contract.test_access, TestAccessAnalysis)
        else None
    )
    if isinstance(contract.grounding, GroundingAnalysis):
        assert netlist is not None
        checks.extend(grounding_checks(contract.grounding, netlist))
    else:
        if not isinstance(contract.grounding, AnalysisNotApplicable):
            raise ValueError("Grounding requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="grounding", status="NOT_APPLICABLE", detail=contract.grounding.reason
            )
        )
    if isinstance(contract.pcb_return_paths, PcbReturnPathsAnalysis):
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
                    isinstance(contract.test_access, TestAccessAnalysis)
                    and pcb_access_probe_request_set(contract.test_access) is not None
                ),
            )
            or digest(probe_path) != expected_probe_sha256()
            or digest(probe_path) != snapshot.probe_sha256
        ):
            raise ValueError("PCB connectivity command or probe source evidence differs")
        checks.extend(
            pcb_return_path_checks(
                contract.pcb_return_paths,
                snapshot,
                board_sha256=digest(board_path),
                kicad_version=config.kicad_version,
                image=config.image,
                probe_sha256=expected_probe_sha256(),
            )
        )
    elif isinstance(contract.pcb_return_paths, AnalysisNotApplicable):
        checks.append(
            ElectricalCheck(
                id="pcb-return-paths",
                status="NOT_APPLICABLE",
                detail=contract.pcb_return_paths.reason,
            )
        )
    else:
        raise ValueError("PCB return-path requirements remain pending")  # noqa: TRY004
    access_probe_requests = (
        pcb_access_probe_request_set(contract.test_access)
        if isinstance(contract.test_access, TestAccessAnalysis)
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
    if isinstance(contract.pin_connectivity, PinConnectivityAnalysis):
        assert netlist is not None
        checks.extend(pin_relationship_checks(contract.pin_connectivity, netlist))
    elif contract.pin_connectivity is not None:
        if not isinstance(contract.pin_connectivity, AnalysisNotApplicable):
            raise ValueError("Pin connectivity requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="pin-connectivity",
                status="NOT_APPLICABLE",
                detail=contract.pin_connectivity.reason,
            )
        )
    if isinstance(contract.i2c_pullups, I2cPullupAnalysis):
        assert netlist is not None
        checks.extend(i2c_pullup_checks(contract.i2c_pullups, netlist))
    elif contract.i2c_pullups is not None:
        if not isinstance(contract.i2c_pullups, AnalysisNotApplicable):
            raise ValueError("I2C pull-up requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="i2c-pullups",
                status="NOT_APPLICABLE",
                detail=contract.i2c_pullups.reason,
            )
        )
    if isinstance(contract.can_termination, CanTerminationAnalysis):
        assert netlist is not None
        checks.extend(can_termination_checks(contract.can_termination, netlist))
    elif contract.can_termination is not None:
        if not isinstance(contract.can_termination, AnalysisNotApplicable):
            raise ValueError("CAN termination requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="can-termination",
                status="NOT_APPLICABLE",
                detail=contract.can_termination.reason,
            )
        )
    if isinstance(contract.usb_c, UsbCAnalysis):
        assert netlist is not None
        checks.extend(usb_c_checks(contract.usb_c, netlist))
    elif contract.usb_c is not None:
        if not isinstance(contract.usb_c, AnalysisNotApplicable):
            raise ValueError("USB-C requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(id="usb-c", status="NOT_APPLICABLE", detail=contract.usb_c.reason)
        )
    if isinstance(contract.spi, SpiAnalysis):
        assert netlist is not None
        checks.extend(spi_checks(contract.spi, netlist))
    elif contract.spi is not None:
        if not isinstance(contract.spi, AnalysisNotApplicable):
            raise ValueError("SPI requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(id="spi", status="NOT_APPLICABLE", detail=contract.spi.reason)
        )
    if isinstance(contract.serial_peers, SerialPeerAnalysis):
        assert netlist is not None
        checks.extend(serial_peer_checks(contract.serial_peers, netlist))
    elif contract.serial_peers is not None:
        if not isinstance(contract.serial_peers, AnalysisNotApplicable):
            raise ValueError("Serial peer requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="serial-peers",
                status="NOT_APPLICABLE",
                detail=contract.serial_peers.reason,
            )
        )
    if isinstance(contract.digital_peer_voltages, DigitalPeerVoltageAnalysis):
        assert netlist is not None
        checks.extend(digital_peer_voltage_checks(contract.digital_peer_voltages, netlist))
    elif contract.digital_peer_voltages is not None:
        if not isinstance(contract.digital_peer_voltages, AnalysisNotApplicable):
            raise ValueError("Digital peer voltage requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="digital-peer-voltages",
                status="NOT_APPLICABLE",
                detail=contract.digital_peer_voltages.reason,
            )
        )
    if isinstance(contract.component_voltage_ratings, ComponentVoltageRatingAnalysis):
        assert netlist is not None
        checks.extend(component_voltage_rating_checks(contract.component_voltage_ratings, netlist))
    elif contract.component_voltage_ratings is not None:
        if not isinstance(contract.component_voltage_ratings, AnalysisNotApplicable):
            raise ValueError("Component voltage-rating requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="component-voltage-ratings",
                status="NOT_APPLICABLE",
                detail=contract.component_voltage_ratings.reason,
            )
        )
    if isinstance(contract.component_power_ratings, ComponentPowerRatingAnalysis):
        assert netlist is not None
        checks.extend(component_power_rating_checks(contract.component_power_ratings, netlist))
    elif contract.component_power_ratings is not None:
        if not isinstance(contract.component_power_ratings, AnalysisNotApplicable):
            raise ValueError("Component power-rating requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="component-power-ratings",
                status="NOT_APPLICABLE",
                detail=contract.component_power_ratings.reason,
            )
        )
    if isinstance(contract.connector_contact_ratings, ConnectorContactRatingAnalysis):
        assert netlist is not None
        checks.extend(connector_contact_rating_checks(contract.connector_contact_ratings, netlist))
    elif contract.connector_contact_ratings is not None:
        if not isinstance(contract.connector_contact_ratings, AnalysisNotApplicable):
            raise ValueError("Connector contact rating requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="connector-contact-ratings",
                status="NOT_APPLICABLE",
                detail=contract.connector_contact_ratings.reason,
            )
        )
    if isinstance(contract.mosfet_stress, MosfetStressAnalysis):
        assert netlist is not None
        checks.extend(mosfet_stress_checks(contract.mosfet_stress, netlist))
    elif contract.mosfet_stress is not None:
        if not isinstance(contract.mosfet_stress, AnalysisNotApplicable):
            raise ValueError("MOSFET stress requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="mosfet-stress",
                status="NOT_APPLICABLE",
                detail=contract.mosfet_stress.reason,
            )
        )
    if isinstance(contract.rs485, Rs485Analysis):
        assert netlist is not None
        checks.extend(rs485_checks(contract.rs485, netlist))
    elif contract.rs485 is not None:
        if not isinstance(contract.rs485, AnalysisNotApplicable):
            raise ValueError("RS-485 requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(id="rs485", status="NOT_APPLICABLE", detail=contract.rs485.reason)
        )
    if isinstance(contract.control_inputs, ControlInputsAnalysis):
        assert netlist is not None
        checks.extend(control_input_checks(contract.control_inputs, netlist))
    elif contract.control_inputs is not None:
        if not isinstance(contract.control_inputs, AnalysisNotApplicable):
            raise ValueError("Control-input requirements remain pending")  # noqa: TRY004
        checks.append(
            ElectricalCheck(
                id="control-inputs",
                status="NOT_APPLICABLE",
                detail=contract.control_inputs.reason,
            )
        )
    if isinstance(contract.power_connectivity, PowerConnectivityAnalysis):
        assert netlist is not None
        checks.extend(power_connectivity_checks(contract.power_connectivity, netlist))
    elif contract.power_connectivity is not None:
        if not isinstance(contract.power_connectivity, AnalysisNotApplicable):
            raise ValueError("Power connectivity requirements remain pending")  # noqa: TRY004 - incomplete policy
        checks.append(
            ElectricalCheck(
                id="power-connectivity",
                status="NOT_APPLICABLE",
                detail=contract.power_connectivity.reason,
            )
        )
    if isinstance(contract.test_access, TestAccessAnalysis):
        assert netlist is not None
        checks.extend(evaluate_test_access_checks(contract.test_access, netlist))
        if isinstance(contract.test_access.pcb_accessibility, PcbAccessAnalysis):
            if config.kind is not ProjectKind.PCB:
                raise ValueError("PCB access requirements need an authoritative PCB project")
            board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
            checks.extend(
                pcb_accessibility_checks(
                    contract.test_access,
                    contract.test_access.pcb_accessibility,
                    board_path,
                )
            )
        elif isinstance(contract.test_access.pcb_accessibility, AnalysisNotApplicable):
            checks.append(
                ElectricalCheck(
                    id="test-access/pcb-accessibility",
                    status="NOT_APPLICABLE",
                    detail=contract.test_access.pcb_accessibility.reason,
                )
            )
        else:
            raise ValueError("PCB test-access requirements remain pending")  # noqa: TRY004
        if access_probe_requests is not None:
            if access_probe_snapshot is None:
                raise ValueError("Retained PCB probe-envelope observations are missing")
            checks.extend(pcb_probe_envelope_checks(contract.test_access, access_probe_snapshot))
    elif isinstance(contract.test_access, AnalysisNotApplicable):
        checks.append(
            ElectricalCheck(
                id="test-access/schematic",
                status="NOT_APPLICABLE",
                detail=contract.test_access.reason,
            )
        )
        checks.append(
            ElectricalCheck(
                id="test-access/pcb-accessibility",
                status="NOT_APPLICABLE",
                detail=contract.test_access.reason,
            )
        )
    else:
        raise ValueError("Test-access requirements remain pending")  # noqa: TRY004
    if isinstance(contract.high_frequency, AnalysisNotApplicable):
        checks.append(
            ElectricalCheck(
                id="high-frequency", status="NOT_APPLICABLE", detail=contract.high_frequency.reason
            )
        )
    checks.extend(power_budget_checks(contract.power))
    cases = simulation_cases(contract)
    expected_commands: set[str] = {case.id for case in cases}
    if cases:
        expected_commands.add("version")
    if (
        isinstance(contract.pcb_return_paths, PcbReturnPathsAnalysis)
        or access_probe_requests is not None
    ):
        expected_commands.add("pcb-connectivity")
    if set(report.commands) != expected_commands:
        raise ValueError("Electrical evidence command inventory differs from required cases")
    if cases:
        version = read_model(artifact("ngspice-version.command.json"), CommandEvidence)
        if (
            version != report.commands["version"]
            or version.returncode != 0
            or version.error
            or contract.ngspice_version not in observed_versions(version)
        ):
            raise ValueError("Electrical evidence has no successful exact simulator version probe")
    for case in cases:
        command = read_model(artifact(f"{case.id}/ngspice.command.json"), CommandEvidence)
        if command != report.commands[case.id]:
            raise ValueError(f"{case.id}: electrical command evidence differs")
        if artifact(f"{case.id}/simulation.cir").read_text() != simulation_deck(root, case):
            raise ValueError(f"{case.id}: retained simulation deck differs from reviewed inputs")
        checks.extend(measured_checks(case, command))
        checks.extend(waveform_checks(artifact(f"{case.id}/waveforms.raw"), case))
    if (
        tuple(checks) != report.checks
        or not checks
        or any(row.status not in {"PASS", "NOT_APPLICABLE"} for row in checks)
    ):
        raise ValueError("Retained electrical checks fail or omit reviewed requirements")
    return report
