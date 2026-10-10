"""Hosted CI orchestration with the same selection and checks available locally.

GitHub Actions owns runner allocation, job dependencies and artifact uploads. This
module owns decisions and commands, recording each stage under ignored build/.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from .ci_hosted_can_peer_assignment import can_peer_assignment_fixture_lane
from .ci_hosted_can_termination_fixtures import can_termination_native_fixture_lane
from .ci_hosted_complementary_pairs import complementary_pair_fixture_lane
from .ci_hosted_component_peer_pins import (
    component_peer_bidirectional_fixture_lane,
    component_peer_power_output_fixture_lane,
    component_peer_signal_input_fixture_lane,
    component_peer_signal_output_fixture_lane,
)
from .ci_hosted_component_peer_power_assignment import component_peer_power_assignment_fixture_lane
from .ci_hosted_component_rating_lane import component_rating_fixtures_lane
from .ci_hosted_connector_inventory import connector_inventory_fixture_lane
from .ci_hosted_connector_return_lane import connector_return_lint_fixture_lane
from .ci_hosted_control_inputs import native_control_input_demo_lane
from .ci_hosted_digital_peer_lane import digital_peer_fixture_lane as _digital_peer_fixture_lane
from .ci_hosted_empty_netlist_evidence import empty_netlist_evidence_fixture_lane
from .ci_hosted_i2c_pullup_fixtures import i2c_pullup_native_fixture_lane
from .ci_hosted_ic_rail_capacitors import (
    ic_rail_capacitor_fixture_lane as _run_ic_rail_capacitor_fixture_lane,
)
from .ci_hosted_led_rail import led_rail_fixture_lane
from .ci_hosted_net_dc_reference import net_dc_reference_fixture_lane
from .ci_hosted_open_drain_bias import (
    open_drain_bias_fixture_lane as _run_open_drain_bias_fixture_lane,
)
from .ci_hosted_pcb_access import pcb_access_fixture_lane
from .ci_hosted_pcb_geometry_fixtures import pcb_decoupling_fixture_lane
from .ci_hosted_pcb_reference_planes import (
    pcb_reference_plane_narrow_void_fixture_lane,
    pcb_reference_plane_via_fixture_lane,
)
from .ci_hosted_pcb_return_lane import (
    run_pcb_return_fixture_lane as _run_pcb_return_fixture_lane,
)
from .ci_hosted_pcb_signal_path_drc import pcb_signal_path_drc_fixture_lane
from .ci_hosted_pcb_switching_loop_lane import (
    run_switching_loop_fixture_lane as _run_switching_loop_fixture_lane,
)
from .ci_hosted_power_paths import power_path_fixture_lane
from .ci_hosted_power_sequences import (
    power_sequence_fixture_lane as _run_power_sequence_fixture_lane,
)
from .ci_hosted_release_fixture import release_fixture
from .ci_hosted_serial_peer_fixtures import serial_peer_fixture_lane
from .ci_hosted_serial_peer_net_labels import serial_peer_net_label_fixture_lane
from .ci_hosted_serial_peer_reference_bonds import (
    serial_peer_reference_bond_fixture_lane,
)
from .ci_hosted_stm32_pin_map import stm32_pin_map_fixture_lane
from .ci_hosted_two_pin_components import (
    TWO_PIN_COMPONENT_FIXTURE_CASES,
    two_pin_component_fixture_lane,
)
from .ci_hosted_usb_c_ports import usb_c_port_fixture_lane as _run_usb_c_port_fixture_lane
from .ci_hosted_usb_data_paths import usb_data_path_fixture_lane
from .ci_matrix import build_matrix
from .hwrepo.contracts import (
    read_kicad_erc_report,
    read_model,
    write_model,
)
from .hwrepo.hosted_preview import preview_lane
from .hwrepo.models import (
    ForeignPcbReport,
    ImpactPlan,
    ProjectImportReport,
    ProjectKind,
    ProjectManifest,
)
from .impact import build_plan

__all__ = (
    "TWO_PIN_COMPONENT_FIXTURE_CASES",
    "HostedCommandError",
    "HostedLog",
    "can_peer_assignment_fixture_lane",
    "can_termination_native_fixture_lane",
    "candidate_lane",
    "checked_source",
    "complementary_pair_fixture_lane",
    "component_peer_bidirectional_fixture_lane",
    "component_peer_power_assignment_fixture_lane",
    "component_peer_power_output_fixture_lane",
    "component_peer_signal_input_fixture_lane",
    "component_peer_signal_output_fixture_lane",
    "component_rating_fixtures_lane",
    "connector_inventory_fixture_lane",
    "connector_return_lint_fixture_lane",
    "digital_peer_fixture_lane",
    "electrical_lane",
    "empty_netlist_evidence_fixture_lane",
    "gate_result",
    "i2c_pullup_native_fixture_lane",
    "ic_rail_capacitor_fixture_lane",
    "led_rail_fixture_lane",
    "main",
    "markdown_checks",
    "matrix_lane",
    "native_control_input_demo_lane",
    "native_lane",
    "net_dc_reference_fixture_lane",
    "open_drain_bias_fixture_lane",
    "pcb_access_fixture_lane",
    "pcb_decoupling_fixture_lane",
    "pcb_reference_plane_narrow_void_fixture_lane",
    "pcb_reference_plane_via_fixture_lane",
    "pcb_return_fixture_lane",
    "pcb_signal_path_drc_fixture_lane",
    "pcb_switching_loop_fixture_lane",
    "plan_lane",
    "plan_scope",
    "portable_lane",
    "power_path_fixture_lane",
    "power_sequence_fixture_lane",
    "project_simulator",
    "read_kicad_erc_report",
    "release_fixture",
    "release_lane",
    "serial_peer_fixture_lane",
    "serial_peer_net_label_fixture_lane",
    "serial_peer_reference_bond_fixture_lane",
    "stm32_pin_map_fixture_lane",
    "two_pin_component_fixture_lane",
    "usb_c_port_fixture_lane",
    "usb_data_path_fixture_lane",
    "windows_smoke",
    "windows_types",
    "write_action_outputs",
)


def digital_peer_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Keep the hosted CI import stable while checks live by theme."""
    _digital_peer_fixture_lane(root, project=project, image=image, log=log)


