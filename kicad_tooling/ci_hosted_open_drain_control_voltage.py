"""Exact-version native fixtures for open-collector control pull-up review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from .ci_hosted_support import HostedLog, normalized_netlist_bytes, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import write_model
from .hwrepo.design_lint_types import Candidate
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.native_report_parsing import read_netlist
from .hwrepo.netlist_contract_models import NetlistContract
from .hwrepo.power_open_drain_control_voltage import open_drain_control_pullup_voltage_candidates

RULE_ID = "power.open_drain_control_input_pullup_voltage_review"
FIXTURE_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "control": "51338a18e26c6150e24a799d86c6333850e57c4ff67de94c1b07c5177482d5eb",
        "fault": "3305d61e5e888ff2addaad4d216245af276439476fc62b64542d9ff31ff5c515",
    }
)
EXPECTED_FAULT_EVIDENCE: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "signal_net": ("CONTROL_SIGNAL",),
        "open_collector_output": ("U1.1: GPIO0 (Synthetic:GpioController)",),
        "control_input": ("U2.1: EN (Synthetic:ControlReceiver)",),
        "pullup_paths": ("R1 (10000 Ω): CONTROL_SIGNAL ↔ +5V",),
        "pullup_rail_label": ("+5V: 5 V",),
        "driver_supply_label": ("+3V3: 3.3 V",),
        "receiver_supply_label": ("+3V3: 3.3 V",),
        "pullup_label_relations": (
            "pullup_higher_than_driver",
            "pullup_higher_than_receiver",
        ),
    }
)


def _rule_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    return tuple(
        candidate
        for candidate in open_drain_control_pullup_voltage_candidates(observed)
        if candidate.rule_id == RULE_ID
    )


def _expected_findings(case: str, observed: NetlistContract) -> tuple[Candidate, ...]:
    findings = _rule_candidates(observed)
    expected_count = 0 if case == "control" else 1
    if len(findings) != expected_count:
        raise ValueError(
            f"Native open-drain control {case} exported {len(findings)} findings; "
            f"expected {expected_count}"
        )
    if case == "fault" and dict(findings[0].evidence) != EXPECTED_FAULT_EVIDENCE:
        raise ValueError(
            "Native open-drain control fault evidence differs from its reviewed pin map"
        )
    return findings


def open_drain_control_voltage_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Export and evaluate the synthetic open-drain fault/control pair twice."""

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Open-drain control-voltage fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/open-drain-control-voltage-native"
    )
    fixtures = {case: fixture_root / f"{case}.kicad_sch" for case in FIXTURE_SOURCE_HASHES}
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    if source_hashes != FIXTURE_SOURCE_HASHES:
        raise ValueError("Open-drain control fixture sources differ from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"native-open-drain-control-{project}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        copied = inputs / fixture.name
        shutil.copyfile(fixture, copied)
        if digest(copied) != source_hashes[case]:
            raise ValueError(
                f"Synthetic open-drain {case} fixture changed while staging native input"
            )
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
        f"for case in {' '.join(FIXTURE_SOURCE_HASHES)}; do\n"
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
        "HOME=/tmp/kicad-open-drain-control-fixtures",
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
        "open-drain-control-voltage-fixture/native-export",
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
            "open-drain-control-voltage-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=command_receipt,
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native open-drain control export failed: {command.stderr or command.error}"
        )
    log.event(
        "open-drain-control-voltage-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in FIXTURE_SOURCE_HASHES),
        command_receipt=command_receipt,
    )

    for case in FIXTURE_SOURCE_HASHES:
        if digest(fixtures[case]) != source_hashes[case]:
            raise ValueError(f"Synthetic open-drain {case} fixture changed during native export")
        observations: dict[str, NetlistContract] = {}
        hashes: dict[str, str] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native open-drain fixture omitted {netlist_path.name}")
            observed = read_netlist(netlist_path)
            observations[run] = observed
            hashes[run] = hashlib.sha256(normalized_netlist_bytes(observed)).hexdigest()
        if hashes["first"] != hashes["repeat"]:
            raise ValueError(f"Native open-drain control {case} exports differ after normalization")
        findings = _expected_findings(case, observations["first"])
        log.event(
            f"open-drain-control-voltage-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=hashes["first"],
            repeat_normalized_netlist_sha256=hashes["repeat"],
            findings=len(findings),
            evidence=json.dumps(dict(findings[0].evidence), sort_keys=True) if findings else "none",
            repeatable="true",
            command_receipt=command_receipt,
        )
