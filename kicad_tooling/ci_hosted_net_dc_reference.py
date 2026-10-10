"""Hosted native net DC-reference fixture lane."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def net_dc_reference_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Compare the connector/capacitor-only hint with pinned exports and native ERC."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy, DesignLintReport
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"DC-reference fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/net-dc-reference"
    )
    cases = {
        "fault": ("fault.kicad_sch", True),
        "control": ("control.kicad_sch", False),
        "dnp-control": ("dnp-control.kicad_sch", False),
    }
    source_hashes = {case: digest(fixture_root / filename) for case, (filename, _) in cases.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"net-dc-reference-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, (filename, _) in cases.items():
        shutil.copyfile(fixture_root / filename, inputs / filename)
        if digest(inputs / filename) != source_hashes[case]:
            raise ValueError(f"Synthetic {case} DC-reference fixture changed during native input")
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
        "for case in fault control dnp-control; do\n"
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
        "HOME=/tmp/kicad-net-dc-reference-fixtures",
        "-v",
        f"{inputs.resolve()}:/fixtures:ro",
        "-v",
        f"{output.resolve()}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    log.event(
        "net-dc-reference-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "net-dc-reference-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native DC-reference fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        "net-dc-reference-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    netlist_hashes: dict[tuple[str, str], str] = {}
    erc_hashes: dict[tuple[str, str], str] = {}
    reports: dict[str, DesignLintReport] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    for case, (_, expected_finding) in cases.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native DC-reference {case} export omitted a required report")
            raw_netlist_sha256 = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized_netlist = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            netlist_hashes[(case, run)] = hashlib.sha256(normalized_netlist).hexdigest()
            erc_report = read_kicad_erc_report(erc_path)
            if erc_report.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native {case} ERC version differs from KiCad {config.kicad_version}"
                )
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "error")
            )
            if erc_errors[(case, run)]:
                raise ValueError(
                    f"Native DC-reference {case} has unexpected ERC errors: "
                    f"{erc_errors[(case, run)]}"
                )
            erc_rows = [
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted(
                            ((detail.description, detail.x, detail.y) for detail in item.items),
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
                key=lambda violation: json.dumps(
                    violation,
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
            erc_hashes[(case, run)] = hashlib.sha256(normalized_erc).hexdigest()
            report = evaluate(
                f"synthetic-net-dc-reference-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-net-dc-reference-{case}",
                    observed=observed,
                    netlist_sha256=raw_netlist_sha256,
                ),
                DesignLintPolicy(),
            )
            if case in {"fault", "dnp-control"}:
                net = tuple(sorted(observed.nets.get("ANALOG_IN", ())))
                if net != ("C1.1", "J1.1"):
                    raise ValueError(f"Native {case} net membership changed: {net}")
            if case == "dnp-control" and "C1" not in observed.dnp_components:
                raise ValueError("Native DNP control did not preserve C1's DNP state")
            rule_findings = tuple(
                item
                for item in report.findings
                if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
            )
            if bool(rule_findings) != expected_finding:
                raise ValueError(
                    f"Native DC-reference {case} expected finding={expected_finding}, "
                    f"observed {len(rule_findings)}"
                )
            expected_status = "REVIEW" if expected_finding else "PASS"
            if report.status != expected_status:
                raise ValueError(
                    f"Native DC-reference {case} expected {expected_status}, "
                    f"observed {report.status}"
                )
            reports[case] = report

    for case in cases:
        if netlist_hashes[(case, "first")] != netlist_hashes[(case, "repeat")]:
            raise ValueError(f"Native DC-reference {case} netlist export was not repeatable")
        if erc_hashes[(case, "first")] != erc_hashes[(case, "repeat")]:
            raise ValueError(f"Native DC-reference {case} ERC export was not repeatable")
        finding_text = (
            ";".join(
                item.subject
                for item in reports[case].findings
                if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
            )
            or "none"
        )
        log.event(
            f"net-dc-reference-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=netlist_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=netlist_hashes[(case, "repeat")],
            normalized_erc_sha256=erc_hashes[(case, "first")],
            repeat_normalized_erc_sha256=erc_hashes[(case, "repeat")],
            lint_status=reports[case].status,
            finding=finding_text,
            erc_error_types=";".join(erc_errors[(case, "first")]) or "none",
            repeatable="true",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    if any(
        digest(fixture_root / filename) != source_hashes[case]
        for case, (filename, _) in cases.items()
    ):
        raise ValueError("Synthetic DC-reference fixture source changed during native export")
