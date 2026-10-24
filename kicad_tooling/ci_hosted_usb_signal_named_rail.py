"""Digest-pinned native fixtures for USB data pins assigned to named rails."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

USB_SIGNAL_NAMED_RAIL_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
_SIGNAL_RULE_ID = "bus.usb_signal_on_named_rail"
_SIGNAL_SOURCE_HASHES = {
    "control": "30270e674ad045a2ebc238b6f632ed455c04f549d6c53061f74151c77d160002",
    "fault": "9330de44f6600afd92d2aa7199eced1ca6e892ed74fb5765f20a1832eef97148",
}
_CC_RULE_ID = "bus.usb_c_cc_signal_on_named_rail"
_CC_SOURCE_HASHES = {
    "fault": "9f484af298d4a8bbd9e779e7bf2659098f3b05473343411dd5698c4204fa90b2",
    "control": "e49f410117e4ef7a2d3bead575c68cc184c05efe9c42a3f6bea29c7bab467b5a",
}


def usb_signal_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports for USB data pins assigned to a named rail."""
    _usb_named_rail_fixture_lane(root, version=version, image=image, log=log, feature="signal")


def usb_c_cc_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports for USB-C controller CC pins assigned to rails."""
    _usb_named_rail_fixture_lane(root, version=version, image=image, log=log, feature="cc")


def _usb_named_rail_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
    feature: Literal["signal", "cc"],
) -> None:
    """Share source-bound exact-version exports for USB named-rail heuristics."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in USB_SIGNAL_NAMED_RAIL_TOOLCHAINS:
        raise ValueError(f"USB named-rail coverage is not configured for KiCad {version}")
    pinned = pinned_image(image)
    if feature == "signal":
        rule_id = _SIGNAL_RULE_ID
        fixture_directory = "usb-signal-named-rail"
        stage_prefix = "usb-signal-named-rail-fixture"
        reviewed_hashes = _SIGNAL_SOURCE_HASHES
        expected_pin_functions = None
        expected_nets = {
            "fault": {
                "GND": ("U1.1",),
                "USB_D-": ("J1.2", "U1.2"),
                "USB_D+": ("J1.1",),
            },
            "control": {
                "USB_D+": ("J1.1", "U1.1"),
                "USB_D-": ("J1.2", "U1.2"),
            },
        }
        expected_subjects = {
            "fault": ("U1.1: USB_DP on return-like net GND",),
            "control": (),
        }
    else:
        rule_id = _CC_RULE_ID
        fixture_directory = "usb-c-cc-named-rail"
        stage_prefix = "usb-c-cc-named-rail-fixture"
        reviewed_hashes = _CC_SOURCE_HASHES
        expected_pin_functions = {
            "J1.1": "CC1",
            "J1.2": "CC2",
            "U1.1": "CC1",
            "U1.2": "CC2",
        }
        expected_nets = {
            "fault": {"GND": ("J1.1", "U1.1"), "+3V3": ("J1.2", "U1.2")},
            "control": {"CC1_BUS": ("J1.1", "U1.1"), "CC2_BUS": ("J1.2", "U1.2")},
        }
        expected_subjects = {
            "fault": (
                "U1.1: CC1 on return-like net GND",
                "U1.2: CC2 on supply-like net +3V3",
            ),
            "control": (),
        }
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint" / fixture_directory
    )
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in ("fault", "control")}
    source_hashes = {case: digest(source) for case, source in sources.items()}
    if source_hashes != reviewed_hashes:
        raise ValueError(f"USB {feature} named-rail sources differ from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"usb-{feature}-named-rail-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    output = scratch / "output"
    output.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
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
        f"HOME=/tmp/kicad-usb-{feature}-named-rail",
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
        f"{stage_prefix}/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(
            f"Native USB {feature} named-rail export failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    findings: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted USB {feature} named-rail {case} evidence")
            observed = read_netlist(netlist_path)
            if (
                expected_pin_functions is not None
                and observed.pin_functions != expected_pin_functions
            ):
                raise ValueError(f"Native USB {feature} {case} pin functions changed")
            if any(observed.nets.get(net) != pins for net, pins in expected_nets[case].items()):
                raise ValueError(f"Native USB {feature} named-rail {case} net assignments changed")
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version or any(
                item.severity == "error" for item in erc.violations
            ):
                raise ValueError(f"Native ERC reported errors for USB {feature} named-rail {case}")
            project_id = f"synthetic-usb-{feature}-named-rail-{case}"
            report = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=digest(netlist_path),
                ),
                DesignLintPolicy(),
            )
            findings[(case, run)] = tuple(
                item.subject for item in report.findings if item.rule_id == rule_id
            )

    for case in sources:
        first = normalized_hashes[(case, "first")]
        repeat = normalized_hashes[(case, "repeat")]
        expected = expected_subjects[case]
        if first != repeat or findings[(case, "first")] != expected:
            raise ValueError(
                f"Native USB {feature} named-rail {case} result differs from its fixture"
            )
        if findings[(case, "repeat")] != findings[(case, "first")]:
            raise ValueError(f"Native USB {feature} named-rail {case} findings are not repeatable")
        log.event(
            f"{stage_prefix}/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=first,
            repeat_normalized_netlist_sha256=repeat,
            erc_errors="none",
            repeatable="true",
            subjects=";".join(expected) if expected else "none",
        )
    log.event(
        f"{stage_prefix}/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
