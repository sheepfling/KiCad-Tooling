"""Digest-pinned native fixtures for serial TX output-sharing review."""

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

SERIAL_TX_OUTPUT_SHARING_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def serial_tx_output_sharing_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeatable native exports, clean ERC, and the TX-sharing review clue."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in SERIAL_TX_OUTPUT_SHARING_TOOLCHAINS:
        raise ValueError(f"Serial TX-sharing fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/serial-tx-output-sharing"
    sources = {
        "control": fixture_root / "tx-one-to-two-rx-control.kicad_sch",
        "fault": fixture_root / "tx-shared-fault.kicad_sch",
    }
    source_hashes = {case: digest(source) for case, source in sources.items()}
    expected_hashes = {
        "control": "2d49ca26d8a70d95c81b9b853b6bccca27a77d70e23b436a08c6b63574d98329",
        "fault": "d9801df7bbe3ef1261dd1edc68cf1fa1adeb0b991412a67c108e2d2d216104b4",
    }
    if source_hashes != expected_hashes:
        raise ValueError("Serial TX-sharing fixture sources changed from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"serial-tx-sharing-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic serial TX-sharing {case} source changed during setup")
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
        "for case in control fault; do\n"
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
        "HOME=/tmp/kicad-serial-tx-output-sharing",
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
        "serial-tx-output-sharing-fixture/native-export",
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
            "serial-tx-output-sharing-fixture/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native serial TX-sharing export failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted an output for serial TX-sharing {case}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version:
                raise ValueError(f"Native ERC version mismatch for serial TX-sharing {case}")
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            report = evaluate(
                f"synthetic-serial-tx-sharing-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-serial-tx-sharing-{case}",
                    observed=observed,
                    netlist_sha256=raw_hashes[(case, run)],
                ),
                DesignLintPolicy(),
            )
            subjects[(case, run)] = tuple(
                item.subject
                for item in report.findings
                if item.rule_id == "bus.serial_tx_outputs_share_net"
            )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]
        or erc_errors[(case, "first")] != erc_errors[(case, "repeat")]
        for case in sources
    ):
        raise ValueError("Native serial TX-sharing outputs differ between repeated exports")
    expected_subjects = {
        "control": (),
        "fault": ("U1, U2: serial TX functions share SERIAL_TX_BUS",),
    }
    for case in sources:
        observed_subjects = subjects[(case, "first")]
        if (
            observed_subjects != expected_subjects[case]
            or subjects[(case, "repeat")] != observed_subjects
        ):
            raise ValueError(
                f"Native serial TX-sharing {case} produced {observed_subjects!r}; "
                f"expected {expected_subjects[case]!r}"
            )
        if erc_errors[(case, "first")]:
            raise ValueError(
                f"Native ERC reported errors on serial TX-sharing {case}: "
                f"{erc_errors[(case, 'first')]!r}"
            )
        log.event(
            f"serial-tx-output-sharing-fixture/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            erc_errors="none",
            repeatable="true",
            subjects=";".join(observed_subjects) if observed_subjects else "none",
        )
    log.event(
        "serial-tx-output-sharing-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
