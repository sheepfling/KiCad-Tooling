"""Run all configured electrical checks into a fresh, source-bound receipt."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypeAlias
from uuid import uuid4

import kicad_tooling.hwrepo.electrical_analysis_contract_models as electrical_contracts

from .command_evidence_models import CommandEvidence
from .component_power_ratings import component_power_rating_checks
from .component_voltage_ratings import component_voltage_rating_checks
from .connector_contact_ratings import connector_contact_rating_checks
from .contract_coach import (
    AutoNetlistRunner,
    ContainerNetlistRunner,
    LocalNetlistRunner,
    NetlistRunner,
    capture,
    inspect_summary,
    receipt_directory,
)
from .contracts import write_model
from .control_input_checks import control_input_checks
from .digital_peer_voltages import digital_peer_voltage_checks
from .electrical import (
    bind_electrical_inputs,
    grounding_checks,
    load_analysis,
    pin_relationship_checks,
    power_budget_checks,
    selected_config,
    simulation_cases,
)
from .electrical_bus_evaluation import (
    ElectricalBusEvaluationRequest,
    evaluate_electrical_bus_requirements,
)
from .electrical_netlist_evidence import (
    ElectricalNetlistEvidence,
    NetlistEvidenceNotRequested,
    NetlistEvidenceObserved,
    admit_netlist_evidence,
)
from .electrical_operation_models import ElectricalAnalysisRequest
from .electrical_pcb_evaluation import (
    ElectricalPcbReturnEvaluationRequest,
    ElectricalTestAccessEvaluationRequest,
    evaluate_electrical_test_access,
    evaluate_pcb_return_paths,
)
from .electrical_pcb_evidence import (
    ElectricalPcbEvidence,
    PcbEvidenceNotRequested,
    PcbEvidenceObserved,
    admit_pcb_evidence,
)
from .electrical_report_models import (
    ElectricalAnalysisReport,
    ElectricalCheck,
    ElectricalSuiteReport,
)
from .electrical_simulation_evaluation import (
    ElectricalSimulationEvaluationRequest,
    evaluate_electrical_simulations,
)
from .electrical_simulation_evidence import SimulationVersionObserved
from .evidence import digest, source_state
from .model_primitives import Digest, RepositoryPath
from .mosfet_stress import mosfet_stress_checks
from .netlist_contract_models import NetlistContract
from .pcb_return_path_capture import capture_native_pcb_connectivity, expected_probe_sha256
from .power_connectivity import power_connectivity_checks
from .project_models import ProjectKind
from .rs485_heuristics import rs485_checks
from .selection import ProjectSelector, resolve_project_ids
from .serial_heuristics import serial_peer_checks
from .test_access import pcb_access_probe_request_set

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
    """Compatibility adapter for the typed electrical-analysis operation."""
    request = ElectricalAnalysisRequest(
        project_id=project_id,
        output=output,
        native_summary=native_summary,
        cli=cli,
        ngspice=ngspice,
    )
    if runner is None:
        return analyze_request(root, request)
    return _analyze(root, request, runner)


def analyze_request(
    root: Path,
    request: ElectricalAnalysisRequest,
) -> ElectricalAnalysisReport:
    """Run electrical analysis from one typed request and the selected fixed runner."""
    return _analyze(root, request, None)


def _selected_netlist_runner(request: ElectricalAnalysisRequest) -> NetlistRunner:
    if request.runner_mode == "local":
        return LocalNetlistRunner(request.cli)
    if request.runner_mode == "container":
        return ContainerNetlistRunner()
    return AutoNetlistRunner(request.cli)


def _analyze(
    root: Path,
    request: ElectricalAnalysisRequest,
    runner: NetlistRunner | None,
) -> ElectricalAnalysisReport:
    project_id = request.project_id
    output = request.output
    native_summary = request.native_summary
    ngspice = request.ngspice
    root = root.resolve()
    source = source_state(root)
    if native_summary is not None and not native_summary.is_absolute():
        native_summary = root / native_summary
    if output is None:
        output = Path("build/electrical") / f"{project_id}-{uuid4().hex[:12]}"
    output = receipt_directory(root, project_id, output)
    checks: list[ElectricalCheck] = []
    commands: dict[str, CommandEvidence] = {}
    inputs: dict[RepositoryPath, Digest] = {}
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
            inputs = bind_electrical_inputs(root, config, contract)
            write_model(output / "requirements.json", contract)
            netlist_evidence: ElectricalNetlistEvidence = NetlistEvidenceNotRequested(
                project_id=project_id
            )
            netlist: NetlistContract | None = None
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
                    netlist_report = capture(
                        root,
                        project_id,
                        netlist_output,
                        runner or _selected_netlist_runner(request),
                    )
                else:
                    netlist_report = inspect_summary(root, project_id, native_summary)
                write_model(output / "netlist-evidence.json", netlist_report)
                netlist_evidence = admit_netlist_evidence(
                    netlist_report,
                    project_id,
                    {name: inputs[name] for name in config.required_inputs},
                )
                if isinstance(netlist_evidence, NetlistEvidenceObserved):
                    netlist = netlist_evidence.observed
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
            pcb_evidence: ElectricalPcbEvidence = PcbEvidenceNotRequested(project_id=project_id)
            needs_pcb_probe = (
                isinstance(pcb_return_paths, electrical_contracts.PcbReturnPathsAnalysis)
                or access_probe_requests is not None
            )
            if needs_pcb_probe:
                if config.kind is not ProjectKind.PCB:
                    pcb_evidence = admit_pcb_evidence(
                        project_id,
                        None,
                        None,
                        reason="PCB native evidence requires an authoritative PCB project.",
                        access_probe_requests=access_probe_requests,
                    )
                else:
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
                            pcb_evidence = admit_pcb_evidence(
                                project_id,
                                command,
                                None,
                                reason=(
                                    "KiCad native PCB probing did not produce evidence; inspect "
                                    "pcb-connectivity/native.command.json."
                                ),
                                access_probe_requests=access_probe_requests,
                            )
                        else:
                            write_model(output / "pcb-connectivity/snapshot.json", pcb_snapshot)
                            pcb_evidence = admit_pcb_evidence(
                                project_id,
                                command,
                                pcb_snapshot,
                                access_probe_requests=access_probe_requests,
                            )
                    except (OSError, ValueError) as exc:
                        pcb_evidence = admit_pcb_evidence(
                            project_id,
                            None,
                            None,
                            reason=str(exc) or "KiCad native PCB probing did not produce evidence.",
                            access_probe_requests=access_probe_requests,
                        )
            checks.extend(
                evaluate_pcb_return_paths(
                    ElectricalPcbReturnEvaluationRequest(
                        project_id=project_id,
                        root=root,
                        config=config,
                        requirement=pcb_return_paths,
                        evidence=pcb_evidence,
                        expected_probe_sha256=(
                            expected_probe_sha256()
                            if isinstance(
                                pcb_return_paths, electrical_contracts.PcbReturnPathsAnalysis
                            )
                            and isinstance(pcb_evidence, PcbEvidenceObserved)
                            else None
                        ),
                    )
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
            checks.extend(
                evaluate_electrical_bus_requirements(
                    ElectricalBusEvaluationRequest(
                        project_id=project_id,
                        netlist_evidence=netlist_evidence,
                        i2c_pullups=i2c_pullups,
                        can_termination=can_termination,
                        usb_c=usb_c,
                        spi=spi,
                    )
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
            checks.extend(
                evaluate_electrical_test_access(
                    ElectricalTestAccessEvaluationRequest(
                        project_id=project_id,
                        root=root,
                        config=config,
                        requirement=test_access,
                        netlist_evidence=netlist_evidence,
                        pcb_evidence=pcb_evidence,
                    )
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
            simulation = evaluate_electrical_simulations(
                ElectricalSimulationEvaluationRequest(
                    project_id=project_id,
                    root=root,
                    output=output,
                    ngspice=ngspice,
                    expected_version=contract.ngspice_version,
                    source_sha256={name: inputs[name] for name in config.required_inputs},
                    cases=simulation_cases(contract),
                )
            )
            if isinstance(simulation.version, SimulationVersionObserved):
                commands["version"] = simulation.version.command
            for result in simulation.cases:
                if result.command is not None:
                    commands[result.case.id] = result.command
                checks.extend(result.checks)
            bind_electrical_inputs(root, config, contract, inputs)
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
        analyze_request(
            root,
            ElectricalAnalysisRequest(project_id=project_id, cli=cli, ngspice=ngspice),
        )
        for project_id in identifiers
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
