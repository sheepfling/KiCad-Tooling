"""Hosted native PCB signal-path DRC fixture lane."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def pcb_signal_path_drc_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Check native fromTo length and skew rules on repeatable synthetic boards."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.pcb_drc_rule_parser import read_native_pcb_drc_fixture_report

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"PCB signal-path native DRC fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(image)
    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/signal-path"
    if not (fixture_root / "create.py").is_file():
        raise ValueError("Synthetic signal-path DRC generator is missing")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"pcb-signal-path-drc-{project}-", dir=log.directory.resolve())
    )
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = () if os.name == "nt" else ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'actual="$(kicad-cli version)"\n'
        'printf "%s\\n" "$actual" > /output/kicad-version.txt\n'
        f'test "$actual" = "{config.kicad_version}"\n'
        f"python3 /fixtures/create.py /output {config.kicad_version}\n"
        "for case in control fault ignored; do\n"
        "  for run in first repeat; do\n"
        "    set +e\n"
        "    kicad-cli pcb drc --format json --severity-all --exit-code-violations "
        '--output "/output/${case}.${run}.json" "/output/${case}.kicad_pcb"\n'
        "    result=$?\n"
        "    set -e\n"
        '    if [ "$result" -ne 0 ] && [ "$result" -ne 5 ]; then exit "$result"; fi\n'
        '    printf "%s\\n" "$result" > "/output/${case}.${run}.exit"\n'
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
        "HOME=/tmp/kicad-signal-path-drc",
        "-v",
        f"{fixture_root.resolve()}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    log.event(
        "pcb-signal-path-drc-fixture/native-run",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "pcb-signal-path-drc-fixture/native-run",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native signal-path DRC fixture failed: {command.stderr or command.error}"
        )

    source_hashes = {
        f"{case}_{kind}": digest(output / f"{case}.{suffix}")
        for case in ("control", "fault", "ignored")
        for kind, suffix in (("board", "kicad_pcb"), ("rules", "kicad_dru"))
    }
    target_types = {"length_out_of_range", "skew_out_of_range"}
    observed: dict[str, dict[str, tuple[tuple[str, ...], str, int]]] = {}
    report_hashes: dict[str, str] = {}
    for case in ("control", "fault", "ignored"):
        observed[case] = {}
        for run in ("first", "repeat"):
            report_path = output / f"{case}.{run}.json"
            status_path = output / f"{case}.{run}.exit"
            if not report_path.is_file() or not status_path.is_file():
                raise ValueError(f"Native signal-path DRC omitted {case} {run} evidence")
            report = read_native_pcb_drc_fixture_report(report_path)
            report_hashes[f"{case}_{run}"] = digest(report_path)
            if report.kicad_version != config.kicad_version:
                raise ValueError(f"Native signal-path {case} DRC has an unexpected KiCad version")
            if Path(report.source).name != f"{case}.kicad_pcb":
                raise ValueError(f"Native signal-path {case} DRC does not identify its board")
            exit_code = int(status_path.read_text(encoding="utf-8").strip())
            if exit_code not in {0, 5}:
                raise ValueError(f"Native signal-path {case} DRC has an unexpected exit code")
            observed[case][run] = (
                report.violation_types,
                report.violation_records_sha256,
                exit_code,
            )

        if observed[case]["first"] != observed[case]["repeat"]:
            raise ValueError(f"Repeated native signal-path {case} DRC findings changed")

    control_types, control_records_sha256, control_exit = observed["control"]["first"]
    fault_types, fault_records_sha256, fault_exit = observed["fault"]["first"]
    ignored_types, ignored_records_sha256, ignored_exit = observed["ignored"]["first"]
    if control_exit != 0 or target_types & set(control_types):
        raise ValueError(f"Native signal-path control produced target findings: {control_types}")
    if fault_exit != 5 or not target_types <= set(fault_types):
        raise ValueError(f"Native signal-path fault missed length/skew: {fault_types}")
    if ignored_exit != 0 or target_types & set(ignored_types):
        raise ValueError(
            f"Native signal-path ignored-rule control produced target findings: {ignored_types}"
        )
    log.event(
        "pcb-signal-path-drc-fixture/native-run",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        control_violation_types=",".join(control_types) or "none",
        fault_violation_types=",".join(fault_types),
        ignored_violation_types=",".join(ignored_types) or "none",
        control_exit_code=control_exit,
        fault_exit_code=fault_exit,
        ignored_exit_code=ignored_exit,
        expected_findings=",".join(sorted(target_types)),
        repeatable="true",
        control_violation_records_sha256=control_records_sha256,
        fault_violation_records_sha256=fault_records_sha256,
        ignored_violation_records_sha256=ignored_records_sha256,
        artifact_directory=output.relative_to(root).as_posix(),
        control_board_sha256=source_hashes["control_board"],
        control_rules_sha256=source_hashes["control_rules"],
        fault_board_sha256=source_hashes["fault_board"],
        fault_rules_sha256=source_hashes["fault_rules"],
        ignored_board_sha256=source_hashes["ignored_board"],
        ignored_rules_sha256=source_hashes["ignored_rules"],
        control_first_drc_sha256=report_hashes["control_first"],
        control_repeat_drc_sha256=report_hashes["control_repeat"],
        fault_first_drc_sha256=report_hashes["fault_first"],
        fault_repeat_drc_sha256=report_hashes["fault_repeat"],
        ignored_first_drc_sha256=report_hashes["ignored_first"],
        ignored_repeat_drc_sha256=report_hashes["ignored_repeat"],
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
