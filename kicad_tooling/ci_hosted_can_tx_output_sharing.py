"""Digest-pinned native fixtures for CAN TX output-sharing review."""

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
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist

CAN_TX_OUTPUT_SHARING_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def can_tx_output_sharing_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native netlist/ERC exports and verify shared-TX fault and control."""
    root = root.resolve()
    if (version, image) not in CAN_TX_OUTPUT_SHARING_TOOLCHAINS:
        raise ValueError(f"CAN TX-sharing fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint/can-tx-output-sharing"
    sources = {
        "fault": fixture_root / "multiple-transmitters.kicad_sch",
        "control": fixture_root / "one-transmitter-control.kicad_sch",
    }
    source_hashes = {case: digest(source) for case, source in sources.items()}
    expected_hashes = {
        "fault": "c3a6207f2c03eb1e5ce7bd6cbc9bd544833463e92f639a09b7ad126079a3d4e6",
        "control": "45907af0a675dd98b7fd6bc48046be280b7ce4b9da72b84a67be9d7f384fb6d3",
    }
    if source_hashes != expected_hashes:
        raise ValueError("CAN TX-sharing fixture sources changed from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"can-tx-output-sharing-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(source, target)
        if digest(target) != source_hashes[case]:
            raise ValueError(f"Synthetic CAN TX-sharing {case} source changed during setup")
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
        "HOME=/tmp/kicad-can-tx-output-sharing",
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
        "can-tx-output-sharing-fixture/native-export",
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
            "can-tx-output-sharing-fixture/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native CAN TX-sharing export failed: {command.stderr or command.error}")

    normalized_hashes: dict[tuple[str, str], str] = {}
    source_output_hashes: dict[tuple[str, str], str] = {}
    subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted a CAN TX-sharing {case} output")
            source_output_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if case == "fault" and run == "first":
                if {observed.pin_functions.get(f"U{index}.1") for index in (1, 2)} != {"CAN1_TX"}:
                    raise ValueError(
                        "Native CAN TX-sharing fault did not preserve both TX functions"
                    )
                if set(observed.nets.get("CAN_TX_SHARED", ())) != {"U1.1", "U2.1"}:
                    raise ValueError("Native CAN TX-sharing fault did not preserve the shared net")
                if any(
                    observed.component_pin_numbers.get(f"U{index}") != ("1", "2")
                    for index in (1, 2)
                ):
                    raise ValueError("Native CAN TX-sharing fault did not preserve pin inventories")
            if case == "control" and run == "first":
                if set(observed.nets.get("CAN_CONTROLLER_LINK", ())) != {"U1.1", "U2.2"}:
                    raise ValueError("Native CAN TX-sharing control did not preserve TX-to-RX link")
                if observed.nets.get("CAN2_TX") != ("U2.1",):
                    raise ValueError(
                        "Native CAN TX-sharing control unexpectedly shares both TX pins"
                    )
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version:
                raise ValueError(f"Native ERC version mismatch for CAN TX-sharing {case}")
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            project_id = f"synthetic-can-tx-output-sharing-{case}"
            report = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=source_output_hashes[(case, run)],
                ),
                DesignLintPolicy(),
            )
            subjects[(case, run)] = tuple(
                item.subject
                for item in report.findings
                if item.rule_id == "bus.can_tx_outputs_share_net"
            )

    expected_subjects = {
        "fault": ("U1, U2: CAN TX functions share CAN_TX_SHARED",),
        "control": (),
    }
    for case in sources:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native CAN TX-sharing {case} netlists differ after normalization")
        if erc_errors[(case, "first")] != erc_errors[(case, "repeat")]:
            raise ValueError(f"Native CAN TX-sharing {case} ERC results differ on repeat")
        if erc_errors[(case, "first")]:
            raise ValueError(f"Native ERC reported CAN TX-sharing {case} errors")
        if subjects[(case, "first")] != expected_subjects[case]:
            raise ValueError(
                f"Native CAN TX-sharing {case} produced {subjects[(case, 'first')]!r}; "
                f"expected {expected_subjects[case]!r}"
            )
        if subjects[(case, "repeat")] != subjects[(case, "first")]:
            raise ValueError(f"Native CAN TX-sharing {case} findings differ on repeat")
        log.event(
            f"can-tx-output-sharing-fixture/{case}",
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
        "can-tx-output-sharing-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
