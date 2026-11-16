"""Digest-pinned native fixtures for shared RS-485 receiver-output review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import DesignLintPolicy
from .hwrepo.native_report_parsing import read_netlist

RS485_RECEIVER_OUTPUT_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
_RULE_ID = "bus.rs485_receiver_outputs_share_net"
_SOURCE_HASHES = {
    "fault": "71ad76ad63c8809b3660430114e2f8dcd4c2d998ce42f2e8003bc9b7cbfc1066",
    "control": "4508463236cfd33c1f681624a4b027ed262c3895e6d5bb7e47dfaedb94f634e0",
}


def rs485_receiver_output_sharing_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Export repeated KiCad netlists and ERC for one shared-net fault/control pair."""
    root = root.resolve()
    if (version, image) not in RS485_RECEIVER_OUTPUT_TOOLCHAINS:
        raise ValueError(
            f"RS-485 receiver-output fixtures do not cover KiCad {version} with this image"
        )
    pinned = pinned_image(image)
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/rs485-receiver-output-sharing"
    )
    sources = {
        "fault": fixture_root / "receiver-outputs-shared.kicad_sch",
        "control": fixture_root / "receiver-outputs-separate-control.kicad_sch",
    }
    source_hashes = {case: digest(source) for case, source in sources.items()}
    if source_hashes != _SOURCE_HASHES:
        raise ValueError("RS-485 receiver-output fixture sources changed from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"rs485-receiver-output-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    output = scratch / "output"
    inputs.mkdir()
    output.mkdir()
    for case, source in sources.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(source, copied)
        if digest(copied) != source_hashes[case]:
            raise ValueError(f"Synthetic RS-485 receiver-output {case} changed during setup")

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
        "HOME=/tmp/kicad-rs485-receiver-output",
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
    stage = "rs485-receiver-output-fixture/native-export"
    log.event(stage, "START", project=f"kicad-{version}", kicad_version=version, image=pinned)
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(
            f"Native RS-485 receiver-output export failed: {command.stderr or command.error}"
        )

    expected_nets = {
        "fault": {"RX_SHARED": ("U1.4", "U2.4")},
        "control": {"RX_U1": ("U1.4",), "RX_U2": ("U2.4",)},
    }
    expected_subjects = {
        "fault": ("U1, U2: RS-485 receiver-output pins share RX_SHARED",),
        "control": (),
    }
    hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted receiver-output evidence for {case}")
            observed = read_netlist(netlist_path)
            if any(
                observed.component_pin_numbers.get(reference) != ("1", "2", "3", "4", "5")
                for reference in ("U1", "U2")
            ):
                raise ValueError(f"Native RS-485 receiver-output {case} lost pin inventory")
            if any(
                observed.pin_functions.get(pin) != "RO"
                or observed.pin_electrical_types.get(pin) != "passive"
                for pin in ("U1.4", "U2.4")
            ):
                raise ValueError(f"Native RS-485 receiver-output {case} lost pin roles or types")
            if any(
                observed.component_symbols.get(reference) != "Synthetic:Rs485_Transceiver"
                or observed.components.get(reference) is None
                or "RS-485" not in observed.components[reference].value
                for reference in ("U1", "U2")
            ):
                raise ValueError(f"Native RS-485 receiver-output {case} lost identity evidence")
            if any(observed.nets.get(net) != pins for net, pins in expected_nets[case].items()):
                raise ValueError(f"Native RS-485 receiver-output {case} assignments changed")

            raw_hashes[(case, run)] = digest(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version:
                raise ValueError(f"Native ERC version mismatch for RS-485 receiver-output {case}")
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            project_id = f"synthetic-rs485-receiver-output-{case}"
            report = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=raw_hashes[(case, run)],
                ),
                DesignLintPolicy(),
            )
            subjects[(case, run)] = tuple(
                item.subject for item in report.findings if item.rule_id == _RULE_ID
            )

    for case in sources:
        if hashes[(case, "first")] != hashes[(case, "repeat")]:
            raise ValueError(f"Native RS-485 receiver-output {case} exports are not repeatable")
        if erc_errors[(case, "first")] != erc_errors[(case, "repeat")]:
            raise ValueError(f"Native ERC changed between RS-485 receiver-output {case} exports")
        if erc_errors[(case, "first")]:
            raise ValueError(
                f"Native ERC reported errors for RS-485 receiver-output {case}: "
                f"{erc_errors[(case, 'first')]!r}"
            )
        if (
            subjects[(case, "first")] != expected_subjects[case]
            or subjects[(case, "repeat")] != subjects[(case, "first")]
        ):
            raise ValueError(f"Native RS-485 receiver-output {case} finding changed")
        log.event(
            f"rs485-receiver-output-fixture/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=hashes[(case, "first")],
            repeat_normalized_netlist_sha256=hashes[(case, "repeat")],
            erc_errors="none",
            repeatable="true",
            subjects=";".join(subjects[(case, "first")]) or "none",
        )
    log.event(
        stage,
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
