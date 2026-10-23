"""Digest-pinned native fixtures for RS-485 data-direction review."""

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

RS485_DATA_DIRECTION_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
_RULE_ID = "bus.rs485_data_direction_label_mismatch"
_SOURCE_HASHES = {
    "fault": "10b0e622dd9359866b7edce3dd81c9f6bff6b7e00c3ce1392eef3ae5bb5f605a",
    "control": "16711f441b0a0fc050378ffea39b1bbcecf9c9c698a1da5987a15d5670327cad",
}


def rs485_data_direction_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat exact native netlist/ERC exports for crossed and matching labels."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in RS485_DATA_DIRECTION_TOOLCHAINS:
        raise ValueError(
            f"RS-485 data direction fixtures do not cover KiCad {version} with this image"
        )
    pinned = pinned_image(image)
    fixture_root = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/design_lint/rs485-data-direction-label-mismatch"
    )
    sources = {
        "fault": fixture_root / "crossed-data-labels.kicad_sch",
        "control": fixture_root / "matching-data-labels-control.kicad_sch",
    }
    source_hashes = {case: digest(source) for case, source in sources.items()}
    if source_hashes != _SOURCE_HASHES:
        raise ValueError("RS-485 data direction sources differ from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"rs485-data-direction-{version}-", dir=log.directory.resolve())
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
        "HOME=/tmp/kicad-rs485-data-direction-label-mismatch",
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
        "rs485-data-direction-fixture/native-export",
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
            f"Native RS-485 data direction export failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    for case, source in sources.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted RS-485 data direction {case} evidence")
            observed = read_netlist(netlist_path)
            if observed.component_pin_numbers.get("U1") != ("1", "2"):
                raise ValueError(f"Native RS-485 data direction {case} lost pin inventory")
            if (
                observed.pin_functions.get("U1.1") != "D"
                or observed.pin_functions.get("U1.2") != "R"
            ):
                raise ValueError(f"Native RS-485 data direction {case} lost D/R pin functions")
            expected_nets = (
                {"USART1_TX": ("U1.2",), "USART1_RX": ("U1.1",)}
                if case == "fault"
                else {"USART1_RX": ("U1.2",), "USART1_TX": ("U1.1",)}
            )
            if any(observed.nets.get(net) != pins for net, pins in expected_nets.items()):
                actual_nets = {net: observed.nets.get(net) for net in expected_nets}
                raise ValueError(
                    f"Native RS-485 data direction {case} assignments changed: "
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
                raise ValueError(f"Native ERC reported errors for RS-485 data direction {case}")
            project_id = f"synthetic-rs485-data-direction-{case}"
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
        "fault": ("U1.1: D on USART1_RX", "U1.2: R on USART1_TX"),
        "control": (),
    }
    for case in sources:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native RS-485 data direction {case} exports are not repeatable")
        if (
            subjects[(case, "first")] != expected_subjects[case]
            or subjects[(case, "repeat")] != subjects[(case, "first")]
        ):
            raise ValueError(
                f"Native RS-485 data direction {case} findings do not match the fixture"
            )
        log.event(
            f"rs485-data-direction-fixture/{case}",
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
        "rs485-data-direction-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
