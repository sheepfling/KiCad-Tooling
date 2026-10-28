"""Exact-version native fixtures for open UART/USART function pins."""

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
    FixtureSourceEvidence,
    NativeNetlistFixtureEvidence,
    NativeNetlistRunEvidence,
    NativeRun,
    NativeRunPair,
)
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_finding_models import DesignLintRuleOverride
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist

_FIXTURE_CASES: tuple[FaultControlFixtureCase, ...] = ("control", "fault")


def serial_unconnected_pin_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify a native open-TX fault and connected control on pinned KiCad."""
    rule_id = "bus.serial_unconnected_pin"
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Serial unconnected-pin fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)

    repository = tooling_checkout_root()
    fixture_root = repository / "tests/fixtures/design_lint/serial-peer-native"
    fixtures: dict[FaultControlFixtureCase, Path] = {
        "control": fixture_root / "endpoints.kicad_sch",
        "fault": fixture_root / "unconnected-tx.kicad_sch",
    }
    source_hashes: dict[FaultControlFixtureCase, str] = {
        case: digest(path) for case, path in fixtures.items()
    }
    scratch = Path(
        tempfile.mkdtemp(prefix=f"serial-unconnected-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, path in fixtures.items():
        shutil.copyfile(path, inputs / path.name)
        if digest(inputs / path.name) != source_hashes[case]:
            raise ValueError("Synthetic serial fixture changed while preparing native input")
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
        "for fixture in endpoints unconnected-tx; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${fixture}.${run}.netlist.xml" '
        '      "/fixtures/${fixture}.kicad_sch"\n'
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
        "HOME=/tmp/kicad-serial-unconnected-fixtures",
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
        "serial-unconnected-pin-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "serial-unconnected-pin-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native serial unconnected-pin export failed: {command.stderr or command.error}"
        )

    fixture_evidence: dict[FaultControlFixtureCase, NativeNetlistFixtureEvidence] = {}

    def load_netlist_run(
        case: FaultControlFixtureCase, source: Path, run: NativeRun
    ) -> NativeNetlistRunEvidence:
        path = output / f"{source.stem}.{run}.netlist.xml"
        if not path.is_file():
            raise ValueError(f"Native serial fixture omitted {path.name}")
        contract = read_netlist(path)
        normalized = json.dumps(
            contract.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return NativeNetlistRunEvidence(
            contract=contract,
            netlist_sha256=digest(path),
            normalized_sha256=hashlib.sha256(normalized).hexdigest(),
        )

    for case, source in fixtures.items():
        if (
            digest(source) != source_hashes[case]
            or digest(inputs / source.name) != source_hashes[case]
        ):
            raise ValueError(f"Synthetic serial {case} source changed during native export")
        fixture_evidence[case] = NativeNetlistFixtureEvidence(
            source=FixtureSourceEvidence(path=source, sha256=source_hashes[case]),
            netlists=NativeRunPair(
                first=load_netlist_run(case, source, "first"),
                repeat=load_netlist_run(case, source, "repeat"),
            ),
        )
        netlists = fixture_evidence[case].netlists
        if netlists.first.normalized_sha256 != netlists.repeat.normalized_sha256:
            raise ValueError(
                f"Native serial {case} exports differ after typed-netlist normalization"
            )

    expected_functions = {
        f"J{reference}.{pin}": function
        for reference in range(1, 5)
        for pin, function in ((1, "TX"), (2, "RX"))
    }
    expected_nets = {
        "SERIAL_A_TX": {"J1.1", "J2.2"},
        "SERIAL_A_RX": {"J1.2", "J2.1"},
        "SERIAL_B_TX": {"J3.1", "J4.2"},
        "SERIAL_B_RX": {"J3.2", "J4.1"},
    }
    control = fixture_evidence["control"].netlists.first.contract
    fault = fixture_evidence["fault"].netlists.first.contract
    for case, observed in zip(_FIXTURE_CASES, (control, fault), strict=True):
        if observed.pin_functions != expected_functions:
            raise ValueError(
                f"Native serial {case} function inventory changed: {observed.pin_functions}"
            )
        if observed.component_pin_numbers != {
            f"J{reference}": ("1", "2") for reference in range(1, 5)
        }:
            raise ValueError(f"Native serial {case} connector pin inventory changed")
        if observed.component_symbols != {
            f"J{reference}": "Synthetic:UART_Endpoint" for reference in range(1, 5)
        }:
            raise ValueError(f"Native serial {case} connector identities changed")
    actual_control_nets = {
        net: set(pins) for net, pins in control.nets.items() if net.startswith("SERIAL_")
    }
    if actual_control_nets != expected_nets:
        raise ValueError(f"Native serial control assignments changed: {actual_control_nets}")
    actual_fault_nets = {
        net: set(pins) for net, pins in fault.nets.items() if net.startswith("SERIAL_")
    }
    expected_fault_nets = {**expected_nets, "SERIAL_B_TX": {"J4.2"}}
    if actual_fault_nets != expected_fault_nets:
        raise ValueError(f"Native serial fault changed more than J3.1: {actual_fault_nets}")

    default_report = evaluate(
        "synthetic-serial-unconnected-tx",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-serial-unconnected-tx",
            observed=fault,
            netlist_sha256=fixture_evidence["fault"].netlists.first.netlist_sha256,
        ),
        DesignLintPolicy(),
    )
    default_findings = [item for item in default_report.findings if item.rule_id == rule_id]
    if (
        len(default_findings) != 1
        or default_findings[0].subject != "J3.1: TX"
        or default_findings[0].mode != "off"
        or default_findings[0].disposition != "RULE_OFF"
    ):
        raise ValueError("Native serial fault no longer emits one default-off J3.1 candidate")

    review_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=rule_id,
                mode="review",
                reason="Exercise the synthetic native open-TX review candidate.",
            ),
        )
    )

    def review_report_for(run: NativeRun) -> DesignLintReport:
        return evaluate(
            "synthetic-serial-unconnected-tx",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-serial-unconnected-tx",
                observed=fixture_evidence["fault"].netlists.for_run(run).contract,
                netlist_sha256=(fixture_evidence["fault"].netlists.for_run(run).netlist_sha256),
            ),
            review_policy,
        )

    review_reports = NativeRunPair(
        first=review_report_for("first"),
        repeat=review_report_for("repeat"),
    )
    review_report, repeated_report = review_reports.first, review_reports.repeat
    review_findings = [item for item in review_report.findings if item.rule_id == rule_id]
    repeated_findings = [item for item in repeated_report.findings if item.rule_id == rule_id]
    if (
        len(review_findings) != 1
        or len(repeated_findings) != 1
        or review_findings[0].subject != "J3.1: TX"
        or review_findings[0].mode != "review"
        or review_findings[0].disposition != "OPEN"
        or review_findings[0].fingerprint != repeated_findings[0].fingerprint
        or review_findings[0].evidence != repeated_findings[0].evidence
    ):
        raise ValueError("Native serial review candidate changed on repeated export")

    control_report = evaluate(
        "synthetic-serial-unconnected-control",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-serial-unconnected-control",
            observed=control,
            netlist_sha256=fixture_evidence["control"].netlists.first.netlist_sha256,
        ),
        review_policy,
    )
    if any(item.rule_id == rule_id for item in control_report.findings):
        raise ValueError("Connected native serial control unexpectedly emitted an open-pin prompt")

    receipt = (scratch / "native.command.json").relative_to(root).as_posix()
    for case in _FIXTURE_CASES:
        log.event(
            f"serial-unconnected-pin-fixture/{case}",
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
            command_receipt=receipt,
            **(
                {
                    "rule_findings": "none",
                    "review_mode": "review",
                }
                if case == "control"
                else {
                    "default_mode": default_findings[0].mode,
                    "default_disposition": default_findings[0].disposition,
                    "review_mode": review_findings[0].mode,
                    "review_disposition": review_findings[0].disposition,
                    "findings": ";".join(item.subject for item in review_findings),
                    "evidence": ";".join(
                        f"{key}={'|'.join(value)}"
                        for key, value in sorted(review_findings[0].evidence.items())
                    ),
                }
            ),
        )

    log.event(
        "serial-unconnected-pin-fixture/native-export",
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
        repeatability_basis="normalized_native_netlist_contract",
        command_receipt=receipt,
    )
