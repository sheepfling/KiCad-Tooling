"""Run one project's fail-closed native KiCad validation operation."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypeAlias

import kicad_tooling.hwrepo.models as hwrepo_models

from .contracts import repo_path, write_model
from .discovery import load_config
from .evidence import digest as file_digest
from .evidence import source_state
from .kicad_compatibility import require_cli_profile
from .models import CheckEvidence, ValidationSummary
from .native_command import execute, svg_files, write_native_bom
from .native_project_validation_models import NativeProjectValidationRequest
from .native_report_parsing import check_netlist, check_report, read_netlist
from .native_toolchain import cli_executable, toolchain
from .pcb_dru_compilation import run_pcb_dru_compilation_probe
from .project_models import ProjectConfig, ProjectKind
from .project_source_hashes import hash_project_sources
from .source_state_models import SourceHashInventory

ValidationContract: TypeAlias = (
    hwrepo_models.PcbValidationContract
    | hwrepo_models.PcbOnlyValidationContract
    | hwrepo_models.SchematicValidationContract
    | hwrepo_models.SystemWiringValidationContract
    | hwrepo_models.HarnessInterfaceValidationContract
)


def validate_project(root: Path, request: NativeProjectValidationRequest) -> ValidationSummary:
    """Run a typed, fail-closed KiCad check for one declared configuration."""
    output = request.output
    cli = request.cli
    config_path = request.config_path
    output.mkdir(parents=True, exist_ok=False)
    root = root.resolve()
    source_before = source_state(root)
    checks: dict[str, CheckEvidence] = {}
    before: SourceHashInventory = {}
    source_roots: tuple[str, ...] = ("projects",)
    config: ProjectConfig | None = None
    profile: Literal["training", "development", "production"] | None = None
    not_for_manufacture: bool | None = None
    drc_rules_required = False
    selected_config = root / (
        Path("examples/projects/controller/project.json") if config_path is None else config_path
    )
    try:
        if root not in selected_config.resolve().parents:
            raise ValueError("Configuration path must remain inside the repository root")
        config = load_config(root, selected_config)
        validation_contract: ValidationContract = config.validation
        from .governance_lint import lint
        from .product import check as check_product
        from .product import (
            check_harness_interface_contract,
            check_project_netlist,
            check_system_wiring_contract,
        )
        from .repository import check_repository

        governance = lint(root, [config.project_id])
        repository = check_repository(root, (config.project_id,))
        product_policy = check_product(root, selected_project_ids=(config.project_id,))
        checks["governance"] = CheckEvidence(
            status=governance.status,
            error="; ".join(governance.issues) if governance.issues else None,
        )
        checks["repository"] = CheckEvidence(
            status=repository.status,
            error="; ".join(repository.issues) if repository.issues else None,
        )
        checks["product_policy"] = CheckEvidence(
            status=product_policy.status,
            error=(
                "; ".join(f"{issue.code}: {issue.message}" for issue in product_policy.issues)
                if product_policy.issues
                else None
            ),
        )
        if (
            governance.status != "PASS"
            or repository.status != "PASS"
            or product_policy.status != "PASS"
        ):
            raise ValueError(
                f"Repository preflight failed: {governance.issues}; {repository.issues}; {product_policy.issues}"
            )
        declared_toolchain = toolchain(root, config.toolchain_id)
        require_cli_profile(declared_toolchain)
        if (
            config.kicad_version != declared_toolchain.kicad_version
            or config.image != declared_toolchain.image
        ):
            raise ValueError(
                f"Configuration toolchain must match declared toolchain {config.toolchain_id}"
            )
        profile = config.assurance_profile
        not_for_manufacture = config.not_for_manufacture
        source_roots = config.source_roots
        before = hash_project_sources(root, source_roots)
        if set(before) != set(config.required_inputs):
            raise ValueError(
                f"Input inventory differs; missing={set(config.required_inputs) - set(before)}, "
                f"extra={set(before) - set(config.required_inputs)}"
            )
        checks["source_scope"] = CheckEvidence(
            status="PASS",
            source_hashes=before,
        )
        executable = cli_executable(cli)
        if executable is None:
            raise ValueError("KiCad executable is missing")
        version = execute((executable, "version"), root, output, "version")
        actual = version.stdout.strip()
        if version.returncode != 0 or actual != config.kicad_version:
            raise ValueError(f"Expected KiCad {config.kicad_version}; observed {actual!r}")
        checks["toolchain"] = CheckEvidence(
            status="PASS",
            observed_version=actual,
            image=config.image,
        )
        base = repo_path(root, config.project)
        commands: dict[str, tuple[str, ...]] = {}
        if config.kind is ProjectKind.PCB:
            validation = validation_contract
            if not isinstance(validation, hwrepo_models.PcbValidationContract):
                raise ValueError("PCB project requires a PCB validation contract")
            commands.update(
                {
                    "erc": (
                        "sch",
                        "erc",
                        "--format",
                        "json",
                        "--severity-all",
                        "--exit-code-violations",
                        "--output",
                        str(output / "erc.json"),
                        str(base.with_suffix(".kicad_sch")),
                    ),
                    "schematic_svg": (
                        "sch",
                        "export",
                        "svg",
                        "--output",
                        str(output / "schematic"),
                        str(base.with_suffix(".kicad_sch")),
                    ),
                    "drc": (
                        "pcb",
                        "drc",
                        "--format",
                        "json",
                        "--severity-all",
                        "--exit-code-violations",
                        "--schematic-parity",
                        "--refill-zones",
                        "--output",
                        str(output / "drc.json"),
                        str(base.with_suffix(".kicad_pcb")),
                    ),
                    "netlist": (
                        "sch",
                        "export",
                        "netlist",
                        "--format",
                        "kicadxml",
                        "--output",
                        str(output / "netlist.xml"),
                        str(base.with_suffix(".kicad_sch")),
                    ),
                    "pcb_svg": (
                        "pcb",
                        "export",
                        "svg",
                        "--layers",
                        "F.Cu,F.SilkS,Edge.Cuts,Cmts.User",
                        "--output",
                        str(output / "pcb.svg"),
                        str(base.with_suffix(".kicad_pcb")),
                    ),
                }
            )
        elif config.kind is ProjectKind.PCB_ONLY:
            validation = validation_contract
            if not isinstance(validation, hwrepo_models.PcbOnlyValidationContract):
                raise ValueError("PCB-only project requires a PCB-only validation contract")
            commands.update(
                {
                    "drc": (
                        "pcb",
                        "drc",
                        "--format",
                        "json",
                        "--severity-all",
                        "--exit-code-violations",
                        "--refill-zones",
                        "--output",
                        str(output / "drc.json"),
                        str(base.with_suffix(".kicad_pcb")),
                    ),
                    "pcb_svg": (
                        "pcb",
                        "export",
                        "svg",
                        "--layers",
                        "F.Cu,F.SilkS,Edge.Cuts,Cmts.User",
                        "--output",
                        str(output / "pcb.svg"),
                        str(base.with_suffix(".kicad_pcb")),
                    ),
                }
            )
        else:
            commands.update(
                {
                    "erc": (
                        "sch",
                        "erc",
                        "--format",
                        "json",
                        "--severity-all",
                        "--exit-code-violations",
                        "--output",
                        str(output / "erc.json"),
                        str(base.with_suffix(".kicad_sch")),
                    ),
                    "schematic_svg": (
                        "sch",
                        "export",
                        "svg",
                        "--output",
                        str(output / "schematic"),
                        str(base.with_suffix(".kicad_sch")),
                    ),
                }
            )
        if config.kind is ProjectKind.SYSTEM_WIRING:
            check_system_wiring_contract(root, config)
            checks["system_contract"] = CheckEvidence(status="PASS")
        elif config.kind is ProjectKind.HARNESS_INTERFACE:
            check_harness_interface_contract(root, config)
            checks["harness_contract"] = CheckEvidence(status="PASS")
        if (
            config.kind in {ProjectKind.PCB, ProjectKind.SCHEMATIC}
            or config.electrical is not None
            or config.component_identity.required
            or (
                isinstance(validation_contract, hwrepo_models.SchematicValidationContract)
                and validation_contract.components
            )
        ):
            commands["netlist"] = (
                "sch",
                "export",
                "netlist",
                "--format",
                "kicadxml",
                "--output",
                str(output / "netlist.xml"),
                str(base.with_suffix(".kicad_sch")),
            )
        for name, arguments in commands.items():
            command = execute((executable, *arguments), root, output, name)
            evidence = CheckEvidence(status="FAIL", returncode=command.returncode)
            try:
                if command.returncode != 0 and not (
                    name in {"erc", "drc"} and command.returncode == 5
                ):
                    raise ValueError(f"KiCad command failed with {command.returncode}")
                if name in {"erc", "drc"}:
                    kind: Literal["erc", "drc"] = "erc" if name == "erc" else "drc"
                    # KiCad uses exit 5 for findings. Retain their count and report
                    # identity even when the gate correctly rejects the design.
                    findings = check_report(output / f"{name}.json", kind, config)
                    evidence = evidence.model_copy(update={"findings": findings})
                    ignored = (
                        config.validation.expected_ignored_checks.erc
                        if kind == "erc"
                        else config.validation.expected_ignored_checks.drc
                    )
                    evidence = evidence.model_copy(
                        update={
                            "findings": findings,
                            "expected_ignored_checks": ignored,
                        }
                    )
                    if findings:
                        raise ValueError(f"{findings} findings, including exclusions")
                    if command.returncode != 0:
                        raise ValueError(f"KiCad command failed with {command.returncode}")
                elif name == "netlist":
                    validation = validation_contract
                    if not isinstance(
                        validation,
                        (
                            hwrepo_models.PcbValidationContract,
                            hwrepo_models.SchematicValidationContract,
                        ),
                    ):
                        raise ValueError("Netlist check requires an electrical component contract")
                    check_netlist(output / "netlist.xml", validation)
                    if config.electrical is not None:
                        from .electrical import grounding_checks, load_analysis

                        electrical = load_analysis(root, config)
                        if electrical is not None:
                            ground = grounding_checks(
                                electrical.grounding, read_netlist(output / "netlist.xml")
                            )
                            failures = [
                                row.detail
                                for row in ground
                                if row.status not in {"PASS", "NOT_APPLICABLE"}
                            ]
                            checks["grounding"] = CheckEvidence(
                                status="FAIL" if failures else "PASS",
                                error="; ".join(failures) if failures else None,
                            )
                    identity = check_project_netlist(
                        root, config.project_id, output / "netlist.xml"
                    )
                    disposition = (
                        "NOT FOR MANUFACTURE"
                        if config.not_for_manufacture
                        else "ENGINEERING — RELEASE REVIEW REQUIRED"
                    )
                    write_native_bom(output / "bom.csv", validation.components, disposition)
                    evidence = evidence.model_copy(update={"identity_status": identity.status})
                else:
                    evidence = evidence.model_copy(
                        update={
                            "files": tuple(
                                path.relative_to(output).as_posix()
                                for path in svg_files(output, name)
                            )
                        }
                    )
                checks[name] = evidence.model_copy(update={"status": "PASS"})
            except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
                checks[name] = evidence.model_copy(update={"error": str(exc)})
        if config.kind in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
            rules_path = base.with_suffix(".kicad_dru")
            if rules_path.is_file():
                drc_rules_required = True
                try:
                    report = run_pcb_dru_compilation_probe(
                        rules_path=rules_path,
                        project_path=base.with_suffix(".kicad_pro"),
                        repository_root=root,
                        output=output,
                        cli=executable,
                        expected_kicad_version=config.kicad_version,
                        image=config.image,
                        execute=execute,
                    )
                    source_hashes = {report.rules_path: report.rules_sha256}
                    if report.project_path is not None and report.project_sha256 is not None:
                        source_hashes[report.project_path] = report.project_sha256
                    checks["drc_rule_compilation"] = CheckEvidence(
                        status=report.status,
                        returncode=report.native_returncode,
                        error=report.issue,
                        findings=report.sentinel_matches,
                        files=(
                            "drc-rule-compilation.json",
                            "drc-rule-compilation/probe-drc.json",
                            "drc-rule-compilation/native-command.command.json",
                        ),
                        source_hashes=source_hashes,
                        observed_version=report.observed_kicad_version,
                        image=report.image,
                    )
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    checks["drc_rule_compilation"] = CheckEvidence(
                        status="FAIL",
                        error=str(exc),
                    )
    except (OSError, ValueError) as exc:
        checks["preflight"] = CheckEvidence(status="FAIL", error=str(exc))

    try:
        after = hash_project_sources(root, source_roots)
        checks["source_unchanged"] = CheckEvidence(
            status="PASS" if before == after else "FAIL",
            source_hashes=after,
        )
    except (OSError, ValueError) as exc:
        checks["source_unchanged"] = CheckEvidence(status="FAIL", error=str(exc))

    required = {"source_scope", "toolchain", "source_unchanged"}
    if config is not None and config.kind is ProjectKind.PCB:
        required.update({"erc", "schematic_svg", "drc", "netlist", "pcb_svg"})
    elif config is not None and config.kind is ProjectKind.PCB_ONLY:
        required.update({"drc", "pcb_svg"})
    else:
        required.update({"erc", "schematic_svg"})
        if config is not None and config.kind is ProjectKind.SYSTEM_WIRING:
            required.add("system_contract")
        elif config is not None and config.kind is ProjectKind.HARNESS_INTERFACE:
            required.add("harness_contract")
    if drc_rules_required:
        required.add("drc_rule_compilation")
    if config is not None and config.electrical is not None:
        required.add("grounding")
    if config is not None:
        final_validation: ValidationContract = config.validation
        if (
            config.kind in {ProjectKind.PCB, ProjectKind.SCHEMATIC}
            or config.electrical is not None
            or config.component_identity.required
            or (
                isinstance(final_validation, hwrepo_models.SchematicValidationContract)
                and final_validation.components
            )
        ):
            required.add("netlist")
    status = (
        "PASS"
        if required.issubset(checks)
        and all(evidence.status == "PASS" for evidence in checks.values())
        else "FAIL"
    )
    summary = ValidationSummary(
        timestamp_utc=datetime.now(UTC).isoformat(),
        checked_commit=source_before.commit or "LOCAL_UNBOUND",
        source=source_before.model_copy(
            update={
                "clean": source_before.clean and source_state(root) == source_before,
            }
        ),
        project_id=None if config is None else config.project_id,
        pr_head_commit=os.environ.get("PR_HEAD_SHA"),
        assurance_profile=profile,
        not_for_manufacture=not_for_manufacture,
        project_kind=None if config is None else config.kind,
        checks=checks,
        status=status,
        artifacts_sha256={
            path.relative_to(output).as_posix(): file_digest(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        },
    )
    write_model(output / "summary.json", summary)
    return summary
