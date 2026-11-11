"""Exact-version native validation of global schematic ERC suppression."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.evidence import digest


def _pin_not_connected_records(
    path: Path, version: str
) -> tuple[tuple[str, bool, tuple[str, ...]], ...]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("kicad_version") != version:
        raise ValueError("Native ERC report does not identify the configured KiCad version")
    violations = [
        violation
        for sheet in document.get("sheets", [])
        for violation in sheet.get("violations", [])
    ]
    return tuple(
        sorted(
            (
                item.get("severity", ""),
                item.get("excluded", False),
                tuple(sorted(detail.get("uuid", "") for detail in item.get("items", []))),
            )
            for item in violations
            if item.get("type") == "pin_not_connected"
        )
    )


def schematic_erc_global_severity_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Prove Ignore hides a known pin error and Error restores it in native ERC."""
    root = root.resolve()
    toolchains = {pinned_image: version for version, pinned_image in KICAD_10_NATIVE_TOOLCHAINS}
    version = toolchains.get(image)
    if version is None:
        raise ValueError(f"ERC global severity fixture does not cover image {image}")

    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    schematic = fixture_root / "near-miss-pin-line.kicad_sch"
    settings_root = fixture_root / "schematic-erc-global-severity"
    warning_settings = fixture_root / "schematic-erc-warning-downgrade/fault.kicad_pro"
    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"schematic-erc-global-severity-{version}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    output = scratch / "output"
    output.mkdir()
    cases = (
        ("ignored", settings_root / "fault.kicad_pro"),
        ("active", settings_root / "control.kicad_pro"),
        ("downgraded", warning_settings),
    )
    for case, settings_file in cases:
        case_root = inputs / case
        case_root.mkdir()
        shutil.copyfile(schematic, case_root / schematic.name)
        shutil.copyfile(settings_file, case_root / f"{schematic.stem}.kicad_pro")

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        f'test "$actual" = "{version}"\n'
        "for case in ignored active downgraded; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch erc --format json --output "
        '"/output/$case.$run.erc.json" '
        '"/fixtures/$case/near-miss-pin-line.kicad_sch"\n'
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
        "HOME=/tmp/kicad-erc-global-severity",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        image,
        "-ec",
        script,
    )
    log.event(
        "schematic-erc-global-severity/native-export",
        "START",
        project=project,
        kicad_version=version,
        image=image,
    )
    log.run("native-erc-global-severity-export", argv, cwd=root, merge_stderr=True)

    normalized = {
        case: {
            run: _pin_not_connected_records(output / f"{case}.{run}.erc.json", version)
            for run in ("first", "repeat")
        }
        for case in ("ignored", "active", "downgraded")
    }
    expected_active_pins = (
        ("error", False, ("a0000000-0000-4000-8000-000000000003",)),
        ("error", False, ("a0000000-0000-4000-8000-000000000004",)),
    )
    expected_downgraded_pins = tuple(("warning", False, item[2]) for item in expected_active_pins)
    if any(records for records in normalized["ignored"].values()):
        raise ValueError("Native ERC still reports pin_not_connected when its rule is ignored")
    if any(records != expected_active_pins for records in normalized["active"].values()):
        raise ValueError("Native ERC did not report the control pin_not_connected error")
    if any(records != expected_downgraded_pins for records in normalized["downgraded"].values()):
        raise ValueError("Native ERC did not lower pin_not_connected from Error to Warning")
    if any(records["first"] != records["repeat"] for records in normalized.values()):
        raise ValueError("Native ERC global severity recognition is not repeatable")
    log.event(
        "schematic-erc-global-severity/native-export",
        "PASS",
        project=project,
        kicad_version=version,
        image=image,
        ignored_pin_not_connected="absent",
        active_pin_not_connected="error",
        downgraded_pin_not_connected="warning",
        repeatable="true",
        ignored_settings_sha256=digest(settings_root / "fault.kicad_pro"),
        active_settings_sha256=digest(settings_root / "control.kicad_pro"),
        downgraded_settings_sha256=digest(warning_settings),
        schematic_sha256=digest(schematic),
    )
