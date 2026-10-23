"""Digest-pinned native fixtures for SPI clock/control same-net review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_spi_native import SPI_NATIVE_TOOLCHAINS
from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


def spi_clock_control_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native netlist/ERC exports and verify the exact SPI fault/control pair."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    if (version, image) not in SPI_NATIVE_TOOLCHAINS:
        raise ValueError(f"SPI clock/control fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/spi-clock-control-same-net"
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in ("fault", "control")}
    source_hashes = {case: digest(source) for case, source in sources.items()}
    expected_source_hashes = {
        "fault": "794de6c0725d6c43c3c06f1052432974a99531502e4ce58c3419bf8c93a73a34",
        "control": "ab9dce76c1cf100f8d684108c2460b4c928fff9d9f9b53d52e213ad53f41f657",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("SPI clock/control fixtures changed from their reviewed source hashes")

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"spi-clock-control-same-net-{version}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(source, target)
        if digest(target) != source_hashes[case]:
            raise ValueError(f"Synthetic SPI {case} source changed while preparing native input")
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
        "HOME=/tmp/kicad-spi-clock-control-fixtures",
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
        "spi-clock-control-same-net-fixture/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root.resolve(), argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "spi-clock-control-same-net-fixture/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root.resolve()).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native SPI clock/control export failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    findings: dict[tuple[str, str], tuple[str, ...]] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted an SPI clock/control {case} output")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if case == "fault" and run == "first":
                if observed.pin_functions.get("U1.1") != "COPI":
                    raise ValueError("Native fault export did not preserve the COPI function")
                if observed.pin_functions.get("U1.3") != "SCK":
                    raise ValueError("Native fault export did not preserve the SCK function")
                if set(observed.nets.get("SPI_ROLE_SHARED", ())) != {"U1.1", "U1.3"}:
                    raise ValueError("Native fault export did not preserve the shared role net")
                if observed.component_pin_numbers.get("U1") != ("1", "2", "3", "4"):
                    raise ValueError("Native fault export did not preserve the four-pin inventory")
            if case == "control" and run == "first":
                if observed.nets.get("SPI_COPI") != ("U1.1",):
                    raise ValueError("Native control export did not preserve the COPI net")
                if observed.nets.get("SPI_SCK") != ("U1.3",):
                    raise ValueError("Native control export did not preserve the SCK net")
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version:
                raise ValueError(f"Native ERC version mismatch for SPI clock/control {case}")
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            project_id = f"synthetic-spi-clock-control-same-net-{case}"
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
            findings[(case, run)] = tuple(
                item.subject
                for item in report.findings
                if item.rule_id == "bus.spi_clock_control_data_same_net"
            )

    for case in sources:
        if (
            normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]
            or erc_errors[(case, "first")] != erc_errors[(case, "repeat")]
        ):
            raise ValueError(f"Native SPI clock/control exports differ for {case}")
    expected_findings = {
        "fault": ("U1: SPI clock SCK and data input COPI share SPI_ROLE_SHARED",),
        "control": (),
    }
    for case in sources:
        observed_findings = findings[(case, "first")]
        if (
            observed_findings != expected_findings[case]
            or findings[(case, "repeat")] != observed_findings
        ):
            raise ValueError(
                f"Native SPI clock/control {case} produced {observed_findings!r}; "
                f"expected {expected_findings[case]!r}"
            )
        if erc_errors[(case, "first")]:
            raise ValueError(f"Native ERC reported SPI clock/control {case} errors")
        log.event(
            f"spi-clock-control-same-net-fixture/{case}",
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
            subjects=";".join(observed_findings) if observed_findings else "none",
        )
    log.event(
        "spi-clock-control-same-net-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root.resolve()).as_posix(),
    )
    log.finish()
