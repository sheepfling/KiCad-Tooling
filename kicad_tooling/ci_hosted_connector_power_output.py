"""Exact-version native fixtures for generic open connector power outputs."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist


def connector_unconnected_power_output_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify generic open connector power-output fault and assigned control exports."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError("Connector power-output fixture image differs from its toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Connector power-output fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/generic-connector-power-output"
    )
    cases = {"fault": "fault.kicad_sch", "control": "control.kicad_sch"}
    source_hashes = {case: digest(fixture_root / filename) for case, filename in cases.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"connector-power-output-{project}-", dir=log.directory.resolve())
    )
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
    for case, filename in cases.items():
        source_lines.append(
            "for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{filename}"; done\n'
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
        "HOME=/tmp/kicad-connector-power-output",
        "-v",
        f"{fixture_root.resolve()}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        "".join(source_lines),
    )
    lane_name = "connector-power-output-fixture"
    log.event(
        f"{lane_name}/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            f"{lane_name}/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            "Native connector power-output fixture export failed: "
            f"{command.stderr or command.error}"
        )
    log.event(
        f"{lane_name}/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    for case, filename in cases.items():
        case_reports: dict[str, tuple[str, int]] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(
                    f"Native connector power-output export omitted {netlist_path.name}"
                )
            observed = read_netlist(netlist_path)
            raw_hashes[(case, run)] = digest(netlist_path)
            expected_assignments = (
                {"J1.1": (), "J1.2": ("GND",), "J2.1": (), "J2.2": ("GND",)}
                if case == "fault"
                else {
                    "J1.1": ("+5V",),
                    "J1.2": ("GND",),
                    "J2.1": ("+5V",),
                    "J2.2": ("GND",),
                }
            )
            actual_assignments = {
                pin: tuple(sorted(net for net, pins in observed.nets.items() if pin in pins))
                for pin in expected_assignments
            }
            if actual_assignments != expected_assignments:
                raise ValueError(
                    f"Native {case} expected assignments {expected_assignments}; "
                    f"observed {actual_assignments}"
                )
            if (
                observed.component_symbols
                != {"J1": "Lint:GenericPowerOutputPort", "J2": "Lint:GenericPowerOutputPort"}
                or observed.component_pin_numbers.get("J1") != ("1", "2")
                or observed.component_pin_numbers.get("J2") != ("1", "2")
                or observed.pin_electrical_types.get("J1.1") != "power_out"
                or observed.pin_electrical_types.get("J2.1") != "power_out"
                or observed.pin_functions.get("J1.1") != "1"
                or observed.pin_functions.get("J2.1") != "1"
            ):
                raise ValueError("Native export omitted the generic connector power_out inventory")
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-connector-power-output-{case}"
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
            rule_findings = tuple(
                item
                for item in report.findings
                if item.rule_id == "connector.unconnected_power_output"
            )
            expected_count = 2 if case == "fault" else 0
            if len(rule_findings) != expected_count:
                raise ValueError(
                    f"Native {case} expected {expected_count} connector power-output finding(s); "
                    f"observed {len(rule_findings)}"
                )
            if report.status != ("REVIEW" if expected_count else "PASS"):
                raise ValueError(
                    f"Native {case} expected lint status "
                    f"{'REVIEW' if expected_count else 'PASS'}, observed {report.status}"
                )
            case_reports[run] = (report.status, len(rule_findings))
        repeatable = normalized_hashes[(case, "first")] == normalized_hashes[(case, "repeat")]
        if not repeatable:
            raise ValueError(f"Native {case} netlist differs after normalized repeat export")
        if digest(fixture_root / filename) != source_hashes[case]:
            raise ValueError(f"Synthetic {case} source changed during the native export")
        log.event(
            f"{lane_name}/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=case_reports["first"][0],
            finding_count=case_reports["first"][1],
            repeatable=str(repeatable).lower(),
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
