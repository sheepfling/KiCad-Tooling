"""Exact-version native fixtures for direct GPIO control-input voltage review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import write_model
from .hwrepo.design_lint_types import Candidate
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.native_report_parsing import read_netlist
from .hwrepo.netlist_contract_models import NetlistContract
from .hwrepo.power_gpio_control_voltage import (
    gpio_to_control_input_voltage_candidates,
)

RULE_ID = "power.gpio_to_control_input_voltage_review"
FIXTURE_SOURCE_HASHES = {
    "control": "8fbe7219de30483919845ad3d008d56e39e52c055db3d42a59b0b5c2e79727fe",
    "fault": "066861e84e4dfebeac615ee62b6207c411267ff13b828a033ab32a382ca56437",
}


def _normalized_netlist_sha256(observed: NetlistContract) -> str:
    payload = json.dumps(
        observed.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _finding_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    return tuple(
        candidate
        for candidate in gpio_to_control_input_voltage_candidates(observed)
        if candidate.rule_id == RULE_ID
    )


def gpio_control_voltage_native_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Export and evaluate synthetic fault/control schematics twice with pinned KiCad."""

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"GPIO control-voltage fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/gpio-control-voltage-native"
    )
    fixtures = {case: fixture_root / f"{case}.kicad_sch" for case in FIXTURE_SOURCE_HASHES}
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    if source_hashes != FIXTURE_SOURCE_HASHES:
        raise ValueError("GPIO control-voltage fixture sources differ from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"native-gpio-control-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        copied = inputs / fixture.name
        shutil.copyfile(fixture, copied)
        if digest(copied) != source_hashes[case]:
            raise ValueError(f"Synthetic GPIO {case} fixture changed while preparing native input")
    output = scratch / "output"
    output.mkdir()

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{config.kicad_version}"\n'
        "for case in control fault; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml \\\n"
        '      --output "/output/${case}.${run}.netlist.xml" \\\n'
        '      "/fixtures/${case}.kicad_sch"\n'
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
        "HOME=/tmp/kicad-gpio-control-fixtures",
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
        "gpio-control-voltage-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    command_receipt = (scratch / "native.command.json").relative_to(root).as_posix()
    if command.returncode != 0 or command.error is not None:
        log.event(
            "gpio-control-voltage-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=command_receipt,
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native GPIO control-voltage export failed: {command.stderr or command.error}"
        )
    log.event(
        "gpio-control-voltage-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in FIXTURE_SOURCE_HASHES),
        command_receipt=command_receipt,
    )

    for case in FIXTURE_SOURCE_HASHES:
        if digest(fixtures[case]) != source_hashes[case]:
            raise ValueError(f"Synthetic GPIO {case} fixture changed during native export")
        observations: dict[str, NetlistContract] = {}
        normalized_hashes: dict[str, str] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native GPIO fixture omitted {netlist_path.name}")
            observed = read_netlist(netlist_path)
            observations[run] = observed
            normalized_hashes[run] = _normalized_netlist_sha256(observed)
        if normalized_hashes["first"] != normalized_hashes["repeat"]:
            raise ValueError(f"Native GPIO {case} exports differ after typed normalization")

        findings = _finding_candidates(observations["first"])
        expected_count = 1 if case == "fault" else 0
        if len(findings) != expected_count:
            raise ValueError(
                f"Native GPIO {case} exported {len(findings)} findings; expected {expected_count}"
            )
        if case == "fault":
            evidence = findings[0].evidence
            if (
                evidence.get("GPIO_output") != ("U1.1: GPIO0 (Synthetic:GpioController)",)
                or evidence.get("control_input") != ("U2.1: EN (Synthetic:ControlReceiver)",)
                or evidence.get("output_supply_label") != ("+5V: 5 V",)
                or evidence.get("input_supply_label") != ("+3V3: 3.3 V",)
            ):
                raise ValueError(
                    "Native GPIO fault evidence differs from the reviewed pin/rail map"
                )

        log.event(
            f"gpio-control-voltage-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes["first"],
            repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
            findings=len(findings),
            evidence=json.dumps(dict(findings[0].evidence), sort_keys=True) if findings else "none",
            repeatable="true",
            command_receipt=command_receipt,
        )
