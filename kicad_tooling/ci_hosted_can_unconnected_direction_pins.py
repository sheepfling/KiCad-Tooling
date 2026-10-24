"""Exact-version native fixtures for partially open CAN/FDCAN TX/RX pairs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


def can_unconnected_direction_pin_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify a native open-direction fault against a connected control."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.design_lint_finding_models import DesignLintRuleOverride
    from .hwrepo.design_lint_report_models import DesignLintReport
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract
    from .validate import read_netlist

    rule_id = "bus.can_unconnected_direction_pin"
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"CAN unconnected-direction fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)

    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/can-unconnected-direction-native"
    fixtures = {
        "control": fixture_root / "control.kicad_sch",
        "fault": fixture_root / "open-tx.kicad_sch",
    }
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"can-unconnected-direction-{project}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, path in fixtures.items():
        shutil.copyfile(path, inputs / path.name)
        if digest(inputs / path.name) != source_hashes[case]:
            raise ValueError("Synthetic CAN direction fixture changed while preparing native input")
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
        "for fixture in control open-tx; do\n"
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
        "HOME=/tmp/kicad-can-unconnected-direction-fixtures",
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
        "can-unconnected-direction-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "can-unconnected-direction-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native CAN unconnected-direction export failed: {command.stderr or command.error}"
        )

    contracts: dict[str, dict[str, NetlistContract]] = {"control": {}, "fault": {}}
    netlist_hashes: dict[str, dict[str, str]] = {"control": {}, "fault": {}}
    normalized_hashes: dict[str, dict[str, str]] = {"control": {}, "fault": {}}
    for case, source in fixtures.items():
        if (
            digest(source) != source_hashes[case]
            or digest(inputs / source.name) != source_hashes[case]
        ):
            raise ValueError(f"Synthetic CAN direction {case} source changed during native export")
        for run in ("first", "repeat"):
            path = output / f"{source.stem}.{run}.netlist.xml"
            if not path.is_file():
                raise ValueError(f"Native CAN direction fixture omitted {path.name}")
            netlist_hashes[case][run] = digest(path)
            contract = read_netlist(path)
            contracts[case][run] = contract
            normalized = json.dumps(
                contract.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[case][run] = hashlib.sha256(normalized).hexdigest()
        if normalized_hashes[case]["first"] != normalized_hashes[case]["repeat"]:
            raise ValueError(f"Native CAN direction {case} exports differ after normalization")

    expected_functions = {
        "U1.1": "CAN1_TX",
        "U1.2": "CAN1_RX",
        "U2.1": "CAN1_TX",
        "U2.2": "CAN1_RX",
    }
    expected_pin_numbers = {"U1": ("1", "2"), "U2": ("1", "2")}
    expected_symbols = {"U1": "Synthetic:CanController", "U2": "Synthetic:CanController"}
    expected_control_nets = {
        "CAN_TX_SHARED": {"U1.1", "U2.1"},
        "CAN1_RX": {"U1.2"},
        "CAN2_RX": {"U2.2"},
    }
    expected_fault_nets = {
        "CAN_TX_SHARED": {"U2.1"},
        "CAN1_RX": {"U1.2"},
        "CAN2_RX": {"U2.2"},
    }
    control = contracts["control"]["first"]
    fault = contracts["fault"]["first"]
    for case, observed in (("control", control), ("fault", fault)):
        if observed.pin_functions != expected_functions:
            raise ValueError(
                f"Native CAN direction {case} functions changed: {observed.pin_functions}"
            )
        if observed.component_pin_numbers != expected_pin_numbers:
            raise ValueError(f"Native CAN direction {case} pin inventory changed")
        if observed.component_symbols != expected_symbols:
            raise ValueError(f"Native CAN direction {case} component identities changed")
    actual_control_nets = {
        net: set(pins) for net, pins in control.nets.items() if net in expected_control_nets
    }
    if actual_control_nets != expected_control_nets:
        raise ValueError(f"Native CAN direction control assignments changed: {actual_control_nets}")
    actual_fault_nets = {
        net: set(pins) for net, pins in fault.nets.items() if net in expected_fault_nets
    }
    if actual_fault_nets != expected_fault_nets:
        raise ValueError(f"Native CAN direction fault changed more than U1.1: {actual_fault_nets}")

    def report(
        observed: NetlistContract, case: str, run: str, policy: DesignLintPolicy
    ) -> DesignLintReport:
        return evaluate(
            f"synthetic-can-direction-{case}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-can-direction-{case}",
                observed=observed,
                netlist_sha256=netlist_hashes[case][run],
            ),
            policy,
        )

    control_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=rule_id,
                mode="review",
                reason="Exercise the synthetic native connected CAN direction control.",
            ),
        )
    )
    control_report = report(control, "control", "first", control_policy)
    control_findings = [item for item in control_report.findings if item.rule_id == rule_id]
    if control_findings:
        raise ValueError("Native CAN direction connected control unexpectedly emitted a finding")

    default_findings = [
        item
        for item in report(fault, "fault", "first", DesignLintPolicy()).findings
        if item.rule_id == rule_id
    ]
    if (
        len(default_findings) != 1
        or default_findings[0].subject != "U1.1: CAN1_TX"
        or default_findings[0].mode != "off"
        or default_findings[0].disposition != "RULE_OFF"
    ):
        raise ValueError("Native CAN direction fault no longer emits one default-off candidate")

    review_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=rule_id,
                mode="review",
                reason="Exercise the synthetic native open CAN direction review candidate.",
            ),
        )
    )
    review_reports = [report(fault, "fault", run, review_policy) for run in ("first", "repeat")]
    review_findings = [
        [item for item in item_report.findings if item.rule_id == rule_id]
        for item_report in review_reports
    ]
    if (
        any(len(items) != 1 for items in review_findings)
        or review_findings[0][0].subject != "U1.1: CAN1_TX"
        or review_findings[0][0].disposition != "OPEN"
        or review_findings[0][0].fingerprint != review_findings[1][0].fingerprint
        or review_findings[0][0].evidence != review_findings[1][0].evidence
    ):
        raise ValueError("Native CAN direction review candidate changed on repeated export")

    review_finding = review_findings[0][0]
    for case, expected_nets, enabled_report in (
        ("control", expected_control_nets, control_report),
        ("fault", expected_fault_nets, review_reports[0]),
    ):
        log.event(
            f"can-unconnected-direction-fixture/{case}",
            "PASS",
            project=project,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=normalized_hashes[case]["repeat"],
            rule_findings=(
                ";".join(
                    item.subject for item in enabled_report.findings if item.rule_id == rule_id
                )
                or "none"
            ),
            **(
                {
                    "default_mode": default_findings[0].mode,
                    "default_disposition": default_findings[0].disposition,
                    "review_mode": review_finding.mode,
                    "review_disposition": review_finding.disposition,
                    "evidence": ",".join(
                        f"{key}={'|'.join(value)}"
                        for key, value in sorted(review_finding.evidence.items())
                    ),
                }
                if case == "fault"
                else {}
            ),
            net_count=str(len(expected_nets)),
            repeatable="true",
        )
    log.event(
        "can-unconnected-direction-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        control_source_sha256=source_hashes["control"],
        fault_source_sha256=source_hashes["fault"],
        control_normalized_netlist_sha256=normalized_hashes["control"]["first"],
        fault_normalized_netlist_sha256=normalized_hashes["fault"]["first"],
        repeatable="true",
    )
