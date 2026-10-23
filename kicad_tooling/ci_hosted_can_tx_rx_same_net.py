"""Digest-pinned native fixtures for CAN-controller TX/RX same-net review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

CAN_TX_RX_NATIVE_TOOLCHAINS = (
    (
        "10.0.0",
        (
            "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
        ),
    ),
    (
        "10.0.5",
        (
            "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
        ),
    ),
)


def can_tx_rx_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native netlist/ERC exports and verify the CAN TX/RX fault and control."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in CAN_TX_RX_NATIVE_TOOLCHAINS:
        raise ValueError(f"CAN TX/RX fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/can-tx-rx-same-net"
    sources = {
        "fault": fixture_root / "same-net.kicad_sch",
        "control": fixture_root / "separate-lines-control.kicad_sch",
    }
    source_hashes = {case: digest(source) for case, source in sources.items()}
    expected_source_hashes = {
        "fault": "f656da266a502a5b4e897240af320b8832de3807a66823ed035b105a33b01baa",
        "control": "d175d4e73ffc11aac75e38651835f36d9420df4ace0d2b709313e114c6fa40c7",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("CAN TX/RX fixture sources changed from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"can-tx-rx-same-net-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(source, target)
        if digest(target) != source_hashes[case]:
            raise ValueError(f"Synthetic CAN TX/RX {case} source changed while preparing input")
    output = scratch / "output"
    output.mkdir()
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
        "HOME=/tmp/kicad-can-tx-rx-same-net",
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
        "can-tx-rx-same-net-fixture/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "can-tx-rx-same-net-fixture/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native CAN TX/RX export failed: {command.stderr or command.error}")

    normalized_hashes: dict[tuple[str, str], str] = {}
    netlist_hashes: dict[tuple[str, str], str] = {}
    subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted the CAN TX/RX {case} output")
            netlist_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if case == "fault" and run == "first":
                if observed.pin_functions.get("U1.1") != "CAN1_TX":
                    raise ValueError("Native fault export did not preserve CAN1_TX")
                if observed.pin_functions.get("U1.2") != "CAN1_RX":
                    raise ValueError("Native fault export did not preserve CAN1_RX")
                if set(observed.nets.get("CAN1_DATA", ())) != {"U1.1", "U1.2"}:
                    raise ValueError("Native fault export did not preserve the shared CAN data net")
                if observed.component_pin_numbers.get("U1") != ("1", "2"):
                    raise ValueError("Native fault export did not preserve the pin inventory")
            if case == "control" and run == "first":
                if observed.nets.get("CAN1_TX") != ("U1.1",):
                    raise ValueError("Native control export did not preserve separate CAN1_TX")
                if observed.nets.get("CAN1_RX") != ("U1.2",):
                    raise ValueError("Native control export did not preserve separate CAN1_RX")
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version:
                raise ValueError(f"Native ERC version mismatch for CAN TX/RX {case}")
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            project_id = f"synthetic-can-tx-rx-same-net-{case}"
            report = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=netlist_hashes[(case, run)],
                ),
                DesignLintPolicy(),
            )
            subjects[(case, run)] = tuple(
                item.subject for item in report.findings if item.rule_id == "bus.can_tx_rx_same_net"
            )

    expected_subjects = {
        "fault": ("U1: CAN channel 1 TX CAN1_TX and RX CAN1_RX share CAN1_DATA",),
        "control": (),
    }
    for case in sources:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native CAN TX/RX {case} netlists differ after normalization")
        if erc_errors[(case, "first")] != erc_errors[(case, "repeat")]:
            raise ValueError(f"Native CAN TX/RX {case} ERC results differ on repeat")
        if erc_errors[(case, "first")]:
            raise ValueError(f"Native ERC reported CAN TX/RX {case} errors")
        if subjects[(case, "first")] != expected_subjects[case]:
            raise ValueError(
                f"Native CAN TX/RX {case} produced {subjects[(case, 'first')]!r}; "
                f"expected {expected_subjects[case]!r}"
            )
        if subjects[(case, "repeat")] != subjects[(case, "first")]:
            raise ValueError(f"Native CAN TX/RX {case} findings differ on repeat")
        log.event(
            f"can-tx-rx-same-net-fixture/{case}",
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
        "can-tx-rx-same-net-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
