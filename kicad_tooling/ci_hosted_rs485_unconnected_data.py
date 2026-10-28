"""Digest-pinned native fixtures for open RS-485 data-pin review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy, DesignLintRuleOverride
from .validate import read_netlist

RS485_UNCONNECTED_DATA_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
_RULE_ID = "bus.rs485_unconnected_data_pin"
_SOURCE_HASHES = MappingProxyType(
    {
        "fault": "39ec0fb43f3175204f550a71506a7b5fd063cf71759f2786ea0bf765f6077c5f",
        "control": "fa1ee6811e6351691e186c70411c6fbb139acbbebbb99e556136ad36818ea588",
    }
)


def rs485_unconnected_data_pin_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat exact native netlist/ERC exports for open and connected RS-485 data pins."""
    root = root.resolve()
    if (version, image) not in RS485_UNCONNECTED_DATA_TOOLCHAINS:
        raise ValueError(f"RS-485 open-data fixtures do not cover KiCad {version} with this image")
    pinned = pinned_image(image)
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/rs485-unconnected-data-native"
    )
    sources = {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
    source_hashes = MappingProxyType({case: digest(source) for case, source in sources.items()})
    if source_hashes != _SOURCE_HASHES:
        raise ValueError("RS-485 open-data sources differ from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"rs485-open-data-{version}-", dir=log.directory.resolve())
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
        "HOME=/tmp/kicad-rs485-open-data",
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
        "rs485-unconnected-data-fixture/native-export",
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
            f"Native RS-485 open-data export failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    default_subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    default_dispositions: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {}
    review_subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    for case, source in sources.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted RS-485 open-data {case} evidence")
            observed = read_netlist(netlist_path)
            if observed.component_pin_numbers.get("U1") != ("1", "2"):
                raise ValueError(f"Native RS-485 open-data {case} lost pin inventory")
            if (
                observed.pin_functions.get("U1.1") != "D"
                or observed.pin_functions.get("U1.2") != "R"
            ):
                raise ValueError(f"Native RS-485 open-data {case} lost D/R pin functions")
            expected_nets = (
                {"HOST_TX": ("U1.1",)}
                if case == "fault"
                else {"HOST_TX": ("U1.1",), "HOST_RX": ("U1.2",)}
            )
            if any(observed.nets.get(net) != pins for net, pins in expected_nets.items()):
                actual_nets = {net: observed.nets.get(net) for net in expected_nets}
                raise ValueError(
                    f"Native RS-485 open-data {case} assignments changed: "
                    f"expected={expected_nets!r}, actual={actual_nets!r}"
                )
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
                raise ValueError(f"Native ERC reported errors for RS-485 open-data {case}")

            project_id = f"synthetic-rs485-unconnected-data-{case}"
            coach_report = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=digest(netlist_path),
            )
            default_report = evaluate(project_id, coach_report, DesignLintPolicy())
            review_report = evaluate(
                project_id,
                coach_report,
                DesignLintPolicy(
                    rules=(
                        DesignLintRuleOverride(
                            rule_id=_RULE_ID,
                            mode="review",
                            reason="Native open-data regression fixture",
                        ),
                    )
                ),
            )
            default_subjects[(case, run)] = tuple(
                item.subject for item in default_report.findings if item.rule_id == _RULE_ID
            )
            default_dispositions[(case, run)] = tuple(
                (item.mode, item.disposition)
                for item in default_report.findings
                if item.rule_id == _RULE_ID
            )
            review_subjects[(case, run)] = tuple(
                item.subject for item in review_report.findings if item.rule_id == _RULE_ID
            )

    expected_review = {"fault": ("U1.2: R",), "control": ()}
    for case in sources:
        for run in ("first", "repeat"):
            if normalized_hashes[(case, run)] != normalized_hashes[(case, "first")]:
                raise ValueError(f"Native RS-485 open-data {case} exports are not repeatable")
            if review_subjects[(case, run)] != expected_review[case]:
                raise ValueError(f"Native RS-485 open-data {case} review result changed")
            if default_subjects[(case, run)] != expected_review[case]:
                raise ValueError(f"Native RS-485 open-data {case} default-off evidence changed")
            expected_default = (("off", "RULE_OFF"),) if case == "fault" else ()
            if default_dispositions[(case, run)] != expected_default:
                raise ValueError(f"Native RS-485 open-data {case} default policy changed")
            log.event(
                f"rs485-unconnected-data-fixture/{case}",
                "PASS",
                project=f"kicad-{version}",
                kicad_version=version,
                image=pinned,
                source_sha256=source_hashes[case],
                normalized_netlist_sha256=normalized_hashes[(case, run)],
                repeatable="true",
                default_mode="off",
                review_subjects=";".join(review_subjects[(case, run)]) or "none",
                erc_errors="none",
            )
    log.event(
        "rs485-unconnected-data-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
