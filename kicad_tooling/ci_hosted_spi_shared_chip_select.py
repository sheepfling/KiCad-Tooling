"""Digest-pinned native fixtures for shared SPI chip-select review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_spi_native import SPI_NATIVE_TOOLCHAINS as SPI_SHARED_CHIP_SELECT_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist


def spi_shared_chip_select_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeatable native exports, clean ERC, and shared-select review evidence."""

    root = root.resolve()
    if (version, image) not in SPI_SHARED_CHIP_SELECT_TOOLCHAINS:
        raise ValueError(f"SPI shared-select fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    repository = tooling_checkout_root()
    fixture_root = repository / "tests/fixtures/design_lint/spi-shared-chip-select"
    sources = {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
    source_hashes = {case: digest(source) for case, source in sources.items()}
    expected_hashes = {
        "fault": "07cb6cd5633436b444c92fadb4b512284c4fad8d54ab2127a0de7f81e5011cc1",
        "control": "5fedc3b7347b17ec78b4c775773cef64b2e1df7b4a59d21fc22343759c5c8b2e",
    }
    if source_hashes != expected_hashes:
        raise ValueError("SPI shared-select fixture sources changed from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"spi-shared-select-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic SPI shared-select {case} source changed during setup")
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
        "HOME=/tmp/kicad-spi-shared-chip-select",
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
        "spi-shared-chip-select-fixture/native-export",
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
            "spi-shared-chip-select-fixture/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native SPI shared-select export failed: {command.stderr or command.error}"
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
                raise ValueError(f"Native KiCad omitted an output for SPI shared-select {case}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if case == "fault" and run == "first":
                expected_functions = {"U1.1": "SPI1_NSS", "U2.1": "CS_N", "U3.1": "CS_N"}
                expected_types = {"U1.1": "output", "U2.1": "input", "U3.1": "input"}
                if any(
                    observed.pin_functions.get(pin) != name
                    for pin, name in expected_functions.items()
                ):
                    raise ValueError(
                        "Native fault export did not preserve the reviewed SPI pin functions"
                    )
                if any(
                    observed.pin_electrical_types.get(pin) != kind
                    for pin, kind in expected_types.items()
                ):
                    raise ValueError(
                        "Native fault export did not preserve the reviewed SPI pin types"
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
                raise ValueError(f"Native ERC version mismatch for SPI shared-select {case}")
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            report = evaluate(
                f"synthetic-spi-shared-chip-select-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-spi-shared-chip-select-{case}",
                    observed=observed,
                    netlist_sha256=raw_hashes[(case, run)],
                ),
                DesignLintPolicy(),
            )
            subjects[(case, run)] = tuple(
                item.subject
                for item in report.findings
                if item.rule_id == "bus.spi_chip_select_inputs_share_net"
            )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]
        or erc_errors[(case, "first")] != erc_errors[(case, "repeat")]
        for case in sources
    ):
        raise ValueError("Native SPI shared-select outputs differ between repeated exports")
    expected_subjects = {
        "fault": ("U2, U3: SPI chip-select inputs share SPI_CS0",),
        "control": (),
    }
    for case in sources:
        observed_subjects = subjects[(case, "first")]
        if (
            observed_subjects != expected_subjects[case]
            or subjects[(case, "repeat")] != observed_subjects
        ):
            raise ValueError(
                f"Native SPI shared-select {case} produced {observed_subjects!r}; "
                f"expected {expected_subjects[case]!r}"
            )
        if erc_errors[(case, "first")]:
            raise ValueError(
                f"Native ERC reported errors on SPI shared-select {case}: "
                f"{erc_errors[(case, 'first')]!r}"
            )
        log.event(
            f"spi-shared-chip-select-fixture/{case}",
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
        "spi-shared-chip-select-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
