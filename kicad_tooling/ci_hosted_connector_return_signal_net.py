"""Exact-version native acceptance for connector return/signal sharing."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, normalized_netlist_bytes, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import DesignLintPolicy
from .hwrepo.native_report_parsing import read_netlist

_RULE_ID = "connector.return_pin_shares_protocol_signal_net"
_FIXTURE_HASHES = {
    "fault": "8ac8180b2d26c0352d4262cddb74e86c5f346c76b905d7d9b1a3b8300493f5a0",
    "control": "675be8d054c2aad583f023362a77e1a90d36c5c56e2b29ed3e48b933c36966c8",
}


def connector_return_signal_net_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Export synthetic fault/control schematics twice with an exact KiCad image."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its toolchain")
    if (config.kicad_version, config.image) not in KICAD_10_NATIVE_TOOLCHAINS:
        raise ValueError(
            f"Connector return/signal fixtures do not cover KiCad {config.kicad_version}"
        )

    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/connector-return-signal-net"
    )
    cases = ("fault", "control")
    source_hashes = {case: digest(fixture_root / f"{case}.kicad_sch") for case in cases}
    if source_hashes != _FIXTURE_HASHES:
        raise ValueError("Synthetic connector return/signal fixture differs from reviewed source")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"connector-return-signal-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case in cases:
        source = fixture_root / f"{case}.kicad_sch"
        staged = inputs / source.name
        shutil.copyfile(source, staged)
        if digest(staged) != source_hashes[case]:
            raise ValueError(f"Synthetic {case} source changed while staging")
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
        "for case in fault control; do\n"
        "  for run in first repeat; do\n"
        '    kicad-cli sch export netlist --format kicadxml --output "/output/${case}.${run}.netlist.xml" '
        '"/fixtures/${case}.kicad_sch"\n'
        '    kicad-cli sch erc --format json --severity-all --output "/output/${case}.${run}.erc.json" '
        '"/fixtures/${case}.kicad_sch"\n'
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
        "HOME=/tmp/kicad-connector-return-signal",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned_image(config.image),
        "-ec",
        script,
    )
    lane = "connector-return-signal-fixture"
    log.event(
        f"{lane}/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        error = command.stderr or command.error or f"exit {command.returncode}"
        log.event(
            f"{lane}/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=config.image,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=error,
        )
        raise ValueError(f"Native connector return/signal export failed: {error}")

    log.event(
        f"{lane}/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    results: dict[tuple[str, str], tuple[str, int]] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted connector return/signal {case} evidence")
            observed = read_netlist(netlist_path)
            raw_hashes[(case, run)] = digest(netlist_path)
            normalized_hashes[(case, run)] = hashlib.sha256(
                normalized_netlist_bytes(observed)
            ).hexdigest()
            expected_signal_nets = ("SDA_BUS",)
            expected_return_nets = ("SDA_BUS",) if case == "fault" else ("GND",)
            if (
                observed.component_symbols != {"J1": "Lint:ProtocolReturnPort"}
                or observed.component_pin_numbers.get("J1") != ("1", "2")
                or observed.pin_functions.get("J1.1") != "SDA"
                or observed.pin_functions.get("J1.2") != "GND"
            ):
                raise ValueError(f"Native {case} connector pin/function inventory changed")
            signal_nets = tuple(
                sorted(net for net, pins in observed.nets.items() if "J1.1" in pins)
            )
            return_nets = tuple(
                sorted(net for net, pins in observed.nets.items() if "J1.2" in pins)
            )
            if signal_nets != expected_signal_nets or return_nets != expected_return_nets:
                raise ValueError(
                    f"Native {case} assignments changed: SDA={signal_nets}, GND={return_nets}"
                )
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError(f"Native ERC version mismatch for connector return/signal {case}")
            errors = tuple(sorted(item.type for item in erc.violations if item.severity == "error"))
            if errors:
                raise ValueError(f"Native {case} fixture has ERC errors: {errors}")

            project_id = f"synthetic-connector-return-signal-{case}"
            report = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=raw_hashes[(case, run)],
                ),
                DesignLintPolicy(),
            )
            findings = tuple(item for item in report.findings if item.rule_id == _RULE_ID)
            expected_count = 1 if case == "fault" else 0
            expected_status = "REVIEW" if expected_count else "PASS"
            if len(findings) != expected_count or report.status != expected_status:
                raise ValueError(
                    f"Native {case} expected {expected_status}/{expected_count} finding(s), "
                    f"observed {report.status}/{len(findings)}"
                )
            results[(case, run)] = (report.status, len(findings))

    for case in cases:
        repeatable = normalized_hashes[(case, "first")] == normalized_hashes[(case, "repeat")]
        if not repeatable or results[(case, "first")] != results[(case, "repeat")]:
            raise ValueError(f"Native {case} connector return/signal result is not repeatable")
        if digest(fixture_root / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} source changed during native export")
        log.event(
            f"{lane}/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=config.image,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=results[(case, "first")][0],
            finding_count=results[(case, "first")][1],
            repeatable=str(repeatable).lower(),
            repeatability_basis="normalized_netlist_contract",
            command_receipt=receipt.relative_to(root).as_posix(),
        )
