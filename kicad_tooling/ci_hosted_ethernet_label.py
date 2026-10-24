"""Digest-pinned native export lane for Ethernet pin/net-label review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

RULE_ID = "bus.ethernet_data_label_mismatch"


def ethernet_label_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export synthetic Ethernet label controls twice and evaluate the active rule."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.design_lint_report_models import DesignLintReport
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Ethernet label fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    repository = Path(__file__).resolve().parents[1]
    sources = {
        case: repository / f"tests/fixtures/design_lint/ethernet-data-label-native/{case}.kicad_sch"
        for case in ("control", "fault")
    }
    expected_source_hashes = {
        "control": "9fae1afdb0395354f6e61eae17623f5d940b2f90bf82d452ff8339bfed1e421e",
        "fault": "8b42bc11362cedc71519b7ffb2477da399c52374efcf44bcb69d35149f9a1b92",
    }
    source_hashes = {case: digest(path) for case, path in sources.items()}
    if source_hashes != expected_source_hashes:
        raise ValueError("Ethernet pair-label fixtures differ from their reviewed source hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"ethernet-label-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(source, target)
        if digest(target) != source_hashes[case]:
            raise ValueError(f"Synthetic Ethernet {case} schematic changed during preparation")
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
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
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
        "HOME=/tmp/kicad-ethernet-label-fixtures",
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
        "ethernet-label-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "ethernet-label-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native Ethernet label export failed: {command.stderr or command.error}")
    log.event(
        "ethernet-label-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in sorted(sources)),
        command_receipt=receipt.relative_to(root).as_posix(),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    observations: dict[tuple[str, str], NetlistContract] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native Ethernet export omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            observations[(case, run)] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-ethernet-label-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]
        for case in sources
    ):
        raise ValueError("Native Ethernet exports differ after netlist normalization")

    control = reports[("control", "first")]
    fault = reports[("fault", "first")]
    control_findings = tuple(item for item in control.findings if item.rule_id == RULE_ID)
    fault_findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    expected_subjects = (
        "U1.1: TDP on ETH_RX_P",
        "U1.2: TDN on ETH_RX_N",
        "U1.3: RDP on ETH_TX_P",
        "U1.4: RDN on ETH_TX_N",
    )
    if control_findings:
        raise ValueError("Native Ethernet label control produced an unexpected finding")
    if tuple(item.subject for item in fault_findings) != expected_subjects:
        raise ValueError(
            f"Native Ethernet label fault produced "
            f"{tuple(item.subject for item in fault_findings)!r}; expected {expected_subjects!r}"
        )
    if any(item.rule_id == "bus.complementary_pair_assignment" for item in fault.findings):
        raise ValueError("Complete Ethernet pairs should remain outside pair-completeness findings")

    for case, report, findings in (
        ("control", control, control_findings),
        ("fault", fault, fault_findings),
    ):
        observed = observations[(case, "first")]
        expected_pins = {
            "U1.1": ("TDP", "ETH_TX_P" if case == "control" else "ETH_RX_P"),
            "U1.2": ("TDN", "ETH_TX_N" if case == "control" else "ETH_RX_N"),
            "U1.3": ("RDP", "ETH_RX_P" if case == "control" else "ETH_TX_P"),
            "U1.4": ("RDN", "ETH_RX_N" if case == "control" else "ETH_TX_N"),
        }
        for pin, (function, net) in expected_pins.items():
            assigned_nets = tuple(
                sorted(
                    name
                    for name, members in observed.nets.items()
                    if any(member.casefold() == pin.casefold() for member in members)
                )
            )
            if observed.pin_functions.get(pin) != function or assigned_nets != (net,):
                raise ValueError(f"Native Ethernet {case} evidence changed for {pin}")
        log.event(
            f"ethernet-label-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            repeatable="true",
            lint_status=report.status,
            findings=";".join(item.subject for item in findings) if findings else "none",
        )
    log.finish()