def pcb_switching_loop_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Keep the hosted CI import stable while checks live by theme."""
    _run_switching_loop_fixture_lane(root, project=project, image=image, log=log)


def pcb_return_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Keep the hosted CI import stable while checks live by theme."""
    _run_pcb_return_fixture_lane(root, project=project, image=image, log=log)


def usb_c_port_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Keep the hosted CI import stable while checks live by theme."""
    _run_usb_c_port_fixture_lane(root, project=project, image=image, log=log)


def ic_rail_capacitor_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Keep the hosted CI import stable while checks live by theme."""
    _run_ic_rail_capacitor_fixture_lane(root, project=project, image=image, log=log)


def power_sequence_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Keep the hosted CI import stable while checks live by theme."""
    _run_power_sequence_fixture_lane(root, project=project, image=image, log=log)


def open_drain_bias_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Keep the hosted CI import stable while checks live by theme."""
    _run_open_drain_bias_fixture_lane(root, project=project, image=image, log=log)


class HostedCommandError(RuntimeError):
    """A retained child failure whose exit code remains available to the caller."""

    def __init__(self, message: str, returncode: int) -> None:
        super().__init__(message)
        self.returncode = returncode


class HostedLog:
    """Small append-only stage journal that survives a failed hosted command."""

    def __init__(self, root: Path, lane: str) -> None:
        self.directory = root / "build/ci-hosted" / lane
        self.directory.mkdir(parents=True, exist_ok=True)
        self.events = self.directory / "events.jsonl"
        self.event("lane", "START")

    def event(self, stage: str, status: str, **details: str | float) -> None:
        entry: dict[str, str | float | int] = {
            "time_utc": datetime.now(UTC).isoformat(),
            "stage": stage,
            "status": status,
            **details,
        }
        with self.events.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, sort_keys=True) + "\n")
        suffix = (
            " " + " ".join(f"{key}={value}" for key, value in details.items()) if details else ""
        )
        print(f"hosted-ci: {stage} {status.lower()}{suffix}", file=sys.stderr, flush=True)

    def run(
        self,
        stage: str,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        stdout_path: Path | None = None,
        env: dict[str, str] | None = None,
        merge_stderr: bool = False,
    ) -> Path:
        """Retain stdout and stderr separately; stream progress to the Actions log."""
        output = stdout_path or self.directory / f"{stage}.stdout.log"
        error = self.directory / f"{stage}.stderr.log"
        output.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        self.event(stage, "START", command=" ".join(argv))
        try:
            with (
                output.open("w", encoding="utf-8") as stdout,
                error.open("w", encoding="utf-8") as stderr,
            ):
                process = subprocess.Popen(
                    argv,
                    cwd=cwd,
                    stdout=stdout,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                )
                assert process.stderr is not None
                for line in process.stderr:
                    stderr.write(line)
                    stderr.flush()
                    if merge_stderr:
                        stdout.write(line)
                        stdout.flush()
                    sys.stderr.write(line)
                    sys.stderr.flush()
                process.stderr.close()
                code = process.wait()
        except OSError as exc:
            self.event(
                stage, "ERROR", elapsed_seconds=round(time.monotonic() - started, 3), error=str(exc)
            )
            raise
        self.event(
            stage,
            "PASS" if code == 0 else "FAIL",
            elapsed_seconds=round(time.monotonic() - started, 3),
            exit_code=code,
        )
        if code:
            tail = output.read_text(encoding="utf-8", errors="replace")[-4000:].strip()
            if tail:
                print(f"hosted-ci: {stage} stdout tail:\n{tail}", file=sys.stderr)
            raise HostedCommandError(f"{stage} failed ({code}); inspect {error} and {output}", code)
        return output

    def finish(self) -> None:
        self.event("lane", "PASS")


