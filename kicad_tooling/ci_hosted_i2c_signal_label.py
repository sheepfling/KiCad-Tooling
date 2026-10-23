"""Digest-pinned native fixture lane for I2C SDA/SCL label review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

I2C_NATIVE_TOOLCHAINS = (
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


def i2c_signal_label_fixture_lane(root: Path, *, version: str, image: str, log: HostedLog) -> None:
    """Verify crossed SDA/SCL labels against a control with repeated native exports."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.design_lint_report_models import DesignLintReport
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in I2C_NATIVE_TOOLCHAINS:
        raise ValueError(f"I2C signal-role fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/i2c-signal-label-native"
    sources = {
        "control": fixture_root / "correct-i2c-lines.kicad_sch",
        "fault": fixture_root / "mismatched-i2c-lines.kicad_sch",
    }
    source_hashes = {case: digest(source) for case, source in sources.items()}
    expected_hashes = {
        "control": "c9129c01d99cc2636e2c1f5176fbf04cadc0ec875562ea83cc9f6dabe9ccf586",
        "fault": "a9e9f961a03948608a2c36e2c7bf718003c8e3453f01593ce951ccdeb7d9774c",
    }
    if source_hashes != expected_hashes:
        raise ValueError("I2C signal-role fixture sources changed from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"i2c-signal-label-{version}-", dir=log.directory.resolve())
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
        "for case in control fault; do\n"
        "  for run in first repeat; do\n"
        '    kicad-cli sch export netlist --format kicadxml --output "/output/${case}.${run}.netlist.xml" '
        '"/fixtures/${case}.kicad_sch"\n'
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
        "HOME=/tmp/kicad-i2c-signal-label-fixtures",
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
        "i2c-signal-label-fixture/native-export",
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
            "i2c-signal-label-fixture/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native I2C signal-role export failed: {command.stderr or command.error}")

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native I2C export omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-i2c-signal-label-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]
        for case in sources
    ):
        raise ValueError("Native I2C signal-role exports differ after netlist normalization")

    expected_subjects = ("U1.1: SDA on I2C_SCL", "U1.2: SCL on I2C_SDA")
    rule_id = "bus.i2c_signal_label_role_mismatch"
    for case in ("control", "fault"):
        report = reports[(case, "first")]
        findings = tuple(item for item in report.findings if item.rule_id == rule_id)
        subjects = tuple(item.subject for item in findings)
        expected = expected_subjects if case == "fault" else ()
        if subjects != expected:
            raise ValueError(
                f"Native I2C signal-role {case} produced {subjects!r}; expected {expected!r}"
            )
        log.event(
            f"i2c-signal-label-fixture/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            repeatable="true",
            lint_status=report.status,
            role_findings=";".join(subjects) if subjects else "none",
        )
    log.event(
        "i2c-signal-label-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in sorted(sources)),
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
