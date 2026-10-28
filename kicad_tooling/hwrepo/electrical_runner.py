"""Run all configured electrical checks into a fresh, source-bound receipt."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypeAlias
from uuid import uuid4

import kicad_tooling.hwrepo.electrical_analysis_contract_models as electrical_contracts
from kicad_tooling.hwrepo import pcb_test_access_models

from .can_termination_contract import can_termination_checks
from .component_power_ratings import component_power_rating_checks
from .component_voltage_ratings import component_voltage_rating_checks
from .connector_contact_ratings import connector_contact_rating_checks
from .contract_coach import (
    AutoNetlistRunner,
    NetlistRunner,
    capture,
    inspect_summary,
    receipt_directory,
)
from .contracts import repo_path, write_model
from .control_input_checks import control_input_checks
from .digital_peer_voltages import digital_peer_voltage_checks
from .electrical import (
    bound_inputs,
    grounding_checks,
    load_analysis,
    pin_relationship_checks,
    power_budget_checks,
    selected_config,
    simulation_cases,
)
from .evidence import digest, source_state
from .i2c_pullup_contract import i2c_pullup_checks
from .models import (
    CommandEvidence,
    ElectricalAnalysisReport,
    ElectricalCheck,
    ElectricalSuiteReport,
    ProjectKind,
)
from .mosfet_stress import mosfet_stress_checks
from .pcb_return_path_capture import capture_native_pcb_connectivity, expected_probe_sha256
from .pcb_return_path_checks import pcb_return_path_checks
from .power_connectivity import power_connectivity_checks
from .rs485_heuristics import rs485_checks
from .selection import ProjectSelector, resolve_project_ids
from .serial_heuristics import serial_peer_checks
from .spi_contract import spi_checks
from .spice import executable_path, run_case, simulator_version
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


def analyze(
    root: Path,
    project_id: str,
    output: Path | None = None,
    native_summary: Path | None = None,
    cli: str = "kicad-cli",
    ngspice: str = "ngspice",
    runner: NetlistRunner | None = None,
) -> ElectricalAnalysisReport:
    root = root.resolve()
    source = source_state(root)
    if native_summary is not None and not native_summary.is_absolute():
        native_summary = root / native_summary
    if output is None:
        output = Path("build/electrical") / f"{project_id}-{uuid4().hex[:12]}"
    output = receipt_directory(root, project_id, output)
    checks: list[ElectricalCheck] = []
    commands: dict[str, CommandEvidence] = {}
    inputs: dict[str, str] = {}
    status = "FAIL"
    try:
        config = selected_config(root, project_id)
        contract = load_analysis(root, config)
        if contract is None:
            status = "NOT_CONFIGURED"
            checks.append(
                ElectricalCheck(
                    id="configuration",
                    status="NOT_CONFIGURED",
                    detail=f"Run python -B -m kicad_tooling.electrical --project {project_id} --init, then review the starter.",
                )
            )
        else:
            grounding: electrical_contracts.GroundingAnalysis | ElectricalAnalysisState = (
                contract.grounding
            )
            pcb_return_paths: (
                electrical_contracts.PcbReturnPathsAnalysis | ElectricalAnalysisState
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
            usb_c: electrical_contracts.UsbCAnalysis | ElectricalAnalysisState | None = (
                contract.usb_c
            )
            spi: electrical_contracts.SpiAnalysis | ElectricalAnalysisState | None = contract.spi
            serial_peers: (
                electrical_contracts.SerialPeerAnalysis | ElectricalAnalysisState | None
            ) = contract.serial_peers
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
            mosfet_stress: (
                electrical_contracts.MosfetStressAnalysis | ElectricalAnalysisState | None
            ) = contract.mosfet_stress
            rs485: electrical_contracts.Rs485Analysis | ElectricalAnalysisState | None = (
                contract.rs485
            )
            control_inputs: (
                electrical_contracts.ControlInputsAnalysis | ElectricalAnalysisState | None
            ) = contract.control_inputs
            power_connectivity: (
                electrical_contracts.PowerConnectivityAnalysis | ElectricalAnalysisState | None
            ) = contract.power_connectivity
            test_access: (
                electrical_contracts.TestAccessAnalysis | ElectricalAnalysisState | None
            ) = contract.test_access
            high_frequency: electrical_contracts.HighFrequencyAnalysis | ElectricalAnalysisState = (
                contract.high_frequency
            )
            inputs = bound_inputs(root, config, contract)
            write_model(output / "requirements.json", contract)
            netlist = None
            needs_netlist = any(
                (
                    isinstance(grounding, electrical_contracts.GroundingAnalysis),
                    isinstance(pin_connectivity, electrical_contracts.PinConnectivityAnalysis),
                    isinstance(i2c_pullups, electrical_contracts.I2cPullupAnalysis),
                    isinstance(can_termination, electrical_contracts.CanTerminationAnalysis),
                    isinstance(usb_c, electrical_contracts.UsbCAnalysis),
                    isinstance(spi, electrical_contracts.SpiAnalysis),
                    isinstance(serial_peers, electrical_contracts.SerialPeerAnalysis),
                    isinstance(
                        digital_peer_voltages, electrical_contracts.DigitalPeerVoltageAnalysis
                    ),
                    isinstance(
                        component_voltage_ratings,
                        electrical_contracts.ComponentVoltageRatingAnalysis,
                    ),
                    isinstance(
                        component_power_ratings, electrical_contracts.ComponentPowerRatingAnalysis
                    ),
                    isinstance(
                        connector_contact_ratings,
                        electrical_contracts.ConnectorContactRatingAnalysis,
                    ),
                    isinstance(mosfet_stress, electrical_contracts.MosfetStressAnalysis),
                    isinstance(rs485, electrical_contracts.Rs485Analysis),
                    isinstance(control_inputs, electrical_contracts.ControlInputsAnalysis),
                    isinstance(power_connectivity, electrical_contracts.PowerConnectivityAnalysis),
                    isinstance(test_access, electrical_contracts.TestAccessAnalysis),
                )
            )
            if needs_netlist:
                if native_summary is None:
                    netlist_output = output / "netlist"
                    netlist_output.mkdir()
                    observed = capture(
                        root, project_id, netlist_output, runner or AutoNetlistRunner(cli)
                    )
                else:
                    observed = inspect_summary(root, project_id, native_summary)
                write_model(output / "netlist-evidence.json", observed)
                netlist = observed.observed
            if isinstance(grounding, electrical_contracts.GroundingAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="grounding",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(grounding_checks(grounding, netlist))
            else:
                checks.append(
                    ElectricalCheck(
                        id="grounding",
                        status="NOT_CONFIGURED"
                        if isinstance(grounding, electrical_contracts.AnalysisPending)
                        else "NOT_APPLICABLE",
                        detail=grounding.reason,
                    )
                )
            access_probe_requests = (
                pcb_access_probe_request_set(test_access)
                if isinstance(test_access, electrical_contracts.TestAccessAnalysis)
                else None
            )
            pcb_snapshot = None
            pcb_probe_error: str | None = None
            needs_pcb_probe = (
                isinstance(pcb_return_paths, electrical_contracts.PcbReturnPathsAnalysis)
                or access_probe_requests is not None
            )
            if needs_pcb_probe and config.kind is ProjectKind.PCB:
                try:
                    if access_probe_requests is None:
                        command, pcb_snapshot = capture_native_pcb_connectivity(
                            root, config, output / "pcb-connectivity"
                        )
                    else:
                        command, pcb_snapshot = capture_native_pcb_connectivity(
                            root,
                            config,
                            output / "pcb-connectivity",
                            access_probe_requests=access_probe_requests,
                        )
                    commands["pcb-connectivity"] = command
                    if pcb_snapshot is None:
                        pcb_probe_error = (
                            "KiCad native PCB probing did not produce evidence; inspect "
                            "pcb-connectivity/native.command.json."
                        )
                    else:
                        write_model(output / "pcb-connectivity/snapshot.json", pcb_snapshot)
                except (OSError, ValueError) as exc:
                    pcb_probe_error = str(exc)
            if isinstance(pcb_return_paths, electrical_contracts.PcbReturnPathsAnalysis):
                if config.kind is not ProjectKind.PCB:
                    checks.append(
                        ElectricalCheck(
                            id="pcb-return-paths/source",
                            status="FAIL",
                            detail="PCB return-path requirements need an authoritative PCB project.",
                        )
                    )
                else:
                    if pcb_snapshot is None:
                        checks.append(
                            ElectricalCheck(
                                id="pcb-return-paths/native-probe",
                                status="NOT_RUN",
                                detail=pcb_probe_error
                                or "KiCad native PCB probing did not produce evidence.",
                            )
                        )
                    else:
                        board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
                        checks.extend(
                            pcb_return_path_checks(
                                pcb_return_paths,
                                pcb_snapshot,
                                board_sha256=digest(board_path),
                                kicad_version=config.kicad_version,
                                image=config.image,
                                probe_sha256=expected_probe_sha256(),
                            )
                        )
            elif isinstance(pcb_return_paths, electrical_contracts.AnalysisPending):
                checks.append(
                    ElectricalCheck(
                        id="pcb-return-paths",
                        status="NOT_CONFIGURED",
                        detail=pcb_return_paths.reason,
                    )
                )
            else:
                checks.append(
                    ElectricalCheck(
                        id="pcb-return-paths",
                        status="NOT_APPLICABLE",
                        detail=pcb_return_paths.reason,
                    )
                )
            if isinstance(pin_connectivity, electrical_contracts.PinConnectivityAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="pin-connectivity",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(pin_relationship_checks(pin_connectivity, netlist))
            elif pin_connectivity is not None:
                checks.append(
                    ElectricalCheck(
                        id="pin-connectivity",
                        status="NOT_CONFIGURED"
                        if isinstance(pin_connectivity, electrical_contracts.AnalysisPending)
                        else "NOT_APPLICABLE",
                        detail=pin_connectivity.reason,
                    )
                )
            if isinstance(i2c_pullups, electrical_contracts.I2cPullupAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="i2c-pullups",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(i2c_pullup_checks(i2c_pullups, netlist))
            elif i2c_pullups is not None:
                checks.append(
                    ElectricalCheck(
                        id="i2c-pullups",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(i2c_pullups, electrical_contracts.AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=i2c_pullups.reason,
                    )
                )
            if isinstance(can_termination, electrical_contracts.CanTerminationAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="can-termination",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(can_termination_checks(can_termination, netlist))
            elif can_termination is not None:
                checks.append(
                    ElectricalCheck(
                        id="can-termination",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(can_termination, electrical_contracts.AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=can_termination.reason,
                    )
                )
            if isinstance(usb_c, electrical_contracts.UsbCAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="usb-c",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(usb_c_checks(usb_c, netlist))
            elif usb_c is not None:
                checks.append(
                    ElectricalCheck(
                        id="usb-c",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(usb_c, electrical_contracts.AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=usb_c.reason,
                    )
                )
            if isinstance(spi, electrical_contracts.SpiAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="spi",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(spi_checks(spi, netlist))
            elif spi is not None:
                checks.append(
                    ElectricalCheck(
                        id="spi",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(spi, electrical_contracts.AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=spi.reason,
                    )
                )
            if isinstance(serial_peers, electrical_contracts.SerialPeerAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="serial-peers",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(serial_peer_checks(serial_peers, netlist))
            elif serial_peers is not None:
                checks.append(
                    ElectricalCheck(
                        id="serial-peers",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(serial_peers, electrical_contracts.AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=serial_peers.reason,
                    )
                )
            if isinstance(digital_peer_voltages, electrical_contracts.DigitalPeerVoltageAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="digital-peer-voltages",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(digital_peer_voltage_checks(digital_peer_voltages, netlist))
            elif digital_peer_voltages is not None:
                checks.append(
                    ElectricalCheck(
                        id="digital-peer-voltages",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(
                                digital_peer_voltages, electrical_contracts.AnalysisPending
                            )
                            else "NOT_APPLICABLE"
                        ),
                        detail=digital_peer_voltages.reason,
                    )
                )
            if isinstance(
                component_voltage_ratings, electrical_contracts.ComponentVoltageRatingAnalysis
            ):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="component-voltage-ratings",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(
                        component_voltage_rating_checks(component_voltage_ratings, netlist)
                    )
            elif component_voltage_ratings is not None:
                checks.append(
                    ElectricalCheck(
                        id="component-voltage-ratings",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(
                                component_voltage_ratings, electrical_contracts.AnalysisPending
                            )
                            else "NOT_APPLICABLE"
                        ),
                        detail=component_voltage_ratings.reason,
                    )
                )
            if isinstance(
                component_power_ratings, electrical_contracts.ComponentPowerRatingAnalysis
            ):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="component-power-ratings",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(component_power_rating_checks(component_power_ratings, netlist))
            elif component_power_ratings is not None:
                checks.append(
                    ElectricalCheck(
                        id="component-power-ratings",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(
                                component_power_ratings, electrical_contracts.AnalysisPending
                            )
                            else "NOT_APPLICABLE"
                        ),
                        detail=component_power_ratings.reason,
                    )
                )
            if isinstance(
                connector_contact_ratings, electrical_contracts.ConnectorContactRatingAnalysis
            ):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="connector-contact-ratings",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(
                        connector_contact_rating_checks(connector_contact_ratings, netlist)
                    )
            elif connector_contact_ratings is not None:
                checks.append(
                    ElectricalCheck(
                        id="connector-contact-ratings",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(
                                connector_contact_ratings, electrical_contracts.AnalysisPending
                            )
                            else "NOT_APPLICABLE"
                        ),
                        detail=connector_contact_ratings.reason,
                    )
                )
            if isinstance(mosfet_stress, electrical_contracts.MosfetStressAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="mosfet-stress",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(mosfet_stress_checks(mosfet_stress, netlist))
            elif mosfet_stress is not None:
                checks.append(
                    ElectricalCheck(
                        id="mosfet-stress",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(mosfet_stress, electrical_contracts.AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=mosfet_stress.reason,
                    )
                )
            if isinstance(rs485, electrical_contracts.Rs485Analysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="rs485",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(rs485_checks(rs485, netlist))
            elif rs485 is not None:
                checks.append(
                    ElectricalCheck(
                        id="rs485",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(rs485, electrical_contracts.AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=rs485.reason,
                    )
                )
            if isinstance(control_inputs, electrical_contracts.ControlInputsAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="control-inputs",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(control_input_checks(control_inputs, netlist))
            elif control_inputs is not None:
                checks.append(
                    ElectricalCheck(
                        id="control-inputs",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(control_inputs, electrical_contracts.AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=control_inputs.reason,
                    )
                )
            if isinstance(power_connectivity, electrical_contracts.PowerConnectivityAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="power-connectivity",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(power_connectivity_checks(power_connectivity, netlist))
            elif power_connectivity is not None:
                checks.append(
                    ElectricalCheck(
                        id="power-connectivity",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(power_connectivity, electrical_contracts.AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=power_connectivity.reason,
                    )
                )
            if isinstance(test_access, electrical_contracts.TestAccessAnalysis):
                pcb_accessibility: (
                    pcb_test_access_models.PcbAccessAnalysis | ElectricalAnalysisState
                ) = test_access.pcb_accessibility
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="test-access/schematic",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(evaluate_test_access_checks(test_access, netlist))
                if isinstance(pcb_accessibility, pcb_test_access_models.PcbAccessAnalysis):
                    if config.kind is not ProjectKind.PCB:
                        checks.append(
                            ElectricalCheck(
                                id="test-access/pcb-accessibility/source",
                                status="FAIL",
                                detail="PCB access evidence is required, but this project has no PCB project kind.",
                            )
                        )
                    else:
                        board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
                        checks.extend(
                            pcb_accessibility_checks(
                                test_access,
                                pcb_accessibility,
                                board_path,
                            )
                        )
                elif isinstance(pcb_accessibility, electrical_contracts.AnalysisPending):
                    checks.append(
                        ElectricalCheck(
                            id="test-access/pcb-accessibility",
                            status="NOT_CONFIGURED",
                            detail=pcb_accessibility.reason,
                        )
                    )
                else:
                    checks.append(
                        ElectricalCheck(
                            id="test-access/pcb-accessibility",
                            status="NOT_APPLICABLE",
                            detail=pcb_accessibility.reason,
                        )
                    )
                if access_probe_requests is not None:
                    if config.kind is not ProjectKind.PCB:
                        checks.append(
                            ElectricalCheck(
                                id="test-access/pcb-probe-envelope/source",
                                status="FAIL",
                                detail="Probe-envelope evidence requires an authoritative PCB project.",
                            )
                        )
                    elif pcb_snapshot is None:
                        checks.append(
                            ElectricalCheck(
                                id="test-access/pcb-probe-envelope/native-probe",
                                status="NOT_RUN",
                                detail=pcb_probe_error
                                or "KiCad native PCB probing did not produce evidence.",
                            )
                        )
                    else:
                        checks.extend(pcb_probe_envelope_checks(test_access, pcb_snapshot))
            elif test_access is not None:
                access_status = (
                    "NOT_CONFIGURED"
                    if isinstance(test_access, electrical_contracts.AnalysisPending)
                    else "NOT_APPLICABLE"
                )
                checks.append(
                    ElectricalCheck(
                        id="test-access/schematic",
                        status=access_status,
                        detail=test_access.reason,
                    )
                )
                checks.append(
                    ElectricalCheck(
                        id="test-access/pcb-accessibility",
                        status=access_status,
                        detail=test_access.reason,
                    )
                )
            else:
                checks.append(
                    ElectricalCheck(
                        id="test-access/schematic",
                        status="NOT_CONFIGURED",
                        detail=(
                            "No test_access requirement or explicit not-applicable decision is "
                            "recorded in tests/electrical.json."
                        ),
                    )
                )
                checks.append(
                    ElectricalCheck(
                        id="test-access/pcb-accessibility",
                        status="NOT_CONFIGURED",
                        detail=(
                            "No PCB test-access requirements or explicit not-applicable decision "
                            "is recorded in tests/electrical.json."
                        ),
                    )
                )
            if isinstance(
                high_frequency,
                (electrical_contracts.AnalysisNotApplicable, electrical_contracts.AnalysisPending),
            ):
                checks.append(
                    ElectricalCheck(
                        id="high-frequency",
                        status="NOT_CONFIGURED"
                        if isinstance(high_frequency, electrical_contracts.AnalysisPending)
                        else "NOT_APPLICABLE",
                        detail=high_frequency.reason,
                    )
                )
            checks.extend(power_budget_checks(contract.power))
            cases = simulation_cases(contract)
            if cases:
                executable = executable_path(ngspice)
                try:
                    commands["version"] = simulator_version(
                        output, executable, contract.ngspice_version
                    )
                except ValueError as exc:
                    checks.extend(
                        ElectricalCheck(id=case.id, status="NOT_RUN", detail=str(exc))
                        for case in cases
                    )
                else:
                    for case in cases:
                        try:
                            command, measured = run_case(root, output, executable, case)
                            commands[case.id] = command
                            checks.extend(measured)
                        except (OSError, ValueError) as exc:
                            checks.append(
                                ElectricalCheck(id=case.id, status="FAIL", detail=str(exc))
                            )
            if bound_inputs(root, config, load_analysis(root, config) or contract) != inputs:
                raise ValueError("Electrical inputs changed during analysis")
            if source_state(root) != source:
                raise ValueError("Repository source changed during electrical analysis")
            status = (
                "PASS"
                if checks and all(c.status in {"PASS", "NOT_APPLICABLE"} for c in checks)
                else "FAIL"
            )
    except (OSError, ValueError) as exc:
        checks.append(ElectricalCheck(id="inputs", status="FAIL", detail=str(exc)))
    report = ElectricalAnalysisReport(
        project_id=project_id,
        source=source,
        status=status,
        run_directory=str(output),
        input_sha256=inputs,
        artifacts_sha256={
            path.relative_to(output).as_posix(): digest(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        },
        commands=commands,
        checks=tuple(checks),
    )
    write_model(output / "electrical.json", report)
    (output / "electrical.txt").write_text(format_report(report, "full") + "\n", encoding="utf-8")
    return report


def analyze_scope(
    root: Path,
    selector: ProjectSelector | None = None,
    cli: str = "kicad-cli",
    ngspice: str = "ngspice",
) -> ElectricalSuiteReport:
    """Run the same selected electrical scope for CLI and MCP, retaining every result."""
    identifiers = resolve_project_ids(root, selector or ProjectSelector())
    reports = tuple(
        analyze(root, project_id, cli=cli, ngspice=ngspice) for project_id in identifiers
    )
    return ElectricalSuiteReport(
        status="PASS" if reports and all(report.status == "PASS" for report in reports) else "FAIL",
        projects=reports,
    )


def format_report(
    report: ElectricalAnalysisReport, detail: Literal["brief", "full"] = "brief"
) -> str:
    lines = [f"Electrical analysis: {report.status}", f"Project: {report.project_id}"]
    failed = [row for row in report.checks if row.status not in {"PASS", "NOT_APPLICABLE"}]
    if detail == "brief":
        passed = sum(row.status == "PASS" for row in report.checks)
        excluded = sum(row.status == "NOT_APPLICABLE" for row in report.checks)
        lines.append(
            f"Checks: {passed} passed, {len(failed)} need attention, {excluded} not applicable"
        )
        shown = failed[:5]
    else:
        shown = report.checks
    lines.extend(f"  {row.id}: {row.status} — {row.detail}" for row in shown)
    if detail == "brief" and len(failed) > len(shown):
        lines.append("More findings: --detail full or --format json.")
    lines.append(f"Receipt: {report.run_directory}")
    if failed:
        lines.append(
            "Next: follow docs/workflow/ELECTRICAL_ANALYSIS.md or run "
            f"kicad_tooling.template doctor --electrical --project-id {report.project_id} --format text."
        )
    if detail == "full":
        lines.extend(f"Scope: {limit}" for limit in report.limits)
    else:
        lines.append(
            "Scope: declared pins, budgets and reviewed circuit models; layout and hardware acceptance remain separate."
        )
    return "\n".join(lines)