def write_action_outputs(values: dict[str, str]) -> None:
    destination = os.environ.get("GITHUB_OUTPUT")
    if destination is None:
        return
    with Path(destination).open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise ValueError(f"Multiline GitHub output is not allowed: {key}")
            stream.write(f"{key}={value}\n")


def plan_scope(
    root: Path,
    *,
    event: str,
    base: str | None,
    focus: str,
    value: str | None,
    exclude_tag: str | None,
    shard: str | None,
    head: str = "HEAD",
) -> ImpactPlan:
    """Use the same typed impact planner for PRs, branch diffs and manual cohorts."""
    if event == "pull_request":
        if not base:
            raise ValueError("Pull-request planning requires a base commit")
        if focus != "full" or value or exclude_tag:
            raise ValueError("Pull-request planning uses its Git diff, not manual focus inputs")
        return build_plan(root, base=base, head=head, shard=shard)
    if focus == "branch":
        if not value:
            raise ValueError("Branch focus requires the base branch or commit in value")
        if exclude_tag:
            raise ValueError("exclude_tag is available only with project/product/tag focus")
        return build_plan(root, base=value, head=head, shard=shard)
    if focus in {"project", "product", "tag"}:
        if not value:
            raise ValueError(f"{focus} focus requires a value")
        if focus == "project":
            return build_plan(root, select_project=value, exclude_tag=exclude_tag, shard=shard)
        if focus == "product":
            return build_plan(root, select_product=value, exclude_tag=exclude_tag, shard=shard)
        return build_plan(root, select_tag=value, exclude_tag=exclude_tag, shard=shard)
    if focus == "full":
        if value or exclude_tag:
            raise ValueError("Full focus does not take a value or exclude_tag")
        return build_plan(root, full=True, shard=shard)
    raise ValueError(f"Unknown CI focus: {focus}")


def plan_lane(root: Path, args: argparse.Namespace, log: HostedLog) -> None:
    plan = plan_scope(
        root,
        event=args.event,
        base=args.base or None,
        focus=args.focus,
        value=args.value or None,
        exclude_tag=args.exclude_tag or None,
        shard=args.shard or None,
        head=args.head,
    )
    destination = root / "build/impact.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
    systems = (
        ["ubuntu-24.04", "windows-2022", "macos-14"] if plan.scope == "full" else ["ubuntu-24.04"]
    )
    write_action_outputs(
        {
            "scope": plan.scope,
            "projects": " ".join(plan.projects),
            "docs-changed": str(plan.docs_changed).lower(),
            "portable-matrix": json.dumps({"os": systems, "python": ["3.11"]}),
        }
    )
    log.event("scope", "PASS", scope=plan.scope, projects=len(plan.projects))
    print(plan.model_dump_json(indent=2))


