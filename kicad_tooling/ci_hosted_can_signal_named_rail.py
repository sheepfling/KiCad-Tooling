"""Digest-pinned native fixtures for CAN signals assigned to named rails."""

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
from typing import Literal

from .ci_hosted_can_tx_rx_same_net import CAN_TX_RX_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import DesignLintPolicy
from .hwrepo.native_report_parsing import read_netlist

CAN_SIGNAL_NAMED_RAIL_TOOLCHAINS = CAN_TX_RX_NATIVE_TOOLCHAINS
_SIGNAL_RULE_ID = "bus.can_signal_on_named_rail"
_SIGNAL_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "fault": "bd3ab9e52d76f8a0befdc186c3e61d56faf8ea46b066cd0be5fc8703a436cc6c",
        "control": "d3c57cce862e757ba2473486fdbcfd88f2faf9cb583f1b9a9ea897a53b36fb86",
    }
)
_LINE_RULE_ID = "bus.can_line_on_named_rail"
_LINE_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "fault": "b35e61b7b03a30af1df1fcbba40e6cfe3fd3e59c3a4022929f37fba42bace526",
        "control": "9f4fa5661ffbc0552ecd89657663b14f9377dbcbf4e3bca2370958763b9f7ce8",
    }
)
_MODULE_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "fault": "ac85d23bf274c93411a8960c81b7abeee3d8df3c4438b5a992431e4b7d229532",
        "control": "36851f1d1b838183e758a734e65565c89994a075574784b3280e028b27080a4c",
    }
)


def can_signal_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat source-bound exports for CAN signal named-rail fixtures."""
    _can_named_rail_fixture_lane(root, version=version, image=image, log=log, feature="signal")


def can_line_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat source-bound exports for CANH/CANL named-rail fixtures."""
    _can_named_rail_fixture_lane(root, version=version, image=image, log=log, feature="line")


