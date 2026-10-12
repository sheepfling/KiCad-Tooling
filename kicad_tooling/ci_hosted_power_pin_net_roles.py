"""Digest-pinned native exports for named power-pin net-role lint."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


def power_pin_net_role_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
    cases: tuple[str, ...] = ("fault", "control"),
) -> None:
    """Repeat native netlist export for conflicting and valid pin-role assignments."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.design_lint_report_models import DesignLintReport
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: power pin-role image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Power pin-role fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/power-pin-net-role-native"
    )
    case_files = {
        "fault": "fault.kicad_sch",
        "control": "control.kicad_sch",
        "negative-rail-fault": "negative-rail-fault.kicad_sch",
    }
    if not cases or set(cases) - set(case_files):
        raise ValueError(f"Unsupported named power-pin fixture cases: {cases}")
    selected_cases = {case: case_files[case] for case in cases}
    source_hashes = {
        case: digest(fixture_root / filename) for case, filename in selected_cases.items()
    }
    scratch = Path(
        tempfile.mkdtemp(prefix=f"power-pin-net-role-{project}-", dir=log.directory.resolve())
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
    for case, filename in selected_cases.items():
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
        "HOME=/tmp/kicad-power-pin-net-roles",
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
    log.event(
        "power-pin-net-role/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(
            f"Native power pin-role fixture export failed: {command.stderr or command.error}"
        )

    normalized: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    expected_assignments: dict[str, tuple[str, set[str], set[str]]] = {
        "fault": ("GND", {"U1.1", "U1.2"}, set()),
        "control": ("+3V3", {"U1.1"}, {"U1.2"}),
        "negative-rail-fault": ("-5V", {"U1.1"}, {"U1.2"}),
    }
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native power pin-role fixture omitted {netlist_path.name}")
            raw_hashes[case, run] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized_bytes = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized[case, run] = hashlib.sha256(normalized_bytes).hexdigest()
            expected_supply_net, expected_supply_members, expected_return_members = (
                expected_assignments[case]
            )
            if (
                observed.pin_functions.get("U1.1") != "VDD"
                or observed.pin_functions.get("U1.2") != "GND"
                or set(observed.nets.get(expected_supply_net, ())) != expected_supply_members
                or (
                    expected_return_members
                    and set(observed.nets.get("GND", ())) != expected_return_members
                )
            ):
                raise ValueError(f"Native {case} export lost the expected named-pin assignments")
            project_id = f"synthetic-power-pin-net-role-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[case, run],
            )
            reports[case, run] = evaluate(project_id, coach, DesignLintPolicy())

    expected_findings_by_case = {
        "fault": {"power.pin_function_net_role_conflict": "U1.1: VDD pin assigned to GND"},
        "control": {},
        "negative-rail-fault": {
            "power.named_supply_pin_on_negative_rail": "U1.1: VDD pin assigned to -5V"
        },
    }
    for case, filename in selected_cases.items():
        if normalized[case, "first"] != normalized[case, "repeat"]:
            raise ValueError(f"Native {case} netlist exports differ after normalization")
        first_report = reports[case, "first"]
        repeat_report = reports[case, "repeat"]
        first_findings = tuple(
            (item.rule_id, item.fingerprint, item.evidence) for item in first_report.findings
        )
        repeat_findings = tuple(
            (item.rule_id, item.fingerprint, item.evidence) for item in repeat_report.findings
        )
        if first_report.status != repeat_report.status or first_findings != repeat_findings:
            raise ValueError(f"Native {case} lint reports differ after normalized export")
        findings_by_rule = {item.rule_id: item.subject for item in first_report.findings}
        expected = expected_findings_by_case[case]
        if findings_by_rule != expected:
            raise ValueError(
                f"Native {case} role findings differ from expectation: {findings_by_rule}"
            )
        expected_status = "REVIEW" if expected else "PASS"
        if first_report.status != expected_status:
            raise ValueError(f"Native {case} lint status differs: {first_report.status}")
        if digest(fixture_root / filename) != source_hashes[case]:
            raise ValueError(f"Native {case} source changed during fixture export")
        log.event(
            f"power-pin-net-role/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[case, "first"],
            repeat_netlist_sha256=raw_hashes[case, "repeat"],
            normalized_netlist_sha256=normalized[case, "first"],
            repeat_normalized_netlist_sha256=normalized[case, "repeat"],
            lint_status=expected_status,
            findings=";".join(sorted(expected.values())) or "none",
            finding_rules=",".join(sorted(expected)) or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "power-pin-net-role/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in selected_cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