def matrix_lane(root: Path, projects: tuple[str, ...] | None, log: HostedLog) -> None:
    matrix = build_matrix(root, projects)
    destination = root / "build/build-matrix.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(matrix.model_dump_json(indent=2) + "\n", encoding="utf-8")
    write_action_outputs(
        {
            "matrix": matrix.model_dump_json(),
            "has-projects": str(bool(matrix.include)).lower(),
        }
    )
    log.event("matrix", "PASS", projects=len(matrix.include))
    print(matrix.model_dump_json())


def markdown_checks(root: Path, log: HostedLog) -> None:
    log.run(
        "docs-policy", (sys.executable, "-I", "-B", "-m", "kicad_tooling.docs_policy"), cwd=root
    )
    log.run(
        "rumdl",
        (sys.executable, "-I", "-m", "kicad_tooling.markdown_check", "check", ".", "--no-cache"),
        cwd=root,
    )
    log.run("mdrepo", (sys.executable, "-B", "-m", "mdrepo", "check", "."), cwd=root)


def portable_lane(
    root: Path, scope: str, projects: tuple[str, ...], docs_changed: bool, jobs: int, log: HostedLog
) -> None:
    if scope == "docs":
        markdown_checks(root, log)
    elif scope == "focused":
        if not projects:
            raise ValueError("Focused portable lane requires selected projects")
        argv = (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.ci",
            *(part for project in projects for part in ("--project", project)),
            "--jobs",
            str(jobs),
            "--output",
            "build/portable",
        )
        log.run("portable-focused", argv, cwd=root)
        if docs_changed:
            markdown_checks(root, log)
    elif scope == "full":
        log.run(
            "portable-full",
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.ci",
                "--jobs",
                str(jobs),
                "--output",
                "build/portable",
            ),
            cwd=root,
        )
    else:
        raise ValueError(f"Unknown portable scope: {scope}")


def windows_types(root: Path, log: HostedLog) -> None:
    log.run(
        "windows-types",
        (
            sys.executable,
            "-B",
            "-m",
            "pyright",
            "--pythonpath",
            sys.executable,
            "--pythonplatform",
            "Windows",
            "--pythonversion",
            "3.11",
            str(Path(__file__).resolve().parent),
        ),
        cwd=root,
        stdout_path=root / "build/portable/windows-types.txt",
    )


def windows_smoke(root: Path, log: HostedLog) -> None:
    log.run(
        "windows-inventory",
        (sys.executable, "-I", "-B", "-m", "kicad_tooling.template", "list", "--format", "json"),
        cwd=root,
        stdout_path=root / "build/portable/windows-inventory.json",
    )
    log.run(
        "windows-policy",
        (sys.executable, "-I", "-B", "-m", "kicad_tooling.ci", "--format", "json"),
        cwd=root,
        stdout_path=root / "build/portable/windows-policy.json",
    )


def checked_source(root: Path, log: HostedLog) -> None:
    log.run("source-diff", ("git", "diff", "--exit-code"), cwd=root)
    log.run("index-diff", ("git", "diff", "--cached", "--exit-code"), cwd=root)


