"""Hosted native fixture lane for mapped and heuristic power paths."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_power_path_native_evidence import validate_power_path_fixture_netlist
from .ci_hosted_power_path_requirements import power_path_requirement_map

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def power_path_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Compare mapped and heuristic power paths with repeated pinned exports and ERC."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.contracts import read_kicad_erc_report, write_model
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
    )
    from .hwrepo.power_paths import PowerPathMismatch, power_path_mismatches
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Power-path fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/power-path-native"
    )
    cases = {
        "control": "control.kicad_sch",
        "fault": "fault.kicad_sch",
        "diode-control": "diode-control.kicad_sch",
        "diode-reverse-fault": "diode-reverse-fault.kicad_sch",
        "schottky-diode-control": "schottky-diode-control.kicad_sch",
        "bridged-jumper-control": "bridged-jumper-control.kicad_sch",
        "open-jumper-fault": "open-jumper-fault.kicad_sch",
        "bridged-three-pin12-control": "bridged-three-pin12-control.kicad_sch",
        "bridged-three-pin123-control": "bridged-three-pin123-control.kicad_sch",
        "bridged-three-pin12-unbridged-terminal-fault": (
            "bridged-three-pin12-unbridged-terminal-fault.kicad_sch"
        ),
        "isolated-control": "isolated-control.kicad_sch",
        "custom-capacitor-control": "custom-capacitor-control.kicad_sch",
        "custom-capacitor-fault": "custom-capacitor-fault.kicad_sch",
        "opaque-capacitor-fault": "opaque-capacitor-fault.kicad_sch",
        "external-source-control": "external-source-control.kicad_sch",
        "dnp-external-source-fault": "dnp-external-source-fault.kicad_sch",
        "alternate-source-control": "alternate-source-control.kicad_sch",
        "both-sources-dnp-fault": "both-sources-dnp-fault.kicad_sch",
    }
    source_hashes = {case: digest(fixture_root / filename) for case, filename in cases.items()}
    scratch = Path(tempfile.mkdtemp(prefix=f"power-path-{project}-", dir=log.directory.resolve()))
    inputs = scratch / "input"
    inputs.mkdir()
    for case, filename in cases.items():
        shutil.copyfile(fixture_root / filename, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} power-path fixture changed during native input")
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")

    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{config.kicad_version}"\n'
        "for case in control fault diode-control diode-reverse-fault schottky-diode-control "
        "bridged-jumper-control open-jumper-fault bridged-three-pin12-control "
        "bridged-three-pin123-control bridged-three-pin12-unbridged-terminal-fault "
        "isolated-control custom-capacitor-control "
        "custom-capacitor-fault opaque-capacitor-fault external-source-control "
        "dnp-external-source-fault alternate-source-control both-sources-dnp-fault; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
        '      "/fixtures/${case}.kicad_sch"\n'
        "    kicad-cli sch erc --format json --severity-all "
        '      --output "/output/${case}.${run}.erc.json" '
        '      "/fixtures/${case}.kicad_sch"\n'
        "  done\n"
        "done\n"
    )
    argv = (
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        *user,
        "-e",
        "HOME=/tmp/kicad-power-path-fixtures",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    log.event(
        "power-path-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "power-path-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native power-path fixture command failed: {command.stderr or command.error}"
        )

    path_map = power_path_requirement_map()

    normalized_hashes: dict[tuple[str, str], str] = {}
    normalized_erc_hashes: dict[tuple[str, str], str] = {}
    raw_erc_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    unmapped_reports: dict[tuple[str, str], DesignLintReport] = {}
    mismatches_by_case: dict[tuple[str, str], tuple[PowerPathMismatch, ...]] = {}
    erc_errors_by_case: dict[tuple[str, str], tuple[str, ...]] = {}
    return_nets_by_case: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native power-path fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            erc_path = output / f"{case}.{run}.erc.json"
            if not erc_path.is_file():
                raise ValueError(f"Native power-path fixture omitted {erc_path.name}")
            raw_erc_hashes[(case, run)] = digest(erc_path)
            erc_report = read_kicad_erc_report(erc_path)
            if erc_report.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native {case} ERC report version differs from KiCad {config.kicad_version}"
                )
            erc_rows = [
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted(
                            [(detail.description, detail.x, detail.y) for detail in item.items],
                            key=lambda detail: json.dumps(
                                detail,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            ),
                        )
                    ),
                )
                for item in erc_report.violations
            ]
            erc_rows.sort(
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc_report.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[(case, run)] = hashlib.sha256(normalized_erc).hexdigest()
            erc_errors = tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "error")
            )
            erc_errors_by_case[(case, run)] = erc_errors
            if erc_errors:
                raise ValueError(
                    f"Native power-path {case} has unexpected ERC errors: {erc_errors}"
                )
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            case_path_map = (
                None
                if case
                in {
                    "external-source-control",
                    "dnp-external-source-fault",
                    "alternate-source-control",
                    "both-sources-dnp-fault",
                    "diode-control",
                    "diode-reverse-fault",
                    "schottky-diode-control",
                    "bridged-jumper-control",
                    "open-jumper-fault",
                    "bridged-three-pin12-control",
                    "bridged-three-pin123-control",
                    "bridged-three-pin12-unbridged-terminal-fault",
                }
                else path_map
            )
            mismatches = (
                power_path_mismatches(case_path_map, observed) if case_path_map is not None else ()
            )
            observed_return_names = validate_power_path_fixture_netlist(case, observed, mismatches)
            return_nets_by_case[(case, run)] = observed_return_names
            mismatches_by_case[(case, run)] = mismatches
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-power-path-{case}",
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            unmapped_reports[(case, run)] = evaluate(
                f"synthetic-power-path-{case}",
                coach,
                DesignLintPolicy(),
            )
            reports[(case, run)] = evaluate(
                f"synthetic-power-path-{case}",
                coach,
                DesignLintPolicy(power_path_map=case_path_map),
            )

    fitted_external = read_netlist(output / "external-source-control.first.netlist.xml")
    dnp_external = read_netlist(output / "dnp-external-source-fault.first.netlist.xml")
    normalized_dnp = dnp_external.model_copy(
        update={"dnp_components": fitted_external.dnp_components}
    )
    if normalized_dnp != fitted_external:
        raise ValueError("External-source fitted and DNP fixtures differ beyond population state")
    alternate_fitted = read_netlist(output / "alternate-source-control.first.netlist.xml")
    alternate_both_dnp = read_netlist(output / "both-sources-dnp-fault.first.netlist.xml")
    normalized_alternate_dnp = alternate_both_dnp.model_copy(
        update={"dnp_components": alternate_fitted.dnp_components}
    )
    if normalized_alternate_dnp != alternate_fitted:
        raise ValueError("Alternate-source fixtures differ beyond source population state")

    for case in cases:
        unmapped = unmapped_reports[(case, "first")]
        heuristic_findings = tuple(
            item
            for item in unmapped.findings
            if item.rule_id == "power.input_without_supported_source_path"
        )
        expected_heuristic_faults = {
            "fault",
            "custom-capacitor-fault",
            "dnp-external-source-fault",
            "both-sources-dnp-fault",
            "diode-reverse-fault",
            "open-jumper-fault",
            "bridged-three-pin12-unbridged-terminal-fault",
        }
        expected_ids = (
            ("power.input_without_supported_source_path",)
            if case in expected_heuristic_faults
            else ()
        )
        if tuple(item.rule_id for item in heuristic_findings) != expected_ids:
            raise ValueError(
                f"Native power-path {case} has unexpected no-map source-path findings: "
                f"{heuristic_findings}"
            )
        other_unmapped = tuple(
            item
            for item in unmapped.findings
            if item.rule_id != "power.input_without_supported_source_path"
        )
        expected_other_unmapped = (
            (
                (
                    "power.ic_rail_without_fitted_capacitor",
                    "VLOAD: IC supply decoupling review",
                ),
            )
            if case == "opaque-capacitor-fault"
            else ()
        )
        observed_other_unmapped = tuple((item.rule_id, item.subject) for item in other_unmapped)
        if observed_other_unmapped != expected_other_unmapped:
            raise ValueError(
                f"Native power-path {case} has unexpected other no-map lint findings: "
                f"{observed_other_unmapped}"
            )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native power-path exports differ after normalization to parsed netlist contracts"
        )
    if any(
        normalized_erc_hashes[(case, "first")] != normalized_erc_hashes[(case, "repeat")]
        for case in cases
    ):
        raise ValueError("Native power-path ERC reports differ after normalization")
    if any(
        erc_errors_by_case[(case, "first")] != erc_errors_by_case[(case, "repeat")]
        for case in cases
    ):
        raise ValueError("Native power-path ERC error signatures differ across repeated runs")
    if erc_errors_by_case[("control", "first")] != erc_errors_by_case[("fault", "first")]:
        raise ValueError(
            "Native ERC distinguishes the mapped path control from its wrong-rail fault"
        )
    if any(
        mismatches_by_case[("fault", run)] != mismatches_by_case[("fault", "first")]
        for run in ("first", "repeat")
    ):
        raise ValueError("Native power-path fault mismatches differ across repeated exports")

    for case in cases:
        report = reports[(case, "first")]
        rule_findings = tuple(
            item for item in report.findings if item.rule_id == "power.mapped_series_path_mismatch"
        )
        expected_mapped_faults = {"fault", "custom-capacitor-fault", "opaque-capacitor-fault"}
        if (case not in expected_mapped_faults and rule_findings) or (
            case in expected_mapped_faults and not rule_findings
        ):
            raise ValueError(f"Native power-path {case} produced unexpected lint findings")
        log.event(
            f"power-path-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            source_population=(
                "BOTH_DNP"
                if case == "both-sources-dnp-fault"
                else "J1_DNP_J2_FITTED"
                if case == "alternate-source-control"
                else "DNP"
                if case == "dnp-external-source-fault"
                else "FITTED"
                if case == "external-source-control"
                else "not_applicable"
            ),
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            erc_sha256=raw_erc_hashes[(case, "first")],
            repeat_erc_sha256=raw_erc_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            normalized_erc_sha256=normalized_erc_hashes[(case, "first")],
            repeat_normalized_erc_sha256=normalized_erc_hashes[(case, "repeat")],
            lint_status=report.status,
            power_path_findings=";".join(item.subject for item in rule_findings) or "none",
            power_path_details=";".join(
                issue
                for mismatch in mismatches_by_case[(case, "first")]
                for issue in mismatch.issues
            )
            or "none",
            other_findings=";".join(
                f"{item.rule_id}:{item.subject}"
                for item in report.findings
                if item.rule_id != "power.mapped_series_path_mismatch"
            )
            or "none",
            return_nets=";".join(return_nets_by_case[(case, "first")]) or "none",
            unmapped_lint_status=unmapped_reports[(case, "first")].status,
            unmapped_power_input_findings=";".join(
                f"{item.rule_id}:{item.subject}"
                for item in unmapped_reports[(case, "first")].findings
                if item.rule_id == "power.input_without_supported_source_path"
            )
            or "none",
            unmapped_other_findings=";".join(
                f"{item.rule_id}:{item.subject}"
                for item in unmapped_reports[(case, "first")].findings
                if item.rule_id != "power.input_without_supported_source_path"
            )
            or "none",
            erc_error_types=";".join(erc_errors_by_case[(case, "first")]) or "none",
            erc_violation_types=";".join(
                sorted(
                    {
                        item.type
                        for item in read_kicad_erc_report(
                            output / f"{case}.first.erc.json"
                        ).violations
                    }
                )
            )
            or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract_and_erc",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    log.event(
        "power-path-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    if any(
        digest(fixture_root / filename) != source_hashes[case]
        or digest(inputs / f"{case}.kicad_sch") != source_hashes[case]
        for case, filename in cases.items()
    ):
        raise ValueError("Synthetic power-path fixture source changed during native export")
