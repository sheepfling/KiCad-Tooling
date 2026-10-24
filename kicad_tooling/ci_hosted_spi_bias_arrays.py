"""Digest-pinned native fixtures for mapped SPI chip-select bias arrays."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_spi_native import SPI_NATIVE_TOOLCHAINS as SPI_BIAS_ARRAY_TOOLCHAINS
from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


def spi_bias_array_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
) -> None:
    """Verify repeatable native exports, array contract checks, and lint results."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.design_lint_policy_models import DesignLintPolicy
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport
    from .hwrepo.spi_contract import spi_checks
    from .hwrepo.spi_models import SpiAnalysis
    from .hwrepo.spi_participants import SpiRosterContext
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in SPI_BIAS_ARRAY_TOOLCHAINS:
        raise ValueError(f"SPI bias-array fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/spi-bias-array-native"
    sources = {
        "control": fixture_root / "control.kicad_sch",
        "fault": fixture_root / "fault.kicad_sch",
    }
    contract_path = fixture_root / "spi.json"
    source_hashes = {case: digest(source) for case, source in sources.items()}
    expected_source_hashes = {
        "control": "ffe5cb313f55aa3f0105392a66ca5eb24c021e448e22daed75ec9c6cc8474203",
        "fault": "930e3ea9fd621140ff739c1ff13cd64182c325c5bf8fefe4db7a4e2d231d2e18",
    }
    expected_contract_hash = "ecadc621e352e50f891f081447b38b993014592e35b52ff1cde653a6251599cb"
    if source_hashes != expected_source_hashes:
        raise ValueError("SPI bias-array fixture schematics changed from their reviewed hashes")
    contract_sha256 = digest(contract_path)
    if contract_sha256 != expected_contract_hash:
        raise ValueError("SPI bias-array contract changed from its reviewed hash")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"spi-bias-array-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic SPI bias-array {case} source changed during setup")
    shutil.copyfile(contract_path, inputs / "spi.json")
    if digest(inputs / "spi.json") != contract_sha256:
        raise ValueError("Synthetic SPI bias-array contract changed during setup")

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
        "HOME=/tmp/kicad-spi-bias-array",
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
        "spi-bias-array-fixture/native-export",
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
            "spi-bias-array-fixture/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native SPI bias-array export failed: {command.stderr or command.error}")

    analysis = SpiAnalysis.model_validate_json(contract_path.read_text(encoding="utf-8"))
    roster = SpiRosterContext(
        state="required",
        analysis=analysis,
        source_path=contract_path.relative_to(repository).as_posix(),
        source_sha256=contract_sha256,
    )
    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    array_statuses: dict[tuple[str, str], str] = {}
    array_details: dict[tuple[str, str], str] = {}
    findings: dict[tuple[str, str], tuple[str, ...]] = {}
    for case, source in sources.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native KiCad omitted an SPI bias-array export for {case}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if observed.pin_functions.get("U2.1") != "CS_N":
                raise ValueError(f"Native {case} export lost the active-low SPI input function")
            if observed.pin_electrical_types.get("U2.1", "").casefold() != "input":
                raise ValueError(f"Native {case} export lost the SPI input electrical type")
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            check_id = "spi/bias-array/RN1/peripheral-select"
            array_checks = {item.id: item for item in spi_checks(analysis, observed)}
            if check_id not in array_checks:
                raise ValueError(f"Native {case} did not produce the mapped SPI array check")
            array_statuses[(case, run)] = array_checks[check_id].status
            array_details[(case, run)] = array_checks[check_id].detail
            report = evaluate(
                f"synthetic-spi-bias-array-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-spi-bias-array-{case}",
                    observed=observed,
                    netlist_sha256=raw_hashes[(case, run)],
                ),
                DesignLintPolicy(),
                spi_roster=roster,
            )
            findings[(case, run)] = tuple(
                item.subject
                for item in report.findings
                if item.rule_id == "bus.spi_active_low_chip_select_without_pullup"
            )

    expected_status = {"control": "PASS", "fault": "FAIL"}
    expected_findings = {"control": (), "fault": ("SPI_CS_N: active-low SPI chip-select bias",)}
    for case in sources:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native SPI bias-array {case} exports are not repeatable")
        if array_statuses[(case, "first")] != expected_status[case]:
            raise ValueError(
                f"Native SPI bias-array {case} check is {array_statuses[(case, 'first')]}; "
                f"expected {expected_status[case]}: {array_details[(case, 'first')]}"
            )
        if array_statuses[(case, "repeat")] != array_statuses[(case, "first")]:
            raise ValueError(f"Native SPI bias-array {case} check changed between exports")
        if findings[(case, "first")] != expected_findings[case]:
            raise ValueError(
                f"Native SPI bias-array {case} findings are {findings[(case, 'first')]!r}; "
                f"expected {expected_findings[case]!r}"
            )
        if findings[(case, "repeat")] != findings[(case, "first")]:
            raise ValueError(f"Native SPI bias-array {case} findings changed between exports")
        log.event(
            f"spi-bias-array-fixture/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            contract_sha256=contract_sha256,
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            array_check_status=array_statuses[(case, "first")],
            finding_subjects=";".join(findings[(case, "first")]) or "none",
            repeatable="true",
        )
    log.event(
        "spi-bias-array-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