def native_lane(
    root: Path, *, project: str, image: str, pr_head: str, fault_probes: bool, log: HostedLog
) -> None:
    if not project or "@sha256:" not in image:
        raise ValueError("Native lane requires a project and digest-pinned image")
    if sys.platform == "win32":
        raise ValueError("The Docker native lane requires a Unix runner")
    checked = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    (root / "build").mkdir(exist_ok=True)
    (root / "build/checked-commit.txt").write_text(checked + "\n", encoding="utf-8")
    log.run(
        "status-before",
        ("git", "status", "--porcelain=v1"),
        cwd=root,
        stdout_path=root / "build/status-before.txt",
    )
    log.run(
        "source-archive",
        ("git", "archive", "--format=tar.gz", "--output=build/checked-source.tar.gz", "HEAD"),
        cwd=root,
    )
    environment = os.environ.copy()
    environment.update({"CHECKED_SHA": checked, "PR_HEAD_SHA": pr_head, "PROJECT_ID": project})
    docker = (
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--entrypoint",
        "sh",
        "-e",
        "HOME=/tmp/kicad-template",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "CHECKED_SHA",
        "-e",
        "PR_HEAD_SHA",
        "-e",
        "PROJECT_ID",
        "-v",
        f"{root}:/work",
        "-w",
        "/work",
        image,
        "-ec",
    )
    try:
        log.run("docker-pull", ("docker", "pull", image), cwd=root)
        log.run(
            "native-deps",
            (sys.executable, "-I", "-B", "-m", "kicad_tooling.native_deps", "--image", image),
            cwd=root,
        )
        connector_return_lint_fixture_lane(root, project=project, image=image, log=log)
        usb_data_path_fixture_lane(root, project=project, image=image, log=log)
        power_path_fixture_lane(root, project=project, image=image, log=log)
        stm32_pin_map_fixture_lane(root, project=project, image=image, log=log)
        led_rail_fixture_lane(root, project=project, image=image, log=log)
        two_pin_component_fixture_lane(root, project=project, image=image, log=log)
        component_peer_power_output_fixture_lane(root, project=project, image=image, log=log)
        component_peer_power_assignment_fixture_lane(root, project=project, image=image, log=log)
        component_peer_signal_output_fixture_lane(root, project=project, image=image, log=log)
        component_peer_signal_input_fixture_lane(root, project=project, image=image, log=log)
        component_peer_bidirectional_fixture_lane(root, project=project, image=image, log=log)
        component_rating_fixtures_lane(root, project=project, image=image, log=log)
        power_sequence_fixture_lane(root, project=project, image=image, log=log)
        ic_rail_capacitor_fixture_lane(root, project=project, image=image, log=log)
        pcb_signal_path_drc_fixture_lane(root, project=project, image=image, log=log)
        pcb_return_fixture_lane(root, project=project, image=image, log=log)
        pcb_access_fixture_lane(root, project=project, image=image, log=log)
        pcb_decoupling_fixture_lane(root, project=project, image=image, log=log)
        pcb_switching_loop_fixture_lane(root, project=project, image=image, log=log)
        pcb_reference_plane_via_fixture_lane(root, project=project, image=image, log=log)
        pcb_reference_plane_narrow_void_fixture_lane(root, project=project, image=image, log=log)
        log.run(
            "native-check",
            (
                *docker,
                '/work/build/policy-deps/bin/python -I -m kicad_tooling.ci --kicad --project "$PROJECT_ID" '
                + "--output build/review",
            ),
            cwd=root,
            env=environment,
        )
        electrical_lane(root, project, log, native_summary=f"build/review/{project}/summary.json")
        if fault_probes:
            log.run(
                "fault-probes",
                (
                    *docker,
                    "/work/build/policy-deps/bin/python -I -m kicad_tooling.ci --fault-probes --output build/fault-probes",
                ),
                cwd=root,
                env=environment,
            )
    finally:
        checked_source(root, log)


def project_simulator(root: Path, project: str, log: HostedLog) -> str:
    from .hwrepo.electrical import load_analysis, policy_issues, selected_config, simulation_cases
    from .hwrepo.simulator_setup import ensure

    config = selected_config(root, project)
    contract = load_analysis(root, config)
    if contract is None:
        return "ngspice"
    issues = policy_issues(root, config)
    if issues:
        raise ValueError(f"{project}: unresolved electrical requirements: {issues}")
    return (
        ensure(root, contract.ngspice_version, contract.ngspice_source_sha256, log)
        if simulation_cases(contract)
        else "ngspice"
    )


