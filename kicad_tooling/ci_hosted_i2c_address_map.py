"""Digest-pinned KiCad source exports for mapped I2C address review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from .ci_hosted_i2c_native import I2C_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.i2c_address_models import I2cAddressMap
from .hwrepo.models import DesignLintPolicy
from .hwrepo.native_report_parsing import read_netlist
from .hwrepo.netlist_contract_models import NetlistContract

COLLISION_RULE_ID = "bus.i2c_address_collision"
MISMATCH_RULE_ID = "bus.i2c_address_mismatch"
UNMAPPED_RESPONDER_RULE_ID = "bus.i2c_unmapped_responder"
_CASES = ("control", "fault")
_SOURCE_HASHES = {
    "control": "109b7699426f756fbf1b592e2950547b8fbbb145e338e2accbd52841d8bcbb1f",
    "fault": "f9bfcd74c809e5b7956584162d43c12bae8fa5a98cf827480138c5beb2ff861e",
}


def _expected_nets(case: str) -> dict[str, set[str]]:
    address_pins = (
        {"GND": {"U1.3"}, "+3V3": {"U2.3"}} if case == "control" else {"GND": {"U1.3", "U2.3"}}
    )
    return {
        "MAIN_SDA": {"U1.1", "U2.1"},
        "MAIN_SCL": {"U1.2", "U2.2"},
        **address_pins,
    }


def _check_native_netlist(case: str, observed: NetlistContract) -> None:
    expected_pins = {"U1": ("1", "2", "3"), "U2": ("1", "2", "3")}
    expected_symbols = {"U1": "Synthetic:EEPROM", "U2": "Synthetic:EEPROM"}
    expected_functions = {
        "U1.1": "SDA",
        "U1.2": "SCL",
        "U1.3": "A0",
        "U2.1": "SDA",
        "U2.2": "SCL",
        "U2.3": "A0",
    }
    if set(observed.components) != {"U1", "U2"}:
        raise ValueError(f"Native I2C {case} component inventory changed")
    if dict(observed.component_symbols) != expected_symbols:
        raise ValueError(f"Native I2C {case} symbol identity changed")
    if dict(observed.component_pin_numbers) != expected_pins:
        raise ValueError(f"Native I2C {case} pin inventory changed")
    if dict(observed.pin_functions) != expected_functions:
        raise ValueError(f"Native I2C {case} pin functions changed")
    if {name: set(pins) for name, pins in observed.nets.items()} != _expected_nets(case):
        raise ValueError(f"Native I2C {case} segment or strap assignments changed")
    if observed.dnp_components:
        raise ValueError(f"Native I2C {case} unexpectedly marks a responder DNP")


def i2c_address_map_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
    specifications: Mapping[str, I2cAddressMap],
    mismatch_specifications: Mapping[str, I2cAddressMap],
    unmapped_specification: I2cAddressMap,
) -> None:
    """Export sources twice and evaluate collision, mismatch, and map coverage."""
    if (version, image) not in I2C_NATIVE_TOOLCHAINS:
        raise ValueError(f"I2C address fixtures do not cover KiCad {version} with this image")
    if set(specifications) != set(_CASES):
        raise ValueError("I2C address fixtures require one map for each fault/control source")
    if set(mismatch_specifications) != set(_CASES):
        raise ValueError("I2C mismatch fixtures require fault and corrected control maps")
    unmapped_references = {
        responder.reference
        for segment in unmapped_specification.segments
        for responder in segment.responders
    }
    if unmapped_references != {"U1"}:
        raise ValueError("I2C unmapped-responder fixture must omit only fitted U2")

    root = root.resolve()
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint/i2c-address-map-native"
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in _CASES}
    source_hashes = {case: digest(path) for case, path in sources.items()}
    if source_hashes != _SOURCE_HASHES:
        raise ValueError("I2C address fixture sources differ from their reviewed hashes")

    scratch = Path(tempfile.mkdtemp(prefix=f"i2c-address-{version}-", dir=log.directory.resolve()))
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        target = inputs / source.name
        shutil.copyfile(source, target)
        if digest(target) != source_hashes[case]:
            raise ValueError(f"Synthetic I2C {case} source changed during native staging")
    output = scratch / "output"
    output.mkdir()

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{version}"\n'
        "for case in control fault; do\n"
        "  for run in first repeat; do\n"
        '    kicad-cli sch export netlist --format kicadxml --output "/output/${case}.${run}.netlist.xml" '
        '"/fixtures/${case}.kicad_sch"\n'
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
        "HOME=/tmp/kicad-i2c-address-map",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned_image(image),
        "-ec",
        script,
    )
    log.event(
        "i2c-address-map/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=image,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    receipt_path = receipt.relative_to(root).as_posix()
    if command.returncode != 0 or command.error is not None:
        error = command.stderr or command.error or f"exit {command.returncode}"
        log.event(
            "i2c-address-map/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=image,
            command_receipt=receipt_path,
            error=error,
        )
        raise ValueError(f"Native I2C address-map export failed: {error}")

    case_results: dict[str, tuple[str, str, str]] = {}
    control_netlist: NetlistContract | None = None
    control_raw_netlist_sha256: str | None = None
    for case in _CASES:
        if digest(sources[case]) != source_hashes[case]:
            raise ValueError(f"Synthetic I2C {case} source changed during native export")
        run_hashes: list[str] = []
        raw_hashes: list[str] = []
        observed: NetlistContract | None = None
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native KiCad omitted I2C {case} source evidence")
            current = read_netlist(netlist_path)
            _check_native_netlist(case, current)
            normalized = json.dumps(
                current.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            run_hashes.append(hashlib.sha256(normalized).hexdigest())
            raw_hashes.append(digest(netlist_path))
            observed = current
        if run_hashes[0] != run_hashes[1]:
            raise ValueError(f"Native I2C {case} netlist did not repeat identically")
        assert observed is not None

        project_id = f"synthetic-i2c-address-{case}"
        report = evaluate(
            project_id,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[0],
            ),
            DesignLintPolicy(i2c_address_map=specifications[case]),
        )
        if report.i2c_address_coverage.status != "COMPLETE":
            raise ValueError(f"Native I2C {case} address map is not complete")
        findings = tuple(item for item in report.findings if item.rule_id == COLLISION_RULE_ID)
        expected_subjects = ("MAIN: U1, U2 at 0x50",) if case == "fault" else ()
        if tuple(item.subject for item in findings) != expected_subjects:
            raise ValueError(f"Native I2C {case} rule evidence changed")
        if case == "fault" and (len(findings) != 1 or findings[0].mode != "review"):
            raise ValueError("Native I2C address collision no longer defaults to review")
        case_results[case] = (run_hashes[0], raw_hashes[0], report.status)

        log.event(
            f"i2c-address-map/collision/{case}",
            "PASS",
            project=project_id,
            kicad_version=version,
            image=pinned_image(image),
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=run_hashes[0],
            repeat_normalized_netlist_sha256=run_hashes[1],
            findings=";".join(item.subject for item in findings) or "none",
            address_coverage=report.i2c_address_coverage.status,
            repeatable="true",
            command_receipt=receipt_path,
        )
        if case == "control":
            control_netlist = observed
            control_raw_netlist_sha256 = raw_hashes[0]

    if control_netlist is None or control_raw_netlist_sha256 is None:
        raise ValueError("Native I2C address-map control evidence was not retained")

    for case in _CASES:
        project_id = f"synthetic-i2c-address-mismatch-{case}"
        report = evaluate(
            project_id,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=control_netlist,
                netlist_sha256=control_raw_netlist_sha256,
            ),
            DesignLintPolicy(i2c_address_map=mismatch_specifications[case]),
        )
        if report.i2c_address_coverage.status != "COMPLETE":
            raise ValueError(f"Native I2C mismatch {case} map is not complete")
        mismatch_findings = tuple(
            item for item in report.findings if item.rule_id == MISMATCH_RULE_ID
        )
        expected_subjects = ("U2 on MAIN: 0x51",) if case == "fault" else ()
        if tuple(item.subject for item in mismatch_findings) != expected_subjects:
            raise ValueError(f"Native I2C address-mismatch {case} evidence changed")
        if case == "fault" and (
            len(mismatch_findings) != 1 or mismatch_findings[0].mode != "review"
        ):
            raise ValueError("Native I2C address mismatch no longer defaults to review")
        if any(item.rule_id == COLLISION_RULE_ID for item in report.findings):
            raise ValueError("Native I2C address mismatch unexpectedly creates a collision")
        log.event(
            f"i2c-address-map/strap-mismatch/{case}",
            "PASS",
            project=project_id,
            kicad_version=version,
            image=pinned_image(image),
            source_sha256=source_hashes["control"],
            raw_netlist_sha256=control_raw_netlist_sha256,
            normalized_netlist_sha256=case_results["control"][0],
            findings=";".join(item.subject for item in mismatch_findings) or "none",
            address_coverage=report.i2c_address_coverage.status,
            repeatable="true",
            command_receipt=receipt_path,
        )

    unmapped_project = "synthetic-i2c-address-unmapped-responder-fault"
    unmapped_report = evaluate(
        unmapped_project,
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=unmapped_project,
            observed=control_netlist,
            netlist_sha256=control_raw_netlist_sha256,
        ),
        DesignLintPolicy(i2c_address_map=unmapped_specification),
    )
    if unmapped_report.i2c_address_coverage.status != "COMPLETE":
        raise ValueError("Native I2C unmapped-responder map lost its mapped U1 coverage")
    unmapped_findings = tuple(
        item for item in unmapped_report.findings if item.rule_id == UNMAPPED_RESPONDER_RULE_ID
    )
    if (
        len(unmapped_findings) != 1
        or unmapped_findings[0].subject != "U2: I2C address-map coverage"
        or unmapped_findings[0].mode != "review"
        or unmapped_findings[0].evidence["assigned_net_pairs"] != ("MAIN_SDA / MAIN_SCL",)
    ):
        raise ValueError("Native I2C map omission no longer reviews only the unlisted U2")
    if any(
        item.rule_id in {COLLISION_RULE_ID, MISMATCH_RULE_ID} for item in unmapped_report.findings
    ):
        raise ValueError("Native I2C unmapped-responder fault unexpectedly reports address errors")
    mapped_control_project = "synthetic-i2c-address-unmapped-responder-control"
    mapped_control_report = evaluate(
        mapped_control_project,
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=mapped_control_project,
            observed=control_netlist,
            netlist_sha256=control_raw_netlist_sha256,
        ),
        DesignLintPolicy(i2c_address_map=mismatch_specifications["control"]),
    )
    if mapped_control_report.i2c_address_coverage.status != "COMPLETE":
        raise ValueError("Native I2C unmapped-responder control map is not complete")
    if any(item.rule_id == UNMAPPED_RESPONDER_RULE_ID for item in mapped_control_report.findings):
        raise ValueError("Native I2C complete map unexpectedly reports an unmapped responder")
    for case, report, findings in (
        ("fault", unmapped_report, unmapped_findings),
        ("control", mapped_control_report, ()),
    ):
        log.event(
            f"i2c-address-map/unmapped-responder/{case}",
            "PASS",
            project=f"synthetic-i2c-address-unmapped-responder-{case}",
            kicad_version=version,
            image=pinned_image(image),
            source_sha256=source_hashes["control"],
            raw_netlist_sha256=control_raw_netlist_sha256,
            normalized_netlist_sha256=case_results["control"][0],
            findings=";".join(item.subject for item in findings) or "none",
            overall_lint_status=report.status,
            address_coverage=report.i2c_address_coverage.status,
            repeatable="true",
            command_receipt=receipt_path,
        )

    log.event(
        "i2c-address-map/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned_image(image),
        control_source_sha256=source_hashes["control"],
        fault_source_sha256=source_hashes["fault"],
        control_normalized_netlist_sha256=case_results["control"][0],
        fault_normalized_netlist_sha256=case_results["fault"][0],
        repeatable="true",
        repeatability_basis="source_hash_and_native_netlist_contract",
        command_receipt=receipt_path,
    )
