"""Exact-version native validation of persisted schematic ERC exclusions."""

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

_EXPECTED_EXCLUSIONS = (
    ("label_dangling", "", True, "error"),
    ("pin_not_connected", "Synthetic intentionally-unused test point.", True, "error"),
)


def _normalized_exclusions(path: Path, version: str) -> tuple[tuple[str, str, bool, str], ...]:
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
                item.get("type", ""),
                item.get("comment", ""),
                item.get("excluded", False),
                item.get("severity", ""),
            )
            for item in violations
        )
    )


def schematic_erc_exclusion_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Require both real KiCad images to reload and identify saved exclusions."""
    root = root.resolve()
    toolchains = {pinned_image: version for version, pinned_image in KICAD_10_NATIVE_TOOLCHAINS}
    version = toolchains.get(image)
    if version is None:
        raise ValueError(f"Schematic ERC exclusion fixture does not cover image {image}")

    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    source = fixture_root / "usb-superspeed-peer-reference-native/control.kicad_sch"
    settings = fixture_root / "schematic-erc-exclusions/fault.kicad_pro"
    scratch = Path(
        tempfile.mkdtemp(prefix=f"schematic-erc-exclusions-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    output = scratch / "output"
    output.mkdir()
    shutil.copyfile(source, inputs / "fault.kicad_sch")
    shutil.copyfile(settings, inputs / "fault.kicad_pro")

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        f'test "$actual" = "{version}"\n'
        "for run in first repeat; do\n"
        "  kicad-cli sch erc --format json --severity-exclusions "
        '--output "/output/$run.erc.json" "/fixtures/fault.kicad_sch"\n'
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
        "HOME=/tmp/kicad-erc-exclusions",
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
        "schematic-erc-exclusion-fixture/native-export",
        "START",
        project=project,
        kicad_version=version,
        image=image,
    )
    log.run("native-erc-exclusion-export", argv, cwd=root, merge_stderr=True)

    normalized = {
        run: _normalized_exclusions(output / f"{run}.erc.json", version)
        for run in ("first", "repeat")
    }
    if any(records != _EXPECTED_EXCLUSIONS for records in normalized.values()):
        raise ValueError("Native KiCad ERC exclusions do not match the saved synthetic markers")
    if normalized["first"] != normalized["repeat"]:
        raise ValueError("Native ERC exclusion recognition is not repeatable")
    log.event(
        "schematic-erc-exclusion-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=version,
        image=image,
        project_settings_sha256=hashlib.sha256(settings.read_bytes()).hexdigest(),
        schematic_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        excluded_types="label_dangling,pin_not_connected",
        repeatable="true",
    )
