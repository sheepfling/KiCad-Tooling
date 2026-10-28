"""Pinned native acceptance for a partially assigned I2C signal pair."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_native_fixture_models import (
    FaultControlFixtureCase,
    FaultControlPair,
    FixtureSourceEvidence,
    NativeNetlistFixtureEvidence,
    NativeNetlistRunEvidence,
    NativeRun,
    NativeRunPair,
)
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_finding_models import DesignLintRuleOverride
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
)
from .validate import read_netlist

_FIXTURE_CASES: tuple[FaultControlFixtureCase, ...] = ("control", "fault")


def i2c_unconnected_pin_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Export and compare a no-connect fault and connected control on pinned KiCad."""
    rule_id = "bus.i2c_unconnected_pin"
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"I2C unconnected-pin fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint/i2c-unconnected-pin-native"
    fixtures: dict[FaultControlFixtureCase, Path] = {
        case: fixture_root / f"{case}.kicad_sch" for case in _FIXTURE_CASES
    }
    source_hashes: dict[FaultControlFixtureCase, str] = {
        case: digest(path) for case, path in fixtures.items()
    }
    expected_source_hashes = {
        "control": "05c75407c4af9fac48c8c4e2a0517e3aeed928d3c73990e3384388c38303c27e",
        "fault": "6e98c35fae5fd7484979811006c3d24a7bf100abf7ac59680a679b9b5d1ee133",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("I2C unconnected-pin fixture sources differ from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"i2c-unconnected-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for source in fixtures.values():
        shutil.copyfile(source, inputs / source.name)
        if digest(inputs / source.name) != digest(source):
            raise ValueError("Synthetic I2C source changed while preparing native input")
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
        "for case in control fault; do\n"
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
        "HOME=/tmp/kicad-i2c-unconnected-fixtures",
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
        "i2c-unconnected-pin-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "i2c-unconnected-pin-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native I2C export failed: {command.stderr or command.error}")

    fixture_evidence: dict[FaultControlFixtureCase, NativeNetlistFixtureEvidence] = {}

    def load_netlist_run(case: FaultControlFixtureCase, run: NativeRun) -> NativeNetlistRunEvidence:
        netlist_path = output / f"{case}.{run}.netlist.xml"
        erc_path = output / f"{case}.{run}.erc.json"
        if not netlist_path.is_file() or not erc_path.is_file():
            raise ValueError(f"Native I2C {case} export omitted an expected report")
        observed = read_netlist(netlist_path)
        normalized = json.dumps(
            observed.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        erc = read_kicad_erc_report(erc_path)
        if erc.kicad_version != config.kicad_version:
            raise ValueError(f"Native I2C {case} ERC report version changed")
        if any(item.severity == "error" for item in erc.violations):
            raise ValueError(f"Native I2C {case} emitted an unexpected ERC error")
        return NativeNetlistRunEvidence(
            contract=observed,
            netlist_sha256=digest(netlist_path),
            normalized_sha256=hashlib.sha256(normalized).hexdigest(),
        )

    for case in _FIXTURE_CASES:
        if digest(fixtures[case]) != source_hashes[case]:
            raise ValueError(f"Synthetic I2C {case} source changed during native export")
        fixture_evidence[case] = NativeNetlistFixtureEvidence(
            source=FixtureSourceEvidence(path=fixtures[case], sha256=source_hashes[case]),
            netlists=NativeRunPair(
                first=load_netlist_run(case, "first"),
                repeat=load_netlist_run(case, "repeat"),
            ),
        )
        netlists = fixture_evidence[case].netlists
        if netlists.first.normalized_sha256 != netlists.repeat.normalized_sha256:
            raise ValueError(f"Native I2C {case} netlist is not repeatable")

    expected_functions = {"U1.1": "SDA", "U1.2": "SCL"}
    expected_nets = FaultControlPair(
        control={"I2C_SDA": {"U1.1"}, "I2C_SCL": {"U1.2"}},
        fault={"I2C_SCL": {"U1.2"}},
    )
    for case in _FIXTURE_CASES:
        observed = fixture_evidence[case].netlists.first.contract
        if observed.pin_functions != expected_functions:
            raise ValueError(f"Native I2C {case} function inventory changed")
        if observed.component_pin_numbers != {"U1": ("1", "2")}:
            raise ValueError(f"Native I2C {case} pin inventory changed")
        actual_nets = {
            net: set(pins) for net, pins in observed.nets.items() if net.startswith("I2C_")
        }
        if actual_nets != expected_nets.for_case(case):
            raise ValueError(f"Native I2C {case} assignments changed: {actual_nets}")

    fault_observed = fixture_evidence["fault"].netlists.first.contract
    default_report = evaluate(
        "synthetic-i2c-unconnected-fault",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-i2c-unconnected-fault",
            observed=fault_observed,
            netlist_sha256=fixture_evidence["fault"].netlists.first.netlist_sha256,
        ),
        DesignLintPolicy(),
    )
    default_findings = [item for item in default_report.findings if item.rule_id == rule_id]
    if (
        len(default_findings) != 1
        or default_findings[0].subject != "U1.1: SDA"
        or default_findings[0].mode != "off"
        or default_findings[0].disposition != "RULE_OFF"
    ):
        raise ValueError("Native I2C fault no longer emits one default-off SDA candidate")

    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=rule_id,
                mode="review",
                reason="Exercise the synthetic native open-SDA review candidate.",
            ),
        )
    )
    reports = FaultControlPair(
        control=evaluate(
            "synthetic-i2c-unconnected-control",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-i2c-unconnected-control",
                observed=fixture_evidence["control"].netlists.first.contract,
                netlist_sha256=fixture_evidence["control"].netlists.first.netlist_sha256,
            ),
            policy,
        ),
        fault=evaluate(
            "synthetic-i2c-unconnected-fault",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-i2c-unconnected-fault",
                observed=fixture_evidence["fault"].netlists.first.contract,
                netlist_sha256=fixture_evidence["fault"].netlists.first.netlist_sha256,
            ),
            policy,
        ),
    )
    fault_findings = [item for item in reports.fault.findings if item.rule_id == rule_id]
    control_findings = [item for item in reports.control.findings if item.rule_id == rule_id]
    if (
        len(fault_findings) != 1
        or fault_findings[0].subject != "U1.1: SDA"
        or fault_findings[0].evidence.get("paired_pin") != ("U1.2",)
        or fault_findings[0].evidence.get("paired_net") != ("I2C_SCL",)
        or control_findings
    ):
        raise ValueError("Native I2C fault/control no longer selects the partial-pair candidate")

    receipt_path = receipt.relative_to(root).as_posix()
    for case, findings in zip(_FIXTURE_CASES, (control_findings, fault_findings), strict=True):
        log.event(
            f"i2c-unconnected-pin-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=fixture_evidence[case].source.sha256,
            normalized_netlist_sha256=fixture_evidence[case].netlists.first.normalized_sha256,
            repeat_normalized_netlist_sha256=fixture_evidence[
                case
            ].netlists.repeat.normalized_sha256,
            repeatable="true",
            findings=";".join(item.subject for item in findings) or "none",
            **(
                {
                    "default_mode": default_findings[0].mode,
                    "default_disposition": default_findings[0].disposition,
                    "review_mode": "review",
                }
                if case == "fault"
                else {"review_mode": "review"}
            ),
            command_receipt=receipt_path,
        )
    log.event(
        "i2c-unconnected-pin-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        control_source_sha256=fixture_evidence["control"].source.sha256,
        fault_source_sha256=fixture_evidence["fault"].source.sha256,
        control_normalized_netlist_sha256=(
            fixture_evidence["control"].netlists.first.normalized_sha256
        ),
        fault_normalized_netlist_sha256=(
            fixture_evidence["fault"].netlists.first.normalized_sha256
        ),
        repeatable="true",
        repeatability_basis="normalized_native_netlist_contract_and_ERC",
        command_receipt=receipt_path,
    )
