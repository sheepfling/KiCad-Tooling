"""Digest-pinned native fixtures for shared SPI data-output review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_spi_native import SPI_NATIVE_TOOLCHAINS as SPI_SHARED_DATA_OUTPUT_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist


def spi_shared_data_output_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeated native exports, clean ERC, and shared-data review evidence."""

    root = root.resolve()
    if (version, image) not in SPI_SHARED_DATA_OUTPUT_TOOLCHAINS:
        raise ValueError(f"SPI shared-data fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    repository = tooling_checkout_root()
    fixture_root = repository / "tests/fixtures/design_lint/spi-shared-data-outputs"
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in ("fault", "control")}
    source_hashes = {case: digest(source) for case, source in sources.items()}
    expected_hashes = {
        "fault": "b22837132aeff633a2a91c023a6f49c8469326593bee4942e37f2568a6d5bfb6",
        "control": "f8265c27a9c20a40e44232374c3650a0f17a23c066db3fe9d6dd6b5911b3ae85",
    }
    if source_hashes != expected_hashes:
        raise ValueError("SPI shared-data fixture sources changed from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"spi-shared-data-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic SPI shared-data {case} source changed during setup")
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
        "HOME=/tmp/kicad-spi-shared-data",
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
        "spi-shared-data-fixture/native-export",
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
            "spi-shared-data-fixture/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native SPI shared-data export failed: {command.stderr or command.error}")

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted an output for SPI shared-data {case}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if case == "fault" and run == "first":
                expected = {
                    "functions": {"U2.1": "MISO", "U3.1": "MISO"},
                    "types": {"U2.1": "passive", "U3.1": "passive"},
                }
                if any(
                    observed.pin_functions.get(pin) != function
                    for pin, function in expected["functions"].items()
                ):
                    raise ValueError("Native fault export did not preserve SPI MISO pin functions")
                if any(
                    observed.pin_electrical_types.get(pin) != kind
                    for pin, kind in expected["types"].items()
                ):
                    raise ValueError(
                        "Native fault export did not preserve SPI pin electrical types"
                    )
                if observed.nets.get("SPI_MISO") != ("U2.1", "U3.1"):
                    raise ValueError("Native fault export did not preserve the shared SPI_MISO net")
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version:
                raise ValueError(f"Native ERC version mismatch for SPI shared-data {case}")
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            report = evaluate(
                f"synthetic-spi-shared-data-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-spi-shared-data-{case}",
                    observed=observed,
                    netlist_sha256=raw_hashes[(case, run)],
                ),
                DesignLintPolicy(),
            )
            subjects[(case, run)] = tuple(
                item.subject
                for item in report.findings
                if item.rule_id == "bus.spi_data_outputs_share_net"
            )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]
        or erc_errors[(case, "first")] != erc_errors[(case, "repeat")]
        for case in sources
    ):
        raise ValueError("Native SPI shared-data outputs differ between repeated exports")
    expected_subjects = {
        "fault": ("U2, U3: SPI data-output pins share SPI_MISO",),
        "control": (),
    }
    for case in sources:
        observed_subjects = subjects[(case, "first")]
        if (
            observed_subjects != expected_subjects[case]
            or subjects[(case, "repeat")] != observed_subjects
        ):
            raise ValueError(
                f"Native SPI shared-data {case} produced {observed_subjects!r}; "
                f"expected {expected_subjects[case]!r}"
            )
        if erc_errors[(case, "first")]:
            raise ValueError(
                f"Native ERC reported errors on SPI shared-data {case}: "
                f"{erc_errors[(case, 'first')]!r}"
            )
        log.event(
            f"spi-shared-data-fixture/{case}",
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
        "spi-shared-data-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