def can_module_signal_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat exports for generic TXD/RXD pins on an identified CAN module."""
    _can_named_rail_fixture_lane(root, version=version, image=image, log=log, feature="module")


def _can_named_rail_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
    feature: Literal["signal", "line", "module"],
) -> None:
    """Share exact-version native export and lint checks across CAN rail heuristics."""
    root = root.resolve()
    if (version, image) not in CAN_SIGNAL_NAMED_RAIL_TOOLCHAINS:
        raise ValueError(f"CAN named-rail coverage is not configured for KiCad {version}")
    pinned = pinned_image(image)
    if feature == "signal":
        rule_id = _SIGNAL_RULE_ID
        fixture_directory = "can-signal-named-rail"
        stage_prefix = "can-signal-named-rail-fixture"
        reviewed_hashes = _SIGNAL_SOURCE_HASHES
        expected_functions = {
            "U1.1": "CAN1_TX",
            "U1.2": "CAN1_RX",
            "J1.1": "CAN2_TX",
            "J1.2": "GND_B",
        }
        expected_nets = {
            "fault": {"GND": {"U1.1", "J1.1"}, "CAN1_RX": {"U1.2"}, "GND_B": {"J1.2"}},
            "control": {
                "CAN1_TX": {"U1.1"},
                "CAN1_RX": {"U1.2"},
                "CAN2_TX": {"J1.1"},
                "GND_B": {"J1.2"},
            },
        }
        expected_subjects = {
            "fault": ("J1.1: CAN2_TX on return-like net GND;U1.1: CAN1_TX on return-like net GND"),
            "control": "none",
        }
        expected_inventories = {"U1": ("1", "2"), "J1": ("1", "2")}
    elif feature == "line":
        rule_id = _LINE_RULE_ID
        fixture_directory = "can-line-named-rail"
        stage_prefix = "can-line-named-rail-fixture"
        reviewed_hashes = _LINE_SOURCE_HASHES
        expected_functions = {
            "U1.1": "CANH",
            "U1.2": "CANL",
            "J1.1": "CANH",
            "J1.2": "CANL",
        }
        expected_nets = {
            "fault": {"GND": {"U1.1", "J1.1"}, "+3V3": {"U1.2", "J1.2"}},
            "control": {
                "CANH_BUS": {"U1.1", "J1.1"},
                "CANL_BUS": {"U1.2", "J1.2"},
            },
        }
        expected_subjects = {
            "fault": (
                "J1.1: CANH on return-like net GND;J1.2: CANL on supply-like net +3V3;"
                "U1.1: CANH on return-like net GND;U1.2: CANL on supply-like net +3V3"
            ),
            "control": "none",
        }
        expected_inventories = {"U1": ("1", "2"), "J1": ("1", "2")}
    else:
        rule_id = _SIGNAL_RULE_ID
        fixture_directory = "can-module-signal-named-rail"
        stage_prefix = "can-module-signal-named-rail-fixture"
        reviewed_hashes = _MODULE_SOURCE_HASHES
        expected_functions = {
            "U1.1": "CAN1_TX",
            "U1.2": "CAN1_RX",
            "J1.1": "TXD",
            "J1.2": "RXD",
        }
        expected_nets = {
            "fault": {
                "CAN1_RX": {"U1.2"},
                "CAN1_TX": {"U1.1"},
                "GND": {"J1.1"},
                "+3V3": {"J1.2"},
            },
            "control": {
                "CAN1_RX": {"U1.2"},
                "CAN1_TX": {"U1.1"},
                "CAN_RXD": {"J1.2"},
                "CAN_TXD": {"J1.1"},
            },
        }
        expected_subjects = {
            "fault": ("J1.1: TXD on return-like net GND;J1.2: RXD on supply-like net +3V3"),
            "control": "none",
        }
        expected_inventories = {"U1": ("1", "2"), "J1": ("1", "2")}
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint" / fixture_directory
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in ("fault", "control")}
    source_hashes = {case: digest(source) for case, source in sources.items()}
    if source_hashes != reviewed_hashes:
        raise ValueError(f"CAN {feature} named-rail sources differ from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"can-{feature}-named-rail-{version}-", dir=log.directory.resolve())
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
        f"HOME=/tmp/kicad-{feature}-named-rail",
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
            f"Native CAN {feature} named-rail export failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    results: dict[tuple[str, str], tuple[str, str, str]] = {}
    for case, source in sources.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted CAN {feature} named-rail {case} evidence")
            observed = read_netlist(netlist_path)
            if feature == "module" and observed.components["J1"].value != "CAN transceiver module":
                raise ValueError(f"Native CAN module {case} identity evidence changed")
            if any(
                observed.component_pin_numbers.get(reference) != pins
                for reference, pins in expected_inventories.items()
            ):
                raise ValueError(f"Native CAN {feature} {case} pin inventory changed")
            if observed.pin_functions != expected_functions:
                raise ValueError(f"Native CAN {feature} {case} pin functions changed")
            if any(
                set(observed.nets.get(net, ())) != pins for net, pins in expected_nets[case].items()
            ):
                raise ValueError(f"Native CAN {feature} named-rail {case} net assignments changed")
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
                raise ValueError(f"Native ERC reported errors for CAN {feature} named-rail {case}")
            project_id = f"synthetic-can-{feature}-named-rail-{case}"
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
            subjects = tuple(item.subject for item in report.findings if item.rule_id == rule_id)
            results[(case, run)] = (";".join(subjects) or "none", report.status, "none")

    for case in sources:
        first = normalized_hashes[(case, "first")]
        repeat = normalized_hashes[(case, "repeat")]
        if first != repeat:
            raise ValueError(f"Native CAN {feature} named-rail {case} exports are not repeatable")
        expected = expected_subjects[case]
        if (
            results[(case, "first")][0] != expected
            or results[(case, "repeat")] != results[(case, "first")]
        ):
            raise ValueError(
                f"Native CAN {feature} named-rail {case} findings do not match the fixture"
            )
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
            subjects=expected,
            lint_status=results[(case, "first")][1],
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
