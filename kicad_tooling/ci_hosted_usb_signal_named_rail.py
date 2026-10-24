"""Digest-pinned native fixtures for USB data pins assigned to named rails."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

USB_SIGNAL_NAMED_RAIL_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
_RULE_ID = "bus.usb_signal_on_named_rail"
_SOURCE_HASHES = {
    "control": "30270e674ad045a2ebc238b6f632ed455c04f549d6c53061f74151c77d160002",
    "fault": "9330de44f6600afd92d2aa7199eced1ca6e892ed74fb5765f20a1832eef97148",
}


def usb_signal_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native netlist and ERC exports for a USB rail fault and signal control."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in USB_SIGNAL_NAMED_RAIL_TOOLCHAINS:
        raise ValueError(f"USB named-rail coverage is not configured for KiCad {version}")
    pinned = pinned_image(image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/usb-signal-named-rail"
    )
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in ("fault", "control")}
    source_hashes = {case: digest(source) for case, source in sources.items()}
    if source_hashes != _SOURCE_HASHES:
        raise ValueError("USB named-rail sources differ from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"usb-signal-named-rail-{version}-", dir=log.directory.resolve())
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
        "for case in fault control; do\n"
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
        "HOME=/tmp/kicad-usb-signal-named-rail",
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
        "usb-signal-named-rail-fixture/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(f"Native USB named-rail export failed: {command.stderr or command.error}")

    normalized_hashes: dict[tuple[str, str], str] = {}
    findings: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted USB named-rail {case} evidence")
            observed = read_netlist(netlist_path)
            expected_nets = (
                {"GND": ("U1.1",), "USB_D-": ("J1.2", "U1.2"), "USB_D+": ("J1.1",)}
                if case == "fault"
                else {"USB_D+": ("J1.1", "U1.1"), "USB_D-": ("J1.2", "U1.2")}
            )
            if any(observed.nets.get(net) != pins for net, pins in expected_nets.items()):
                raise ValueError(f"Native USB named-rail {case} net assignments changed")
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
                raise ValueError(f"Native ERC reported errors for USB named-rail {case}")
            project_id = f"synthetic-usb-signal-named-rail-{case}"
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
            findings[(case, run)] = tuple(
                item.subject for item in report.findings if item.rule_id == _RULE_ID
            )

    for case in sources:
        first = normalized_hashes[(case, "first")]
        repeat = normalized_hashes[(case, "repeat")]
        expected = ("U1.1: USB_DP on return-like net GND",) if case == "fault" else ()
        if first != repeat or findings[(case, "first")] != expected:
            raise ValueError(f"Native USB named-rail {case} result differs from its fixture")
        if findings[(case, "repeat")] != findings[(case, "first")]:
            raise ValueError(f"Native USB named-rail {case} findings are not repeatable")
        log.event(
            f"usb-signal-named-rail-fixture/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=first,
            repeat_normalized_netlist_sha256=repeat,
            erc_errors="none",
            repeatable="true",
            subjects=";".join(expected) if expected else "none",
        )
    log.event(
        "usb-signal-named-rail-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
