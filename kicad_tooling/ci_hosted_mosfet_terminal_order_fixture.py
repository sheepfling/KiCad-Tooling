"""Exact-version native fixtures for MOSFET terminal-order review."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType

from .ci_hosted_support import HostedLog, normalized_erc_report_bytes, tooling_checkout_root
from .hwrepo.component_mosfet_terminal_order import RULE_ID as TERMINAL_ORDER_RULE_ID
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_finding_models import DesignLintRuleOverride
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist

MOSFET_TERMINAL_ORDER_FIXTURE_CASES = MappingProxyType(
    {
        "fault_nmos": "mosfet-terminal-order-native/fault_nmos.kicad_sch",
        "control_nmos": "mosfet-terminal-order-native/control_nmos.kicad_sch",
        "fault_pmos": "mosfet-terminal-order-native/fault_pmos.kicad_sch",
        "control_pmos": "mosfet-terminal-order-native/control_pmos.kicad_sch",
    }
)


def mosfet_terminal_order_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export and evaluate NMOS/PMOS rail-order faults and controls twice."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image or config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError("MOSFET terminal-order fixtures require a pinned KiCad 10.0 image")
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    source_hashes = {
        case: digest(fixture_root / relative)
        for case, relative in MOSFET_TERMINAL_ORDER_FIXTURE_CASES.items()
    }
    scratch = Path(tempfile.mkdtemp(prefix="mosfet-terminal-order-", dir=log.directory.resolve()))
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    source_lines = [
        'mkdir -p "$HOME"\n',
        'actual="$(kicad-cli version)"\n',
        'printf "kicad_version=%s\\n" "$actual"\n',
        f'test "$actual" = "{config.kicad_version}"\n',
    ]
    for case, relative in MOSFET_TERMINAL_ORDER_FIXTURE_CASES.items():
        source_lines.append(f'printf "exporting_fixture=%s\\n" "{relative}"\n')
        for run in ("first", "repeat"):
            source_lines.append(
                "kicad-cli sch export netlist --format kicadxml --output "
                f'"/output/{case}.{run}.netlist.xml" "/fixtures/{relative}"\n'
            )
            source_lines.append(
                "kicad-cli sch erc --format json --severity-all --output "
                f'"/output/{case}.{run}.erc.json" "/fixtures/{relative}"\n'
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
        "HOME=/tmp/kicad-mosfet-terminal-order-fixtures",
        "-v",
        f"{fixture_root.resolve()}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned_image(config.image),
        "-ec",
        "".join(source_lines),
    )
    log.event(
        "mosfet-terminal-order-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(
            f"Native MOSFET terminal-order export failed: {command.stderr or command.error}"
        )
    log.event(
        "mosfet-terminal-order-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in source_hashes),
        command_receipt=receipt.relative_to(root).as_posix(),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    erc_hashes: dict[tuple[str, str], str] = {}
    for case in MOSFET_TERMINAL_ORDER_FIXTURE_CASES:
        reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError("MOSFET terminal-order ERC version differs from project pin")
            erc_hashes[(case, run)] = hashlib.sha256(normalized_erc_report_bytes(erc)).hexdigest()
            erc_errors = tuple(item.type for item in erc.violations if item.severity == "error")
            if erc_errors:
                raise ValueError(
                    f"Native MOSFET terminal-order fixture has ERC errors: {erc_errors}"
                )
            reports[run] = evaluate(
                f"synthetic-mosfet-terminal-order-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-mosfet-terminal-order-{case}",
                    observed=observed,
                    netlist_sha256=digest(netlist_path),
                ),
                DesignLintPolicy(
                    rules=(
                        DesignLintRuleOverride(
                            rule_id=TERMINAL_ORDER_RULE_ID,
                            mode="review",
                            reason="Native synthetic MOSFET rail-order fixture",
                        ),
                    )
                ),
            )

        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native MOSFET terminal-order {case} netlist is not repeatable")
        if erc_hashes[(case, "first")] != erc_hashes[(case, "repeat")]:
            raise ValueError(f"Native MOSFET terminal-order {case} ERC is not repeatable")
        first_findings = tuple(
            item.model_dump(mode="json")
            for item in reports["first"].findings
            if item.rule_id == TERMINAL_ORDER_RULE_ID
        )
        repeat_findings = tuple(
            item.model_dump(mode="json")
            for item in reports["repeat"].findings
            if item.rule_id == TERMINAL_ORDER_RULE_ID
        )
        expected_count = 1 if case.startswith("fault_") else 0
        if first_findings != repeat_findings or len(first_findings) != expected_count:
            raise ValueError(
                f"Native MOSFET terminal-order {case} expected {expected_count} stable finding(s)"
            )
        log.event(
            f"mosfet-terminal-order-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=config.image,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            normalized_erc_sha256=erc_hashes[(case, "first")],
            repeat_normalized_erc_sha256=erc_hashes[(case, "repeat")],
            lint_status=reports["first"].status,
            rule_findings=";".join(item["subject"] for item in first_findings) or "none",
            erc_errors="none",
            repeatable="true",
        )
    if any(
        digest(fixture_root / relative) != source_hashes[case]
        for case, relative in MOSFET_TERMINAL_ORDER_FIXTURE_CASES.items()
    ):
        raise ValueError("MOSFET terminal-order sources changed during native export")