def electrical_lane(
    root: Path,
    project: str,
    log: HostedLog,
    native_summary: str | None = None,
    required: bool = False,
) -> None:
    from .hwrepo.electrical import selected_config
    from .hwrepo.models import ElectricalAnalysisReport

    if selected_config(root, project).electrical is None:
        if required:
            raise ValueError(
                f"{project}: no electrical contract; run kicad-team electrical --project {project} --init"
            )
        log.event("electrical", "NOT_CONFIGURED", project=project)
        return
    simulator = project_simulator(root, project, log)
    report = root / "build" / f"electrical-{project}.json"
    summary_args = (
        ("--native-summary", native_summary) if native_summary else ("--runner", "container")
    )

    def charts() -> None:
        analysis = read_model(report, ElectricalAnalysisReport)
        log.run(
            "electrical-charts",
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.electrical_charts",
                "--root",
                str(root),
                "--receipt",
                analysis.run_directory,
                "--format",
                "json",
            ),
            cwd=root,
        )

    try:
        log.run(
            "electrical-check",
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.electrical",
                "--root",
                str(root),
                "--project",
                project,
                *summary_args,
                "--ngspice",
                simulator,
                "--format",
                "json",
            ),
            cwd=root,
            stdout_path=report,
        )
    except RuntimeError:
        # Keep plots from measured failures, while preserving the original gate failure.
        try:
            charts()
        except (OSError, ValueError, RuntimeError) as exc:
            log.event("electrical-charts", "UNAVAILABLE", error=str(exc))
        raise
    charts()


def candidate_lane(root: Path, project: str, release_id: str, log: HostedLog) -> None:
    from .hwrepo.evidence import source_state
    from .hwrepo.packaging import package, verify
    from .hwrepo.release import check
    from .hwrepo.releasing import prepare

    source = source_state(root)
    if os.environ.get("GITHUB_SHA") and source.commit != os.environ["GITHUB_SHA"]:
        raise ValueError("Checkout differs from dispatched source commit")
    simulator = project_simulator(root, project, log)
    log.event("candidate-prepare", "START", project=project, release_id=release_id)
    manifest = prepare(root, release_id, (project,), ngspice=simulator)
    readiness = check(root, manifest)
    write_model(log.directory / "readiness.json", readiness)
    if readiness.status != "PASS":
        raise ValueError(f"Release readiness failed: {readiness.issues}")
    archive = root / "build" / f"{release_id}.zip"
    write_model(
        log.directory / "package.json",
        package(root, f"build/releases/{release_id}/manifest.json", archive),
    )
    write_model(log.directory / "verified.json", verify(archive))
    checked_source(root, log)
    log.event("candidate-restore", "PASS", archive=str(archive))


