"""Re-evaluate retained native evidence against current project contracts."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

import kicad_tooling.hwrepo.electrical_analysis_contract_models as electrical_contracts
import kicad_tooling.hwrepo.models as model_contracts
from kicad_tooling.hwrepo import pcb_test_access_models

from ..validate import check_netlist, check_report, read_netlist, svg_files
from .can_termination_contract import can_termination_checks
from .contracts import read_model, repo_path
from .control_input_checks import control_input_checks
from .discovery import load_config, load_registry
from .electrical import grounding_checks, load_analysis
from .evidence import digest, evidence_path, verify_source
from .i2c_pullup_contract import i2c_pullup_checks
from .models import CommandEvidence, EvidenceFile, ProjectKind, SourceState, ValidationSummary
from .power_connectivity import power_connectivity_checks
from .product import check_project_netlist
from .rs485_heuristics import rs485_checks
from .test_access import evaluate_test_access_checks, pcb_accessibility_checks

ElectricalAnalysisState: TypeAlias = (
    electrical_contracts.AnalysisNotApplicable | electrical_contracts.AnalysisPending
)
ProjectValidation: TypeAlias = (
    model_contracts.PcbValidationContract
    | model_contracts.PcbOnlyValidationContract
    | model_contracts.SchematicValidationContract
    | model_contracts.SystemWiringValidationContract
    | model_contracts.HarnessInterfaceValidationContract
)


def verify_native(
    root: Path, reference: EvidenceFile, source: SourceState, project_id: str
) -> ValidationSummary:

    path = evidence_path(root, reference)
    report = read_model(path, ValidationSummary)
    verify_source(report.source, source)
    project = next(project for project in load_registry(root).projects if project.id == project_id)
    config = load_config(root, project.config)
    validation: ProjectValidation = config.validation
    if report.checked_commit != source.commit or report.project_id != project_id:
        raise ValueError("Native report identifies a different project or source commit")
    if (
        report.project_kind != config.kind
        or report.assurance_profile != config.assurance_profile
        or report.not_for_manufacture != config.not_for_manufacture
    ):
        raise ValueError("Native report metadata differs from the project manifest")
    required = {
        "governance",
        "repository",
        "product_policy",
        "source_scope",
        "source_unchanged",
        "toolchain",
    }
    if project.kind is ProjectKind.PCB:
        required.update({"erc", "schematic_svg", "drc", "netlist", "pcb_svg"})
    elif project.kind is ProjectKind.PCB_ONLY:
        required.update({"drc", "pcb_svg"})
    elif project.kind is ProjectKind.SYSTEM_WIRING:
        required.update({"erc", "schematic_svg", "system_contract"})
    elif project.kind is ProjectKind.HARNESS_INTERFACE:
        required.update({"erc", "schematic_svg", "harness_contract"})
    else:
        required.update({"erc", "schematic_svg"})
    if config.electrical is not None:
        required.add("grounding")
    if (
        config.electrical is not None
        or config.component_identity.required
        or (
            isinstance(validation, model_contracts.SchematicValidationContract)
            and validation.components
        )
    ):
        required.add("netlist")
    if (
        report.status != "PASS"
        or not required <= report.checks.keys()
        or any(
            check.status != "PASS"
            or check.error is not None
            or check.returncode not in {None, 0}
            or check.findings not in {None, 0}
            for check in report.checks.values()
        )
    ):
        raise ValueError("Native report contains failed or missing checks")
    toolchain = report.checks["toolchain"]
    if toolchain.observed_version != config.kicad_version or toolchain.image != config.image:
        raise ValueError("Native toolchain differs from the pinned project toolchain")
    expected = {name: source.files_sha256[name] for name in config.required_inputs}
    if any(
        report.checks[name].source_hashes != expected
        for name in ("source_scope", "source_unchanged")
    ):
        raise ValueError("Native design inventory differs from committed inputs")
    if not report.artifacts_sha256:
        raise ValueError("Native report retains no artifacts")
    for name, expected_digest in report.artifacts_sha256.items():
        if digest(repo_path(path.parent, name)) != expected_digest:
            raise ValueError(f"Missing or changed native artifact: {name}")
    # Re-evaluate the retained native outputs, rather than trusting summary labels.

    if config.electrical is not None:
        electrical = load_analysis(root, config)
        if electrical is not None:
            i2c_pullups: electrical_contracts.I2cPullupAnalysis | ElectricalAnalysisState | None = (
                electrical.i2c_pullups
            )
            can_termination: (
                electrical_contracts.CanTerminationAnalysis | ElectricalAnalysisState | None
            ) = electrical.can_termination
            rs485: electrical_contracts.Rs485Analysis | ElectricalAnalysisState | None = (
                electrical.rs485
            )
            control_inputs: (
                electrical_contracts.ControlInputsAnalysis | ElectricalAnalysisState | None
            ) = electrical.control_inputs
            test_access: (
                electrical_contracts.TestAccessAnalysis | ElectricalAnalysisState | None
            ) = electrical.test_access
            power_connectivity: (
                electrical_contracts.PowerConnectivityAnalysis | ElectricalAnalysisState | None
            ) = electrical.power_connectivity
            netlist = read_netlist(path.parent / "netlist.xml")
            if any(
                row.status not in {"PASS", "NOT_APPLICABLE"}
                for row in grounding_checks(electrical.grounding, netlist)
            ):
                raise ValueError("Retained netlist fails current grounding requirements")
            if isinstance(i2c_pullups, electrical_contracts.I2cPullupAnalysis) and any(
                row.status != "PASS" for row in i2c_pullup_checks(i2c_pullups, netlist)
            ):
                raise ValueError("Retained netlist fails current I2C pull-up requirements")
            if isinstance(i2c_pullups, electrical_contracts.AnalysisPending):
                raise ValueError("Current I2C pull-up requirements remain pending")
            if isinstance(can_termination, electrical_contracts.CanTerminationAnalysis) and any(
                row.status not in {"PASS", "NOT_APPLICABLE"}
                for row in can_termination_checks(can_termination, netlist)
            ):
                raise ValueError("Retained netlist fails current CAN termination requirements")
            if isinstance(can_termination, electrical_contracts.AnalysisPending):
                raise ValueError("Current CAN termination requirements remain pending")
            if isinstance(rs485, electrical_contracts.Rs485Analysis) and any(
                row.status not in {"PASS", "NOT_APPLICABLE"} for row in rs485_checks(rs485, netlist)
            ):
                raise ValueError("Retained netlist fails current RS-485 requirements")
            if isinstance(rs485, electrical_contracts.AnalysisPending):
                raise ValueError("Current RS-485 requirements remain pending")
            if isinstance(control_inputs, electrical_contracts.ControlInputsAnalysis) and any(
                row.status not in {"PASS", "NOT_APPLICABLE"}
                for row in control_input_checks(control_inputs, netlist)
            ):
                raise ValueError("Retained netlist fails current control-input requirements")
            if isinstance(control_inputs, electrical_contracts.AnalysisPending):
                raise ValueError("Current control-input requirements remain pending")
            if isinstance(test_access, electrical_contracts.TestAccessAnalysis) and any(
                row.status not in {"PASS", "NOT_APPLICABLE"}
                for row in evaluate_test_access_checks(test_access, netlist)
            ):
                raise ValueError("Retained netlist fails current test-access requirements")
            if isinstance(test_access, electrical_contracts.TestAccessAnalysis):
                pcb_accessibility: (
                    pcb_test_access_models.PcbAccessAnalysis | ElectricalAnalysisState
                ) = test_access.pcb_accessibility
                if isinstance(pcb_accessibility, pcb_test_access_models.PcbAccessAnalysis):
                    if config.kind is not ProjectKind.PCB:
                        raise ValueError("Current PCB access requirements need a PCB project")
                    board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
                    if any(
                        row.status not in {"PASS", "NOT_APPLICABLE"}
                        for row in pcb_accessibility_checks(
                            test_access,
                            pcb_accessibility,
                            board_path,
                        )
                    ):
                        raise ValueError("Retained PCB pad access fails current requirements")
                elif isinstance(pcb_accessibility, electrical_contracts.AnalysisPending):
                    raise ValueError("Current PCB test-access requirements remain pending")  # noqa: TRY004
            if isinstance(test_access, electrical_contracts.AnalysisPending) or test_access is None:
                raise ValueError("Current test-access requirements remain pending")
            if isinstance(
                power_connectivity, electrical_contracts.PowerConnectivityAnalysis
            ) and any(
                row.status not in {"PASS", "NOT_APPLICABLE"}
                for row in power_connectivity_checks(power_connectivity, netlist)
            ):
                raise ValueError("Retained netlist fails current power connectivity requirements")
            if isinstance(power_connectivity, electrical_contracts.AnalysisPending):
                raise ValueError("Current power connectivity requirements remain pending")

    commands = {"version"}
    if isinstance(validation, model_contracts.PcbOnlyValidationContract):
        commands.update({"drc", "pcb_svg"})
        if check_report(path.parent / "drc.json", "drc", config):
            raise ValueError("Retained DRC report contains findings")
        svg_files(path.parent, "pcb_svg")
    else:
        commands.update({"erc", "schematic_svg"})
        if check_report(path.parent / "erc.json", "erc", config):
            raise ValueError("Retained ERC report contains findings")
        svg_files(path.parent, "schematic_svg")
    if isinstance(validation, model_contracts.PcbValidationContract):
        commands.update({"drc", "netlist", "pcb_svg"})
        if check_report(path.parent / "drc.json", "drc", config):
            raise ValueError("Retained DRC report contains findings")
        svg_files(path.parent, "pcb_svg")
    if "netlist" in required:
        commands.add("netlist")
        if isinstance(
            validation,
            (model_contracts.PcbValidationContract, model_contracts.SchematicValidationContract),
        ):
            check_netlist(path.parent / "netlist.xml", validation)
        check_project_netlist(root, project_id, path.parent / "netlist.xml")
        if (
            config.component_identity.required
            and report.checks["netlist"].identity_status != "PASS"
        ):
            raise ValueError("Required component identity was not checked")
    for name in commands:
        filename = f"{name}.command.json"
        if filename not in report.artifacts_sha256:
            raise ValueError(f"Native command evidence is missing: {name}")
        command = read_model(path.parent / filename, CommandEvidence)
        if command.returncode != 0 or command.error is not None:
            raise ValueError(f"Retained native command failed: {name}")
    return report
