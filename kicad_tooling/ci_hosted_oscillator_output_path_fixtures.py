"""Exact-version native evidence for authored oscillator output paths."""

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

from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_model, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, ProjectTestContract
from .validate import read_netlist

RULE_ID = "oscillator.output_load_path_mismatch"
_CASE_FILES: Mapping[str, str] = MappingProxyType(
    {
        "series-boundary-control": "series-boundary-control.kicad_sch",
        "wrong-value-fault": "wrong-value-fault.kicad_sch",
    }
)
_SOURCE_SHA256: Mapping[str, str] = MappingProxyType(
    {
        "series-boundary-control.kicad_sch": "4fadcabb12a2bbedc396e707abf0bf1247df3a921674b5236cc993c9d54445b9",
        "wrong-value-fault.kicad_sch": "9225ef72ca1e7922003672085bc69531a33f67b0acc1acbde2b9554d350239d8",
    }
)


def _evaluate_case(
    *,
    project_id: str,
    contract: ProjectTestContract,
    case: str,
    netlist_path: Path,
) -> tuple[str, tuple[str, ...], str]:
    policy = contract.design_lint
    if policy is None or policy.oscillator_output_path_map is None:
        raise ValueError("Native oscillator fixture project is missing its authored path map")
    observed = read_netlist(netlist_path)
    content = json.dumps(
        observed.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    raw_sha256 = digest(netlist_path)
    normalized_sha256 = hashlib.sha256(content).hexdigest()
    report = evaluate(
        project_id,
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=project_id,
            observed=observed,
            netlist_sha256=raw_sha256,
        ),
        policy,
    )
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    expected_count = 0 if case == "series-boundary-control" else 1
    if len(findings) != expected_count:
        raise ValueError(
            f"Native oscillator {case} expected {expected_count} target findings, "
            f"observed {len(findings)}"
        )
    issues = () if not findings else tuple(findings[0].evidence.get("issues", ()))
    if case == "wrong-value-fault" and not any(
        "R1 nominal resistance is 1000 ohms" in issue for issue in issues
    ):
        raise ValueError("Native oscillator wrong-value fault omitted parsed 1 kOhm evidence")
    if case == "wrong-value-fault" and (
        report.status != "REVIEW"
        or findings[0].mode != "review"
        or findings[0].disposition != "OPEN"
    ):
        raise ValueError("Native oscillator wrong-value fault lost default REVIEW policy")
    run = next(
        (item for item in report.mapped_check_runs if item.rule_id == RULE_ID),
        None,
    )
    if run is None or run.finding_count != expected_count:
        raise ValueError("Native oscillator report omitted its mapped-check coverage record")
    return report.status, issues, normalized_sha256


def oscillator_output_path_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Export, normalize, and lint the synthetic fault/control on pinned KiCad."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: oscillator fixture image differs from its toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Oscillator output path fixtures do not cover KiCad {config.kicad_version}"
        )
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint/oscillator-output-native"
    fixture_paths = {case: fixture_root / filename for case, filename in _CASE_FILES.items()}
    source_hashes = {path.name: digest(path) for path in fixture_paths.values()}
    if source_hashes != _SOURCE_SHA256:
        raise ValueError("Synthetic oscillator native fixture source hash changed")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"oscillator-output-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    output = scratch / "output"
    inputs.mkdir()
    output.mkdir()
    for case, source_path in fixture_paths.items():
        shutil.copyfile(source_path, inputs / _CASE_FILES[case])
        if digest(inputs / _CASE_FILES[case]) != source_hashes[_CASE_FILES[case]]:
            raise ValueError(f"Synthetic oscillator {case} fixture changed while staging")

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    commands = [
        'mkdir -p "$HOME"\n',
        'actual="$(kicad-cli version)"\n',
        'printf "kicad_version=%s\\n" "$actual"\n',
        f'test "$actual" = "{config.kicad_version}"\n',
    ]
    for case, filename in _CASE_FILES.items():
        commands.append(
            f"for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{filename}"; done\n'
        )
    pinned = pinned_image(config.image)
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
        "HOME=/tmp/kicad-oscillator-output",
        "-v",
        f"{inputs.resolve()}:/fixtures:ro",
        "-v",
        f"{output.resolve()}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        "".join(commands),
    )
    log.event(
        "oscillator-output-path-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    command_path = scratch / "native.command.json"
    write_model(command_path, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "oscillator-output-path-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=command_path.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native oscillator export failed: {command.stderr or command.error}")

    contract_path = root / "projects" / project / "tests" / "contract.json"
    contract = read_model(contract_path, ProjectTestContract)
    normalized_hashes: dict[tuple[str, str], str] = {}
    case_results: dict[str, tuple[str, tuple[str, ...]]] = {}
    for case in _CASE_FILES:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native oscillator export omitted {netlist_path.name}")
            status, issues, normalized_sha256 = _evaluate_case(
                project_id=project,
                contract=contract,
                case=case,
                netlist_path=netlist_path,
            )
            normalized_hashes[(case, run)] = normalized_sha256
            if run == "first":
                case_results[case] = status, issues
    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]
        for case in _CASE_FILES
    ):
        raise ValueError("Native oscillator exports differ after typed-netlist normalization")
    expected_fault = case_results["wrong-value-fault"]
    if expected_fault[0] != "REVIEW":
        raise ValueError("Native oscillator wrong-value fault did not surface a review")
    if case_results["series-boundary-control"][1]:
        raise ValueError("Native oscillator 47-ohm inclusive-boundary control reported a mismatch")
    log.event(
        "oscillator-output-path-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(
            f"{filename}:{source_hashes[filename]}" for filename in sorted(source_hashes)
        ),
        normalized_control_sha256=normalized_hashes[("series-boundary-control", "first")],
        normalized_fault_sha256=normalized_hashes[("wrong-value-fault", "first")],
        repeatable="true",
        command_receipt=command_path.relative_to(root).as_posix(),
    )
    for case, (status, issues) in case_results.items():
        log.event(
            f"oscillator-output-path-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            lint_status=status,
            rule_id=RULE_ID,
            issues="; ".join(issues) or "none",
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeatable="true",
        )