def release_lane(root: Path, log: HostedLog) -> None:
    """Exercise a committed disposable fixture without changing checked-out source."""
    target = root / "build/rehearsal-source"
    release_fixture(root, target)
    log.event("fixture-copy", "PASS")
    manifest_path = target / "examples/projects/arduino-uno-status-led/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    if manifest.release_exports is None:
        raise ValueError("Reference project lacks release export settings")
    settings = manifest.release_exports.model_copy(
        update={
            "supplier_formats": ("odb", "ipc2581", "ipcd356"),
        }
    )
    write_model(manifest_path, manifest.model_copy(update={"release_exports": settings}))
    log.event("supplier-formats", "PASS")
    log.run("fixture-init", ("git", "init", "-q"), cwd=target)
    # This checkout is disposable; background maintenance can race its cleanup.
    log.run("fixture-gc", ("git", "config", "gc.auto", "0"), cwd=target)
    log.run("fixture-maintenance", ("git", "config", "maintenance.auto", "false"), cwd=target)
    log.run("fixture-add", ("git", "add", "--all"), cwd=target)
    log.run(
        "fixture-commit",
        (
            "git",
            "-c",
            "user.name=Scaffold CI fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Disposable release rehearsal",
        ),
        cwd=target,
    )
    for stage, command in (
        (
            "release-prepare",
            (
                "kicad_tooling.release",
                "prepare",
                "--project",
                "arduino-uno-status-led",
                "--release-id",
                "ci-review",
            ),
        ),
        (
            "release-package",
            (
                "kicad_tooling.release",
                "package",
                "--manifest",
                "build/releases/ci-review/manifest.json",
                "--output",
                "build/ci-review.zip",
            ),
        ),
        ("release-verify", ("kicad_tooling.release", "verify", "--archive", "build/ci-review.zip")),
    ):
        log.run(stage, (sys.executable, "-I", "-B", "-m", *command), cwd=target)
    checked_source(target, log)
    fixture = Path(__file__).resolve().parent / "fixtures/foreign-eagle-board.xml"
    conversion = log.run(
        "foreign-conversion",
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.template",
            "convert-pcb",
            "--source",
            str(fixture),
            "--project-id",
            "foreign-smoke",
            "--toolchain",
            "kicad-10.0.5",
            "--input-format",
            "eagle",
            "--runner",
            "container",
            "--format",
            "json",
        ),
        cwd=target,
        stdout_path=target / "build/foreign-pcb-conversion.json",
    )
    receipt = read_model(conversion, ForeignPcbReport)
    native_summary = receipt.native_summary
    if (
        receipt.status != "PASS"
        or not receipt.review_required
        or receipt.build_authorized
        or native_summary is None
        or native_summary.errors
        or native_summary.source_format.lower() != "eagle"
    ):
        raise ValueError("Foreign conversion receipt failed review assertions")
    source = Path(receipt.run_directory) / "stage/foreign-smoke.kicad_pro"
    if (
        source.with_suffix(".kicad_pcb").read_text(encoding="utf-8").count('(layer "Edge.Cuts")')
        != 4
    ):
        raise ValueError("Foreign PCB edge geometry changed")
    imported_path = log.run(
        "foreign-import",
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.template",
            "import-project",
            "--source",
            str(source),
            "--project-id",
            "foreign-smoke",
            "--toolchain",
            "kicad-10.0.5",
            "--format",
            "json",
        ),
        cwd=target,
    )
    imported = read_model(imported_path, ProjectImportReport)
    if imported.status != "PASS" or not imported.review_required:
        raise ValueError("Foreign import receipt failed review assertions")
    project = read_model(target / "projects/foreign-smoke/project.json", ProjectManifest)
    if project.kind is not ProjectKind.PCB_ONLY or project.status != "engineering":
        raise ValueError("Foreign import did not create an engineering PCB-only project")
    log.event("foreign-review", "PASS")


