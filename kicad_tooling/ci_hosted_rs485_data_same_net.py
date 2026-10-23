"""Digest-pinned native fixtures for RS-485 data-pin same-net review."""

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

RS485_DATA_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
_RULE_ID = "bus.rs485_data_input_output_same_net"
_SOURCE_HASHES = {
    "fault": "d8af98143c7c94d2227206c5e6e93d03f8a82f32c9dbf87f93c6ad37bba4bc3a",
    "control": "457198946c70c987a76ff18a4ea992e780db650dcd908497941fe2e8401f5d90",
}


def rs485_data_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat exact native netlist/ERC exports for shared and separate D/R nets."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in RS485_DATA_SAME_NET_TOOLCHAINS:
        raise ValueError(f"RS-485 same-net fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/rs485-data-same-net"
    )
    sources = {
        "fault": fixture_root / "same-data-net.kicad_sch",
        "control": fixture_root / "separate-data-nets-control.kicad_sch",
    }
    source_hashes = {case: digest(source) for case, source in sources.items()}
    if source_hashes != _SOURCE_HASHES:
        raise ValueError("RS-485 same-net sources differ from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"rs485-data-same-net-{version}-", dir=log.directory.resolve())
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
        "HOME=/tmp/kicad-rs485-data-same-net",
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
        "rs485-data-same-net-fixture/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(f"Native RS-485 same-net export failed: {command.stderr or command.error}")

    normalized_hashes: dict[tuple[str, str], str] = {}
    subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    for case, source in sources.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted RS-485 same-net {case} evidence")
            observed = read_netlist(netlist_path)
            if observed.component_pin_numbers.get("U1") != ("1", "2"):
                raise ValueError(f"Native RS-485 same-net {case} lost pin inventory")
            if (
                observed.pin_functions.get("U1.1") != "D"
                or observed.pin_functions.get("U1.2") != "R"
            ):
                raise ValueError(f"Native RS-485 same-net {case} lost D/R pin functions")
            if case == "fault":
                expected_nets = {"DATA_SHARED": ("U1.1", "U1.2")}
            else:
                expected_nets = {"HOST_TX": ("U1.1",), "HOST_RX": ("U1.2",)}
            if any(observed.nets.get(net) != pins for net, pins in expected_nets.items()):
                actual_nets = {net: observed.nets.get(net) for net in expected_nets}
                raise ValueError(
                    f"Native RS-485 same-net {case} assignments changed: "
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
                raise ValueError(f"Native ERC reported errors for RS-485 same-net {case}")
            project_id = f"synthetic-rs485-data-same-net-{case}"
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
            subjects[(case, run)] = tuple(
                item.subject for item in report.findings if item.rule_id == _RULE_ID
            )

    expected_subjects = {
        "fault": ("U1: RS-485 driver input and receiver output share DATA_SHARED",),
        "control": (),
    }
    for case in sources:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native RS-485 same-net {case} exports are not repeatable")
        if (
            subjects[(case, "first")] != expected_subjects[case]
            or subjects[(case, "repeat")] != subjects[(case, "first")]
        ):
            raise ValueError(f"Native RS-485 same-net {case} findings do not match the fixture")
        log.event(
            f"rs485-data-same-net-fixture/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            erc_errors="none",
            repeatable="true",
            subjects=";".join(subjects[(case, "first")]) or "none",
        )
    log.event(
        "rs485-data-same-net-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
