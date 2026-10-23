"""Digest-pinned native fixtures for I2C SDA/SCL same-net review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_i2c_native import I2C_NATIVE_TOOLCHAINS
from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


def i2c_sda_scl_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeatable netlist/ERC exports and same-net review evidence."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in I2C_NATIVE_TOOLCHAINS:
        raise ValueError(f"I2C same-net fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/i2c-sda-scl-same-net"
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in ("fault", "control")}
    source_hashes = {case: digest(source) for case, source in sources.items()}
    expected_hashes = {
        "fault": "e45583f123b62fe0769d19e5ffd08200510b9abb44afb97d6a8fc269ed3e84b6",
        "control": "a6ef0cf9ed06fe027c53a4d57624b0a72d244de75e1266b8df0ded924e378681",
    }
    if source_hashes != expected_hashes:
        raise ValueError("I2C same-net fixture sources changed from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"i2c-sda-scl-same-net-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic I2C {case} source changed while preparing native input")
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
        "HOME=/tmp/kicad-i2c-sda-scl-same-net",
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
        "i2c-sda-scl-same-net-fixture/native-export",
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
            "i2c-sda-scl-same-net-fixture/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native I2C same-net export failed: {command.stderr or command.error}")

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted an output for I2C same-net {case}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if case == "fault" and run == "first":
                if (
                    observed.pin_functions.get("U1.1") != "SDA"
                    or observed.pin_functions.get("U1.2") != "SCL"
                ):
                    raise ValueError("Native I2C same-net fault lost SDA/SCL pin functions")
                if observed.nets.get("I2C_SHARED") != ("U1.1", "U1.2"):
                    raise ValueError("Native I2C fault did not retain the shared signal net")
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version:
                raise ValueError(f"Native ERC version mismatch for I2C same-net {case}")
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            project_id = f"synthetic-i2c-sda-scl-same-net-{case}"
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
                item.subject
                for item in report.findings
                if item.rule_id == "bus.i2c_sda_scl_same_net"
            )

    for case in sources:
        if (
            normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]
            or erc_errors[(case, "first")] != erc_errors[(case, "repeat")]
        ):
            raise ValueError(f"Native I2C same-net exports differ for {case}")
    expected_subjects = {
        "fault": ("U1: I2C SDA/SCL pins share I2C_SHARED",),
        "control": (),
    }
    for case in sources:
        observed_subjects = subjects[(case, "first")]
        if (
            observed_subjects != expected_subjects[case]
            or subjects[(case, "repeat")] != observed_subjects
        ):
            raise ValueError(
                f"Native I2C same-net {case} produced {observed_subjects!r}; "
                f"expected {expected_subjects[case]!r}"
            )
        if erc_errors[(case, "first")]:
            raise ValueError(f"Native ERC reported I2C same-net {case} errors")
        log.event(
            f"i2c-sda-scl-same-net-fixture/{case}",
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
        "i2c-sda-scl-same-net-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in sorted(sources)),
        command_receipt=receipt.relative_to(root).as_posix(),
        repeatable="true",
    )
    log.finish()