def gate_result(
    scope_result: str,
    scope: str,
    unit_result: str,
    matrix_result: str,
    kicad_result: str,
    has_projects: str,
    release_result: str,
) -> None:
    """Fail closed on every expected prerequisite, including skipped jobs."""
    if scope_result != "success" or unit_result != "success":
        raise ValueError("Planning and portable checks must both succeed")
    expected: dict[str, tuple[str, str]] = {
        "docs": ("skipped", "skipped"),
        "focused": ("success", "success"),
        "full": ("success", "success" if has_projects == "true" else "skipped"),
    }
    if scope not in expected:
        raise ValueError(f"Unknown acceptance scope: {scope}")
    expected_matrix, expected_kicad = expected[scope]
    if matrix_result != expected_matrix or kicad_result != expected_kicad:
        raise ValueError("Matrix or KiCad job outcome does not match the planned scope")
    if scope == "focused" and has_projects != "true":
        raise ValueError("Focused acceptance requires selected projects")
    if scope == "full" and has_projects not in {"true", "false"}:
        raise ValueError("Full acceptance requires a definite project-presence result")
    expected_release = "success" if scope == "full" and has_projects == "true" else "skipped"
    if release_result != expected_release:
        raise ValueError("Release rehearsal outcome does not match the planned scope")
    if scope == "full" and has_projects == "false":
        print("Scaffold checks passed; no live designs are declared or validated.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Plan PR, branch or manually focused acceptance")
    plan.add_argument(
        "--event", choices=("pull_request", "workflow_dispatch", "push", "local"), default="local"
    )
    plan.add_argument("--base")
    plan.add_argument("--head", default="HEAD")
    plan.add_argument(
        "--focus", choices=("full", "branch", "project", "product", "tag"), default="full"
    )
    plan.add_argument("--value")
    plan.add_argument("--exclude-tag")
    plan.add_argument("--shard")
    matrix = commands.add_parser("matrix", help="Build native project matrix")
    matrix.add_argument("--scope", choices=("full", "focused"), required=True)
    matrix.add_argument("--projects", default="", help="Space-separated planned IDs")
    portable = commands.add_parser("portable", help="Run full, focused or docs portable checks")
    portable.add_argument("--scope", choices=("full", "focused", "docs"), required=True)
    portable.add_argument("--projects", default="", help="Space-separated planned IDs")
    portable.add_argument("--docs-changed", choices=("true", "false"), default="false")
    portable.add_argument("--jobs", type=int, default=4)
    commands.add_parser("windows-types", help="Check Windows-targeted Python types")
    commands.add_parser("windows-smoke", help="Run Windows portability smoke tests")
    commands.add_parser("source-clean", help="Verify tracked source and index are unchanged")
    native = commands.add_parser("native", help="Run pinned KiCad lane and optional fault probes")
    native.add_argument("--project", required=True)
    native.add_argument("--image", required=True)
    native.add_argument("--pr-head", required=True)
    native.add_argument("--fault-probes", choices=("true", "false"), default="false")
    electrical = commands.add_parser(
        "electrical", help="Run required electrical checks with verified simulator setup"
    )
    electrical.add_argument("--project", required=True)
    candidate = commands.add_parser(
        "candidate", help="Prepare, package and restore a selected review candidate"
    )
    candidate.add_argument("--project", required=True)
    candidate.add_argument("--release-id", required=True)
    preview = commands.add_parser(
        "preview", help="Render 3D views with portable logs and Actions summary"
    )
    preview.add_argument(
        "--project", default=os.environ.get("PROJECT_ID"), required=not os.environ.get("PROJECT_ID")
    )
    preview.add_argument("--runner", choices=("auto", "local", "container"), default="auto")
    preview.add_argument("--cli", default="kicad-cli")
    preview.add_argument("--output", type=Path, default=Path("build/3d-preview"))
    commands.add_parser("release", help="Run disposable release and foreign-board rehearsal")
    gate = commands.add_parser("gate", help="Verify every hosted prerequisite outcome")
    gate.add_argument("--scope-result", default=os.environ.get("SCOPE_RESULT"))
    gate.add_argument("--scope", default=os.environ.get("SCOPE"))
    gate.add_argument("--unit-result", default=os.environ.get("UNIT_RESULT"))
    gate.add_argument("--matrix-result", default=os.environ.get("MATRIX_RESULT"))
    gate.add_argument("--kicad-result", default=os.environ.get("KICAD_RESULT"))
    gate.add_argument("--has-projects", default=os.environ.get("HAS_PROJECTS"))
    gate.add_argument("--release-result", default=os.environ.get("RELEASE_RESULT"))
    args = parser.parse_args()
    root = args.root.resolve()
    log = HostedLog(root, args.command)
    try:
        if args.command == "plan":
            plan_lane(root, args, log)
        elif args.command == "matrix":
            selected = tuple(args.projects.split()) if args.scope == "focused" else None
            if args.scope == "focused" and not selected:
                raise ValueError("Focused matrix requires selected projects")
            matrix_lane(root, selected, log)
        elif args.command == "portable":
            portable_lane(
                root,
                args.scope,
                tuple(args.projects.split()),
                args.docs_changed == "true",
                args.jobs,
                log,
            )
        elif args.command == "windows-types":
            windows_types(root, log)
        elif args.command == "windows-smoke":
            windows_smoke(root, log)
        elif args.command == "source-clean":
            checked_source(root, log)
        elif args.command == "native":
            native_lane(
                root,
                project=args.project,
                image=args.image,
                pr_head=args.pr_head,
                fault_probes=args.fault_probes == "true",
                log=log,
            )
        elif args.command == "release":
            release_lane(root, log)
        elif args.command == "electrical":
            electrical_lane(root, args.project, log, required=True)
        elif args.command == "candidate":
            candidate_lane(root, args.project, args.release_id, log)
        elif args.command == "preview":
            preview_lane(
                root, args.project, log, runner=args.runner, cli=args.cli, output=args.output
            )
        elif args.command == "gate":
            gate_result(
                args.scope_result,
                args.scope,
                args.unit_result,
                args.matrix_result,
                args.kicad_result,
                args.has_projects,
                args.release_result,
            )
        log.finish()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        log.event("lane", "FAIL", error=str(exc))
        print(f"hosted-ci: {exc}", file=sys.stderr)
        return exc.returncode if isinstance(exc, HostedCommandError) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
