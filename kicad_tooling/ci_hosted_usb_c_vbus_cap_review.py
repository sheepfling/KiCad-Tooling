"""Exact-version KiCad fixture lane for USB-C VBUS capacitor review."""

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
from .hwrepo.usb_c_ports import UsbCPortRosterContext

RULE_ID = "bus.usb_c_vbus_capacitance_review"
EXPECTED_FIXTURE_SHA256 = "5368f8bcff7fd3500e80708bab0b5b7283c5d4e9b95a9356082c1addc7756ea6"


def usb_c_vbus_capacitance_review_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
) -> None:
    """Repeat native exports and verify one absent-cap fault plus a cap control."""
    if (version, image) not in KICAD_10_NATIVE_TOOLCHAINS:
        raise ValueError(f"USB-C VBUS capacitor review does not cover KiCad {version}")
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint/usb-c-vbus-cap-review"
    source = fixture_root / "connector-pair.kicad_sch"
    source_hash = digest(source)
    if source_hash != EXPECTED_FIXTURE_SHA256:
        raise ValueError("USB-C VBUS review fixture differs from its reviewed source hash")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"usb-c-vbus-cap-review-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    staged_source = inputs / source.name
    shutil.copyfile(source, staged_source)
    if digest(staged_source) != source_hash:
        raise ValueError("USB-C VBUS review fixture changed while staging")
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    pinned = pinned_image(image)
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{version}"\n'
        "for run in first repeat; do\n"
        '  kicad-cli sch export netlist --format kicadxml --output "/output/$run.netlist.xml" '
        '"/fixtures/connector-pair.kicad_sch"\n'
        '  kicad-cli sch erc --format json --severity-all --output "/output/$run.erc.json" '
        '"/fixtures/connector-pair.kicad_sch"\n'
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
        "HOME=/tmp/kicad-usb-c-vbus-cap-review",
        "-v",
        f"{inputs.resolve()}:/fixtures:ro",
        "-v",
        f"{output.resolve()}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    log.event(
        "usb-c-vbus-cap-review/native-export",
        "START",
        project=f"synthetic-kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root.resolve(), argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        error = command.stderr or command.error or f"exit {command.returncode}"
        log.event(
            "usb-c-vbus-cap-review/native-export",
            "FAIL",
            project=f"synthetic-kicad-{version}",
            kicad_version=version,
            image=pinned,
            error=error,
        )
        raise ValueError(f"USB-C VBUS review fixture export failed: {error}")

    normalized_hashes: dict[str, str] = {}
    raw_hashes: dict[str, str] = {}
    expected_functions = {
        "J1.1": "CC1",
        "J1.2": "CC2",
        "J1.3": "VBUS",
        "J1.4": "GND",
        "J2.1": "CC1",
        "J2.2": "CC2",
        "J2.3": "VBUS",
        "J2.4": "GND",
    }
    target_subjects: tuple[str, ...] | None = None
    warning_count: int | None = None
    for run in ("first", "repeat"):
        netlist_path = output / f"{run}.netlist.xml"
        erc_path = output / f"{run}.erc.json"
        observed = read_netlist(netlist_path)
        raw_hashes[run] = digest(netlist_path)
        normalized = json.dumps(
            observed.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
        if observed.component_symbols.get("C1") != "Device:C":
            raise ValueError("Native control omitted the exact fitted Device:C symbol identity")
        if observed.component_pin_numbers.get("C1") != ("1", "2"):
            raise ValueError("Native control omitted the complete C1 pin inventory")
        if any(
            observed.pin_functions.get(pin) != function
            for pin, function in expected_functions.items()
        ):
            raise ValueError("Native export omitted one or more USB-C port pin functions")
        native_assignments = {
            pin: tuple(sorted(net for net, pins in observed.nets.items() if pin in pins))
            for pin in ("J1.3", "J1.4", "J2.3", "J2.4", "C1.1", "C1.2")
        }
        if native_assignments != {
            "J1.3": ("VBUS_J1",),
            "J1.4": ("GND_J1",),
            "J2.3": ("VBUS_J2",),
            "J2.4": ("GND_J2",),
            "C1.1": ("VBUS_J2",),
            "C1.2": ("GND_J2",),
        }:
            raise ValueError(f"Native USB-C port/cap assignments differ: {native_assignments}")
        erc = read_kicad_erc_report(erc_path)
        errors = tuple(item for item in erc.violations if item.severity == "error")
        if errors:
            raise ValueError(f"Native USB-C VBUS review fixture has ERC errors: {errors}")
        warning_count = sum(item.severity == "warning" for item in erc.violations)
        report = evaluate(
            f"synthetic-usb-c-vbus-cap-{version}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-usb-c-vbus-cap-{version}",
                observed=observed,
                netlist_sha256=raw_hashes[run],
            ),
            DesignLintPolicy(),
            usb_c_port_roster=UsbCPortRosterContext(state="not_configured"),
        )
        subjects = tuple(item.subject for item in report.findings if item.rule_id == RULE_ID)
        if subjects != ("J1: USB-C VBUS has no recognized return capacitor",):
            raise ValueError(f"Native lint expected only J1's missing-cap prompt; got {subjects}")
        if run == "first":
            target_subjects = subjects
        elif subjects != target_subjects:
            raise ValueError("Repeated native lint evaluation changed the USB-C VBUS candidate")

    if normalized_hashes["first"] != normalized_hashes["repeat"]:
        raise ValueError("Native USB-C VBUS netlist changed after normalized repeat export")
    if digest(source) != source_hash:
        raise ValueError("USB-C VBUS review source changed during native export")
    log.event(
        "usb-c-vbus-cap-review/native-export",
        "PASS",
        project=f"synthetic-kicad-{version}",
        kicad_version=version,
        image=pinned,
        source_sha256=source_hash,
        netlist_sha256=raw_hashes["first"],
        repeat_netlist_sha256=raw_hashes["repeat"],
        normalized_netlist_sha256=normalized_hashes["first"],
        repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
        finding_subjects=";".join(target_subjects or ()),
        erc_errors="none",
        erc_warnings=warning_count or 0,
        repeatable="true",
        command_receipt=receipt.relative_to(root.resolve()).as_posix(),
    )
