"""Digest-pinned native fixtures for serial TX/RX label-direction review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_serial_same_net import SERIAL_TX_RX_NATIVE_TOOLCHAINS
from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

SERIAL_TX_RX_LABEL_TOOLCHAINS = SERIAL_TX_RX_NATIVE_TOOLCHAINS
_RULE_ID = "bus.serial_tx_rx_label_mismatch"
_NAMED_RAIL_RULE_ID = "bus.serial_signal_on_named_rail"
_SOURCE_HASHES = {
    "fault": "f48b576254795b7343c145478bf7e44380a7f1555def2c652d40570fa3c181f9",
    "control": "912e346b5e745d60595eaae0715ccf9bc380bac34dd1ed047631ec4ea03b29d0",
    "rail_fault": "425102fe01e6cf6ab102f5d52bffdec315a124612d1256c429995b057cf68626",
}


def serial_tx_rx_label_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports for crossed labels, a named-rail fault, and control."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in SERIAL_TX_RX_LABEL_TOOLCHAINS:
        raise ValueError(
            f"Serial TX/RX label fixtures do not cover KiCad {version} with this image"
        )
    pinned = pinned_image(image)
    fixture_root = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/design_lint/serial-tx-rx-label-mismatch"
    )
    sources = {
        "fault": fixture_root / "crossed-labels.kicad_sch",
        "control": fixture_root / "matching-labels-control.kicad_sch",
        "rail_fault": fixture_root / "tx-on-ground.kicad_sch",
    }
    source_hashes = {case: digest(source) for case, source in sources.items()}
    if source_hashes != _SOURCE_HASHES:
        raise ValueError("Serial TX/RX label sources differ from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"serial-tx-rx-label-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    output = scratch / "output"
    output.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{version}"\n'
        "for case in fault control rail_fault; do\n"
        "  for run in first repeat; do\n"
        '    kicad-cli sch export netlist --format kicadxml --output "/output/$case.$run.netlist.xml" '
        '"/fixtures/$case.kicad_sch"\n'
        '    kicad-cli sch erc --format json --severity-all --output "/output/$case.$run.erc.json" '
        '"/fixtures/$case.kicad_sch"\n'
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
        "HOME=/tmp/kicad-serial-tx-rx-label-mismatch",
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
        "serial-tx-rx-label-fixture/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(
            f"Native serial TX/RX label export failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    label_subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    rail_subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    lint_statuses: dict[tuple[str, str], str] = {}
    for case, source in sources.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted serial TX/RX label {case} evidence")
            observed = read_netlist(netlist_path)
            if observed.component_pin_numbers.get("U1") != ("1", "2"):
                raise ValueError(f"Native serial TX/RX label {case} lost pin inventory")
            expected_nets = {
                "fault": {"USART1_TX": ("U1.2",), "USART1_RX": ("U1.1",)},
                "control": {"USART1_RX": ("U1.2",), "USART1_TX": ("U1.1",)},
                "rail_fault": {"GND": ("U1.1",), "USART1_RX": ("U1.2",)},
            }[case]
            if any(observed.nets.get(net) != pins for net, pins in expected_nets.items()):
                actual_nets = {net: observed.nets.get(net) for net in expected_nets}
                raise ValueError(
                    f"Native serial TX/RX label {case} assignments changed: "
                    f"expected={expected_nets!r}, actual={actual_nets!r}"
                )
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version or any(
                item.severity == "error" for item in erc.violations
            ):
                raise ValueError(f"Native ERC reported errors for serial TX/RX label {case}")
            project_id = f"synthetic-serial-tx-rx-label-{case}"
            report = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=digest(netlist_path),
                ),
                DesignLintPolicy(),
            )
            label_subjects[(case, run)] = tuple(
                item.subject for item in report.findings if item.rule_id == _RULE_ID
            )
            rail_subjects[(case, run)] = tuple(
                item.subject for item in report.findings if item.rule_id == _NAMED_RAIL_RULE_ID
            )
            lint_statuses[(case, run)] = report.status

    expected_label_subjects = {
        "fault": ("U1.1: USART1_TX on USART1_RX", "U1.2: USART1_RX on USART1_TX"),
        "control": (),
        "rail_fault": (),
    }
    expected_rail_subjects = {
        "fault": (),
        "control": (),
        "rail_fault": ("U1.1: USART1_TX on return-like net GND",),
    }
    for case in sources:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native serial TX/RX label {case} exports are not repeatable")
        if (
            label_subjects[(case, "first")] != expected_label_subjects[case]
            or label_subjects[(case, "repeat")] != label_subjects[(case, "first")]
            or rail_subjects[(case, "first")] != expected_rail_subjects[case]
            or rail_subjects[(case, "repeat")] != rail_subjects[(case, "first")]
        ):
            raise ValueError(f"Native serial TX/RX label {case} findings do not match the fixture")
        log.event(
            f"serial-tx-rx-label-fixture/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            erc_errors="none",
            repeatable="true",
            subjects=";".join(label_subjects[(case, "first")]) or "none",
            rail_subjects=";".join(rail_subjects[(case, "first")]) or "none",
            lint_status=lint_statuses[(case, "first")],
        )
    log.event(
        "serial-tx-rx-label-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
