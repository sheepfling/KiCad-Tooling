"""Run all configured electrical checks into a fresh, source-bound receipt."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

from .can_termination_contract import can_termination_checks
from .can_termination_models import CanTerminationAnalysis
from .component_power_ratings import component_power_rating_checks
from .component_rating_models import (
    ComponentPowerRatingAnalysis,
    ComponentVoltageRatingAnalysis,
)
from .component_voltage_ratings import component_voltage_rating_checks
from .connector_contact_rating_models import ConnectorContactRatingAnalysis
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
from .digital_peer_voltage_models import DigitalPeerVoltageAnalysis
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
from .i2c_pullup_models import I2cPullupAnalysis
from .models import (
    AnalysisNotApplicable,
    AnalysisPending,
    CommandEvidence,
    ControlInputsAnalysis,
    ElectricalAnalysisReport,
    ElectricalCheck,
    ElectricalSuiteReport,
    GroundingAnalysis,
    PcbAccessAnalysis,
    PcbReturnPathsAnalysis,
    PinConnectivityAnalysis,
    PowerConnectivityAnalysis,
    ProjectKind,
    TestAccessAnalysis,
    UsbCAnalysis,
)
from .mosfet_stress import mosfet_stress_checks
from .mosfet_stress_models import MosfetStressAnalysis
from .pcb_return_path_capture import capture_native_pcb_connectivity, expected_probe_sha256
from .pcb_return_path_checks import pcb_return_path_checks
from .power_connectivity import power_connectivity_checks
from .rs485_heuristics import rs485_checks
from .rs485_models import Rs485Analysis
from .selection import ProjectSelector, resolve_project_ids
from .serial_heuristics import serial_peer_checks
from .serial_peer_models import SerialPeerAnalysis
from .spi_contract import spi_checks
from .spi_models import SpiAnalysis
from .spice import executable_path, run_case, simulator_version
from .test_access import (
    evaluate_test_access_checks,
    pcb_access_probe_request_set,
    pcb_accessibility_checks,
    pcb_probe_envelope_checks,
)
from .usb_c_contract import usb_c_checks


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
            inputs = bound_inputs(root, config, contract)
            write_model(output / "requirements.json", contract)
            netlist = None
            needs_netlist = any(
                (
                    isinstance(contract.grounding, GroundingAnalysis),
                    isinstance(contract.pin_connectivity, PinConnectivityAnalysis),
                    isinstance(contract.i2c_pullups, I2cPullupAnalysis),
                    isinstance(contract.can_termination, CanTerminationAnalysis),
                    isinstance(contract.usb_c, UsbCAnalysis),
                    isinstance(contract.spi, SpiAnalysis),
                    isinstance(contract.serial_peers, SerialPeerAnalysis),
                    isinstance(contract.digital_peer_voltages, DigitalPeerVoltageAnalysis),
                    isinstance(contract.component_voltage_ratings, ComponentVoltageRatingAnalysis),
                    isinstance(contract.component_power_ratings, ComponentPowerRatingAnalysis),
                    isinstance(contract.connector_contact_ratings, ConnectorContactRatingAnalysis),
                    isinstance(contract.mosfet_stress, MosfetStressAnalysis),
                    isinstance(contract.rs485, Rs485Analysis),
                    isinstance(contract.control_inputs, ControlInputsAnalysis),
                    isinstance(contract.power_connectivity, PowerConnectivityAnalysis),
                    isinstance(contract.test_access, TestAccessAnalysis),
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
            if isinstance(contract.grounding, GroundingAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="grounding",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(grounding_checks(contract.grounding, netlist))
            else:
                checks.append(
                    ElectricalCheck(
                        id="grounding",
                        status="NOT_CONFIGURED"
                        if isinstance(contract.grounding, AnalysisPending)
                        else "NOT_APPLICABLE",
                        detail=contract.grounding.reason,
                    )
                )
            access_probe_requests = (
                pcb_access_probe_request_set(contract.test_access)
                if isinstance(contract.test_access, TestAccessAnalysis)
                else None
            )
            pcb_snapshot = None
            pcb_probe_error: str | None = None
            needs_pcb_probe = (
                isinstance(contract.pcb_return_paths, PcbReturnPathsAnalysis)
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
            if isinstance(contract.pcb_return_paths, PcbReturnPathsAnalysis):
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
                                contract.pcb_return_paths,
                                pcb_snapshot,
                                board_sha256=digest(board_path),
                                kicad_version=config.kicad_version,
                                image=config.image,
                                probe_sha256=expected_probe_sha256(),
                            )
                        )
            elif isinstance(contract.pcb_return_paths, AnalysisPending):
                checks.append(
                    ElectricalCheck(
                        id="pcb-return-paths",
                        status="NOT_CONFIGURED",
                        detail=contract.pcb_return_paths.reason,
                    )
                )
            else:
                checks.append(
                    ElectricalCheck(
                        id="pcb-return-paths",
                        status="NOT_APPLICABLE",
                        detail=contract.pcb_return_paths.reason,
                    )
                )
            if isinstance(contract.pin_connectivity, PinConnectivityAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="pin-connectivity",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(pin_relationship_checks(contract.pin_connectivity, netlist))
            elif contract.pin_connectivity is not None:
                checks.append(
                    ElectricalCheck(
                        id="pin-connectivity",
                        status="NOT_CONFIGURED"
                        if isinstance(contract.pin_connectivity, AnalysisPending)
                        else "NOT_APPLICABLE",
                        detail=contract.pin_connectivity.reason,
                    )
                )
            if isinstance(contract.i2c_pullups, I2cPullupAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="i2c-pullups",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(i2c_pullup_checks(contract.i2c_pullups, netlist))
            elif contract.i2c_pullups is not None:
                checks.append(
                    ElectricalCheck(
                        id="i2c-pullups",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.i2c_pullups, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.i2c_pullups.reason,
                    )
                )
            if isinstance(contract.can_termination, CanTerminationAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="can-termination",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(can_termination_checks(contract.can_termination, netlist))
            elif contract.can_termination is not None:
                checks.append(
                    ElectricalCheck(
                        id="can-termination",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.can_termination, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.can_termination.reason,
                    )
                )
            if isinstance(contract.usb_c, UsbCAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="usb-c",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(usb_c_checks(contract.usb_c, netlist))
            elif contract.usb_c is not None:
                checks.append(
                    ElectricalCheck(
                        id="usb-c",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.usb_c, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.usb_c.reason,
                    )
                )
            if isinstance(contract.spi, SpiAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="spi",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(spi_checks(contract.spi, netlist))
            elif contract.spi is not None:
                checks.append(
                    ElectricalCheck(
                        id="spi",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.spi, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.spi.reason,
                    )
                )
            if isinstance(contract.serial_peers, SerialPeerAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="serial-peers",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(serial_peer_checks(contract.serial_peers, netlist))
            elif contract.serial_peers is not None:
                checks.append(
                    ElectricalCheck(
                        id="serial-peers",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.serial_peers, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.serial_peers.reason,
                    )
                )
            if isinstance(contract.digital_peer_voltages, DigitalPeerVoltageAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="digital-peer-voltages",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(
                        digital_peer_voltage_checks(contract.digital_peer_voltages, netlist)
                    )
            elif contract.digital_peer_voltages is not None:
                checks.append(
                    ElectricalCheck(
                        id="digital-peer-voltages",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.digital_peer_voltages, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.digital_peer_voltages.reason,
                    )
                )
            if isinstance(contract.component_voltage_ratings, ComponentVoltageRatingAnalysis):
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
                        component_voltage_rating_checks(contract.component_voltage_ratings, netlist)
                    )
            elif contract.component_voltage_ratings is not None:
                checks.append(
                    ElectricalCheck(
                        id="component-voltage-ratings",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.component_voltage_ratings, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.component_voltage_ratings.reason,
                    )
                )
            if isinstance(contract.component_power_ratings, ComponentPowerRatingAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="component-power-ratings",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(
                        component_power_rating_checks(contract.component_power_ratings, netlist)
                    )
            elif contract.component_power_ratings is not None:
                checks.append(
                    ElectricalCheck(
                        id="component-power-ratings",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.component_power_ratings, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.component_power_ratings.reason,
                    )
                )
            if isinstance(contract.connector_contact_ratings, ConnectorContactRatingAnalysis):
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
                        connector_contact_rating_checks(contract.connector_contact_ratings, netlist)
                    )
            elif contract.connector_contact_ratings is not None:
                checks.append(
                    ElectricalCheck(
                        id="connector-contact-ratings",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.connector_contact_ratings, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.connector_contact_ratings.reason,
                    )
                )
            if isinstance(contract.mosfet_stress, MosfetStressAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="mosfet-stress",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(mosfet_stress_checks(contract.mosfet_stress, netlist))
            elif contract.mosfet_stress is not None:
                checks.append(
                    ElectricalCheck(
                        id="mosfet-stress",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.mosfet_stress, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.mosfet_stress.reason,
                    )
                )
            if isinstance(contract.rs485, Rs485Analysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="rs485",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(rs485_checks(contract.rs485, netlist))
            elif contract.rs485 is not None:
                checks.append(
                    ElectricalCheck(
                        id="rs485",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.rs485, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.rs485.reason,
                    )
                )
            if isinstance(contract.control_inputs, ControlInputsAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="control-inputs",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(control_input_checks(contract.control_inputs, netlist))
            elif contract.control_inputs is not None:
                checks.append(
                    ElectricalCheck(
                        id="control-inputs",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.control_inputs, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.control_inputs.reason,
                    )
                )
            if isinstance(contract.power_connectivity, PowerConnectivityAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="power-connectivity",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(power_connectivity_checks(contract.power_connectivity, netlist))
            elif contract.power_connectivity is not None:
                checks.append(
                    ElectricalCheck(
                        id="power-connectivity",
                        status=(
                            "NOT_CONFIGURED"
                            if isinstance(contract.power_connectivity, AnalysisPending)
                            else "NOT_APPLICABLE"
                        ),
                        detail=contract.power_connectivity.reason,
                    )
                )
            if isinstance(contract.test_access, TestAccessAnalysis):
                if netlist is None:
                    checks.append(
                        ElectricalCheck(
                            id="test-access/schematic",
                            status="FAIL",
                            detail="No current source-bound netlist; inspect netlist-evidence.json.",
                        )
                    )
                else:
                    checks.extend(evaluate_test_access_checks(contract.test_access, netlist))
                if isinstance(contract.test_access.pcb_accessibility, PcbAccessAnalysis):
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
                                contract.test_access,
                                contract.test_access.pcb_accessibility,
                                board_path,
                            )
                        )
                elif isinstance(contract.test_access.pcb_accessibility, AnalysisPending):
                    checks.append(
                        ElectricalCheck(
                            id="test-access/pcb-accessibility",
                            status="NOT_CONFIGURED",
                            detail=contract.test_access.pcb_accessibility.reason,
                        )
                    )
                else:
                    checks.append(
                        ElectricalCheck(
                            id="test-access/pcb-accessibility",
                            status="NOT_APPLICABLE",
                            detail=contract.test_access.pcb_accessibility.reason,
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
                        checks.extend(pcb_probe_envelope_checks(contract.test_access, pcb_snapshot))
            elif contract.test_access is not None:
                access_status = (
                    "NOT_CONFIGURED"
                    if isinstance(contract.test_access, AnalysisPending)
                    else "NOT_APPLICABLE"
                )
                checks.append(
                    ElectricalCheck(
                        id="test-access/schematic",
                        status=access_status,
                        detail=contract.test_access.reason,
                    )
                )
                checks.append(
                    ElectricalCheck(
                        id="test-access/pcb-accessibility",
                        status=access_status,
                        detail=contract.test_access.reason,
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
            if isinstance(contract.high_frequency, (AnalysisNotApplicable, AnalysisPending)):
                checks.append(
                    ElectricalCheck(
                        id="high-frequency",
                        status="NOT_CONFIGURED"
                        if isinstance(contract.high_frequency, AnalysisPending)
                        else "NOT_APPLICABLE",
                        detail=contract.high_frequency.reason,
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
