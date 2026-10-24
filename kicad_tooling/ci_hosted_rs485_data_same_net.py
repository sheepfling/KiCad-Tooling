"""Digest-pinned native fixtures for focused RS-485 data-pin reviews."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

RS485_DATA_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
_RULE_ID = "bus.rs485_data_input_output_same_net"
_SOURCE_HASHES = {
    "fault": "d8af98143c7c94d2227206c5e6e93d03f8a82f32c9dbf87f93c6ad37bba4bc3a",
    "control": "17edbd6020658f7b4ef29413928ed93fdca4b13a41c2b09c783fe4ce330ccfc8",
}
_NAMED_RAIL_RULE_ID = "bus.rs485_signal_on_named_rail"
_NAMED_RAIL_SOURCE_HASHES = {
    "fault": "4808cd9ba83174fd0d32d182f5816effa20a88da097dc18dea419f5115a39d23",
    "control": "aa38e247661a1bf88460122caf2214bf3ad11468debdc4b6edd71a628a02e512",
}


def rs485_data_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat exact native netlist/ERC exports for shared and separate D/R nets."""
    _rs485_fixture_lane(root, version=version, image=image, log=log, feature="same_net")


def rs485_signal_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat exact native exports for an RS-485 data pin on a named rail."""
    _rs485_fixture_lane(root, version=version, image=image, log=log, feature="named_rail")


def _rs485_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
    feature: Literal["same_net", "named_rail"],
) -> None:
    """Run the source-bound native lane shared by the RS-485 heuristics."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in RS485_DATA_SAME_NET_TOOLCHAINS:
        raise ValueError(f"RS-485 same-net fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    if feature == "same_net":
        fixture_directory = "rs485-data-same-net"
        stage_prefix = "rs485-data-same-net-fixture"
        rule_id = _RULE_ID
        source_names = {
            "fault": "same-data-net.kicad_sch",
            "control": "separate-data-nets-control.kicad_sch",
        }
        reviewed_hashes = _SOURCE_HASHES
        expected_subjects = {
            "fault": ("U1: RS-485 driver input and receiver output share DATA_SHARED",),
            "control": (),
        }
        expected_nets = {
            "fault": {"DATA_SHARED": ("U1.1", "U1.2")},
            "control": {"HOST_TX": ("U1.1",), "HOST_RX": ("U1.2",)},
        }
    else:
        fixture_directory = "rs485-signal-named-rail"
        stage_prefix = "rs485-signal-named-rail-fixture"
        rule_id = _NAMED_RAIL_RULE_ID
        source_names = {"fault": "fault.kicad_sch", "control": "control.kicad_sch"}
        reviewed_hashes = _NAMED_RAIL_SOURCE_HASHES
        expected_subjects = {
            "fault": ("U1.1: D on return-like net GND",),
            "control": (),
        }
        expected_nets = {
            "fault": {"GND": ("U1.1",), "HOST_RX": ("U1.2",)},
            "control": {"HOST_TX": ("U1.1",), "HOST_RX": ("U1.2",)},
        }
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint" / fixture_directory
    )
    sources = {case: fixture_root / name for case, name in source_names.items()}
    source_hashes = {case: digest(source) for case, source in sources.items()}
    if source_hashes != reviewed_hashes:
        raise ValueError(f"RS-485 {feature} sources differ from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"rs485-{feature}-{version}-", dir=log.directory.resolve())
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
        f"HOME=/tmp/kicad-rs485-{feature}",
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
        f"{stage_prefix}/native-export",
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
            f"Native RS-485 {feature} export failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    for case, source in sources.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted RS-485 {feature} {case} evidence")
            observed = read_netlist(netlist_path)
            if observed.component_pin_numbers.get("U1") != ("1", "2"):
                raise ValueError(f"Native RS-485 {feature} {case} lost pin inventory")
            if (
                observed.pin_functions.get("U1.1") != "D"
                or observed.pin_functions.get("U1.2") != "R"
            ):
                raise ValueError(f"Native RS-485 {feature} {case} lost D/R pin functions")
            expected_case_nets = expected_nets[case]
            if any(observed.nets.get(net) != pins for net, pins in expected_case_nets.items()):
                actual_nets = {net: observed.nets.get(net) for net in expected_case_nets}
                raise ValueError(
                    f"Native RS-485 {feature} {case} assignments changed: "
                    f"expected={expected_case_nets!r}, actual={actual_nets!r}"
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
                raise ValueError(f"Native ERC reported errors for RS-485 {feature} {case}")
            project_id = f"synthetic-rs485-{feature}-{case}"
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
                item.subject for item in report.findings if item.rule_id == rule_id
            )

    for case in sources:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native RS-485 {feature} {case} exports are not repeatable")
        if (
            subjects[(case, "first")] != expected_subjects[case]
            or subjects[(case, "repeat")] != subjects[(case, "first")]
        ):
            raise ValueError(f"Native RS-485 {feature} {case} findings do not match the fixture")
        log.event(
            f"{stage_prefix}/{case}",
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
        f"{stage_prefix}/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
