"""Hosted CI orchestration with the same selection and checks available locally.

GitHub Actions owns runner allocation, job dependencies and artifact uploads. This
module owns decisions and commands, recording each stage under ignored build/.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .ci_matrix import build_matrix
from .hwrepo.contracts import read_kicad_erc_report, read_model, write_model
from .hwrepo.hosted_preview import preview_lane
from .hwrepo.models import (
    ForeignPcbReport,
    ImpactPlan,
    ProjectImportReport,
    ProjectKind,
    ProjectManifest,
    SerialLabelFixtureExpectedNets,
)
from .hwrepo.repository import ephemeral, generated_artifact
from .impact import build_plan


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


def empty_netlist_evidence_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify the native empty-netlist trigger on each supported project image."""
    import hashlib
    import json
    import os
    import shutil
    import sys
    import tempfile

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import NetlistContract
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Empty-netlist evidence fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    fixtures = {
        "empty": (
            fixture_root / "empty-native-netlist/empty.kicad_sch",
            "ed107ec68043c2eb02fa6566b289b35f119b37c3296bbd1a0f12705ba36b2c9b",
        ),
        "nonempty-control": (
            fixture_root
            / "serial-peer-connector-reference-native/serial-connector-control.kicad_sch",
            "7d086f4f838504fa3cefc906f7f9e415240b10d89e95c9063c19780922915f16",
        ),
    }
    scratch = Path(
        tempfile.mkdtemp(prefix=f"empty-netlist-evidence-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    source_hashes: dict[str, str] = {}
    for case, (fixture, expected_hash) in fixtures.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(fixture, target)
        source_hash = digest(target)
        if source_hash != expected_hash:
            raise ValueError(f"Synthetic {case} schematic changed from its reviewed hash")
        source_hashes[case] = source_hash
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
        "for case in empty nonempty-control; do\n"
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
        "HOME=/tmp/kicad-empty-netlist-evidence",
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
        "empty-netlist-evidence/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "empty-netlist-evidence/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            error=command.error or command.stderr or command.stdout,
        )
        raise ValueError(f"Native empty-netlist fixture export failed for {project}")
    log.event(
        "empty-netlist-evidence/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        returncode=command.returncode,
    )

    for case in fixtures:
        reports: list[NetlistContract] = []
        raw_hashes: list[str] = []
        normalized_bytes: list[bytes] = []
        for run in ("first", "repeat"):
            path = output / f"{case}.{run}.netlist.xml"
            raw_hashes.append(digest(path))
            observed = read_netlist(path)
            reports.append(observed)
            normalized_bytes.append(
                json.dumps(
                    observed.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
        if normalized_bytes[0] != normalized_bytes[1]:
            raise ValueError(f"Native {case} exports differ after netlist normalization")
        observed = reports[0]
        if case == "empty" and (observed.components or observed.nets):
            raise ValueError("Synthetic empty schematic unexpectedly exported components or nets")
        if case != "empty" and not observed.components:
            raise ValueError("Synthetic nonempty control exported no component records")
        normalized_hash = hashlib.sha256(normalized_bytes[0]).hexdigest()
        repeat_normalized_hash = hashlib.sha256(normalized_bytes[1]).hexdigest()
        log.event(
            f"empty-netlist-evidence/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[0],
            repeat_netlist_sha256=raw_hashes[1],
            normalized_netlist_sha256=normalized_hash,
            repeat_normalized_netlist_sha256=repeat_normalized_hash,
            component_count=len(observed.components),
            net_count=len(observed.nets),
            repeatable="true",
            repeatability_basis="canonical_typed_netlist",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )


def connector_return_lint_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Run a synthetic split/common connector-return regression in pinned KiCad."""
    import hashlib
    import os

    from .hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import grounding_checks, pin_relationship_checks, selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ConnectorInterfaceReview,
        ConnectorInventoryReview,
        ConnectorPinRole,
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        GroundDomain,
        GroundingAnalysis,
        InterfacePin,
        InterfaceRecord,
        NetlistContract,
        PinConnectivityAnalysis,
        PinRelationshipRule,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Connector return lint fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    fixtures = {
        "fault": fixture_root / "cohort-connector-ground-domains/fault.kicad_sch",
        "control": fixture_root / "cohort-connector-ground-domains/control.kicad_sch",
        "cross-symbol-fault": (
            fixture_root / "cohort-cross-symbol-connectors/cross-symbol-fault.kicad_sch"
        ),
        "cross-symbol-control": (
            fixture_root / "cohort-cross-symbol-connectors/cross-symbol-control.kicad_sch"
        ),
        "cross-symbol-open": (
            fixture_root / "cohort-cross-symbol-connectors/cross-symbol-open.kicad_sch"
        ),
        "mapped-supply-fault": (
            fixture_root / "cohort-mapped-connector-supplies/split-supply-fault.kicad_sch"
        ),
        "mapped-supply-control": (
            fixture_root / "cohort-mapped-connector-supplies/common-supply-control.kicad_sch"
        ),
        "channel-power-fault": (fixture_root / "cohort-channel-power-names/fault.kicad_sch"),
        "channel-power-control": (fixture_root / "cohort-channel-power-names/control.kicad_sch"),
        "four-db9-fault": (fixture_root / "four-port-db9-returns/fault.kicad_sch"),
        "four-db9-control": (fixture_root / "four-port-db9-returns/control.kicad_sch"),
        "four-db9-neutral-fault": (
            fixture_root / "four-port-db9-returns/numeric-function-neutral-fault.kicad_sch"
        ),
        "four-db9-neutral-control": (
            fixture_root / "four-port-db9-returns/numeric-function-neutral-control.kicad_sch"
        ),
        "peer-power-fault": (fixture_root / "generic-peer-power-pin/fault.kicad_sch"),
        "peer-power-control": (fixture_root / "generic-peer-power-pin/control.kicad_sch"),
        "peer-pin-outlier-fault": (
            fixture_root / "generic-peer-pin-assignment-native/fault.kicad_sch"
        ),
        "peer-pin-outlier-control": (
            fixture_root / "generic-peer-pin-assignment-native/control.kicad_sch"
        ),
        "peer-pin-minority-fault": (
            fixture_root / "generic-peer-pin-assignment-native/minority-fault.kicad_sch"
        ),
        "peer-pin-divergence-fault": (
            fixture_root / "generic-peer-pin-assignment-native/divergence-fault.kicad_sch"
        ),
        "generic-placeholder-divergence-fault": (
            fixture_root
            / "generic-peer-pin-assignment-native/generic-placeholder-divergence-fault.kicad_sch"
        ),
        "peer-scope-split-return-fault": (
            fixture_root
            / "generic-peer-pin-assignment-native/peer-scope-split-return-fault.kicad_sch"
        ),
        "generic-placeholder-control": (
            fixture_root
            / "generic-peer-pin-assignment-native/generic-placeholder-control.kicad_sch"
        ),
        "two-peer-open-fault": (
            fixture_root / "generic-peer-pin-assignment-native/two-peer-open-fault.kicad_sch"
        ),
        "two-peer-no-connect-fault": (
            fixture_root / "generic-peer-pin-assignment-native/two-peer-no-connect-fault.kicad_sch"
        ),
        "two-peer-common-control": (
            fixture_root / "generic-peer-pin-assignment-native/two-peer-common-control.kicad_sch"
        ),
        "single-offboard-port-control": (
            fixture_root
            / "generic-peer-pin-assignment-native/single-offboard-port-control.kicad_sch"
        ),
        "unconnected-generic-power-input-fault": (
            fixture_root / "unconnected-generic-power-input-connector/fault.kicad_sch"
        ),
        "unconnected-generic-power-input-control": (
            fixture_root / "unconnected-generic-power-input-connector/control.kicad_sch"
        ),
        "unconnected-generic-component-power-input-fault": (
            fixture_root / "generic-component-power-input/fault.kicad_sch"
        ),
        "unconnected-generic-component-power-input-control": (
            fixture_root / "generic-component-power-input/control.kicad_sch"
        ),
        "unconnected-generic-component-power-input-no-connect-fault": (
            fixture_root / "generic-component-power-input/no-connect-fault.kicad_sch"
        ),
        "unconnected-generic-component-power-input-dnp-control": (
            fixture_root / "generic-component-power-input/dnp-control.kicad_sch"
        ),
    }
    cases = tuple(fixtures)
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    expected_source_hashes = {
        "fault": "aea557c738a417192ccfce0e7228b5832aab566f66c2a354dce72f5df7882474",
        "control": "9584fbcc1f0560ac66306691f49d161617199b240cb7520588ad298a69b72176",
        "cross-symbol-fault": "941aa1acc62384d86fe04e7dec77638a5e23cd8b67b196bc1d93130e5e99f21e",
        "cross-symbol-control": "5b9f1a9d18b4e57495d090e815ff192c44f61b8a164ef03622e3d962ac553baf",
        "cross-symbol-open": "180c28fd280b71febe0c636e799217f0d86a3659c45e280cb86a768b7a03533a",
        "mapped-supply-fault": "0991c6df2403df88ff33d5c359b14487b6aa385023bd864573ce236478449213",
        "mapped-supply-control": "c45d390f138ebb9e440a1c6b0fea822f858ce9e31bfa229b28aaddc248adca3b",
        "channel-power-fault": "d6a52dd120801e0bf5776e82421ceb64670b26a9ace28afafd89b608a61aabb3",
        "channel-power-control": "37c7c28963b530a679cd3dc2087a4fa3b5d97dda52250332556406c66b9e1fc7",
        "four-db9-fault": "c4a842c1685d5fbf21985aa22bd0b6436e163025f4381a8ac2544621c264e546",
        "four-db9-control": "3c00cfdee7a7bbba3439baf49f82eb6911ead068cf04ac0782f8f8fe7297cecc",
        "four-db9-neutral-fault": "8b54babacd735da898cbd477b641a57085ff03b74bf0d9aa665fc8625a36f65f",
        "four-db9-neutral-control": "49e3bca48e79e4b46ce4eba8298026b5c730fca56b119a3ec407dfaafbcf54cd",
        "peer-power-fault": "4e2382aede1643770a466a9c902b1e960f8a8ab0d1bc676a03db33dfe6e582a8",
        "peer-power-control": "e50d57b2739dc49d3b164e0ea141f48835967fdc1982d3cfdd702f671dc7d197",
        "peer-pin-outlier-fault": "e9945c83c351ece43064a6c09c770fd8f3ab5fadd550ac58ee5d001f5d8842e2",
        "peer-pin-outlier-control": "94a9897ea50645a4232abf005477e620a4cd9b12330dfc2d6f32734e8157b8be",
        "peer-pin-minority-fault": "a071543178ad7668d20a3653fea5196cf556c3b96338b81dbeac97a6360ede2c",
        "peer-pin-divergence-fault": "c278b2ff86c869a6dba7c19ee08f064a863d282d251be44fd47c1e8a71254e57",
        "generic-placeholder-divergence-fault": "f6f4c9b419ab590366ca329b1ac0749706b29536017f2f24145de7ef6bdfaf30",
        "peer-scope-split-return-fault": "a597bbdee4794b3de8ff08bce5691363a7a123bde303462d64cb692a6a97968e",
        "generic-placeholder-control": "d63a7f7cd79fd0855de599041dacb8219313ffbb2667f37d1e61e88fbec880c0",
        "two-peer-open-fault": "3de502ac74b394afb21cdaef8130026f11f7aa6050018a571dc65b10ae864350",
        "two-peer-no-connect-fault": "8801b0ff24e9f012e6f2df10247cdc04668db40d3233eb5d2111d279cfdf7256",
        "two-peer-common-control": "ae23ddb802c9a0f5cf30e89699a2cf6f48b3d15b6e18967387e756dcdf6fa3df",
        "single-offboard-port-control": "ceaa7038e372ec74a00f7e7c2cb5311377df01624760ab555adb413c4e02d8e9",
        "unconnected-generic-power-input-fault": "2e16c602d6ba0068360b3f8b493351f6d7e4d7adbe94946d17db883587f0528f",
        "unconnected-generic-power-input-control": "b05c1a3994a4f26f07e18bdfe28c8caaf4a298cbb66b6d1814b20c9a7dce2c13",
        "unconnected-generic-component-power-input-fault": "40271ae0a6551c8c7209427b30e89d9a95267aa92765eaac1a5cdf65e1ffd1a1",
        "unconnected-generic-component-power-input-control": "67d6ad249e1caa2095b3a408457e6a1710fb9bb6ef7d8e5cb1fdcdd7710b43ec",
        "unconnected-generic-component-power-input-no-connect-fault": "664e619ceaba71c27bd7acfaa0bb4563ab3203b33a03c564b2a8f7c6bdf4c4bd",
        "unconnected-generic-component-power-input-dnp-control": "3be52ef83ba54bf0f43bede043095afe42583319e9fd6fa19f17aba250cc3c81",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("Connector-return fixture sources differ from the reviewed hashes")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"connector-return-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        shutil.copyfile(fixture, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} fixture changed while preparing native input")
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
        f"for case in {' '.join(cases)}; do\n"
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
        "HOME=/tmp/kicad-connector-fixtures",
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
        "connector-return-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "connector-return-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native connector fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        "connector-return-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    if any(
        digest(fixtures[case]) != source_hashes[case]
        or digest(inputs / f"{case}.kicad_sch") != source_hashes[case]
        for case in cases
    ):
        raise ValueError("Synthetic connector fixture source changed during native export")

    reports: dict[tuple[str, str], DesignLintReport] = {}
    observed_contracts: dict[tuple[str, str], NetlistContract] = {}
    netlist_hashes: dict[tuple[str, str], str] = {}
    normalized_netlist_hashes: dict[tuple[str, str], str] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native connector fixture omitted {netlist_path.name}")
            netlist_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            observed_contracts[(case, run)] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_netlist_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-connector-returns-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=netlist_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())

    expected_rules = {"connector.repeated_pin_function", "net.numbered_returns"}
    fault = reports[("fault", "first")]
    repeated = next(
        (
            finding
            for finding in fault.findings
            if finding.rule_id == "connector.repeated_pin_function"
        ),
        None,
    )
    if (
        fault.status != "REVIEW"
        or {finding.rule_id for finding in fault.findings} != expected_rules
        or repeated is None
        or dict(repeated.evidence)
        != {
            "J1.1": ("GND1",),
            "J1.2": ("GND1",),
            "J2.1": ("GND2",),
            "J2.2": ("GND2",),
        }
    ):
        raise ValueError("Split-return fixture no longer produces its expected REVIEW evidence")
    control = reports[("control", "first")]
    if control.status != "PASS" or control.findings:
        raise ValueError("Common-return control fixture no longer passes without findings")

    generic_power_fault = reports[("unconnected-generic-power-input-fault", "first")]
    generic_power_control = reports[("unconnected-generic-power-input-control", "first")]
    expected_generic_power_subjects = {
        "J1.1: generic native power-input pin is unassigned",
        "J2.1: generic native power-input pin is unassigned",
    }
    if (
        generic_power_fault.status != "REVIEW"
        or {item.rule_id for item in generic_power_fault.findings}
        != {"connector.unconnected_power_input"}
        or {item.subject for item in generic_power_fault.findings}
        != expected_generic_power_subjects
        or generic_power_control.status != "PASS"
        or generic_power_control.findings
        or observed_contracts[
            ("unconnected-generic-power-input-fault", "first")
        ].pin_electrical_types
        != {"J1.1": "power_in", "J1.2": "passive", "J2.1": "power_in", "J2.2": "passive"}
        or observed_contracts[("unconnected-generic-power-input-control", "first")].nets.get("+5V")
        != ("J1.1", "J2.1")
    ):
        raise ValueError(
            "Generic connector power-input fixture lost its exact native fault/control result"
        )

    generic_component_fault = reports[("unconnected-generic-component-power-input-fault", "first")]
    generic_component_control = reports[
        ("unconnected-generic-component-power-input-control", "first")
    ]
    generic_component_no_connect = reports[
        ("unconnected-generic-component-power-input-no-connect-fault", "first")
    ]
    generic_component_dnp = reports[
        ("unconnected-generic-component-power-input-dnp-control", "first")
    ]
    expected_component_subject = "U1.1: generic native power-input pin is unassigned"
    if (
        generic_component_fault.status != "REVIEW"
        or {item.rule_id for item in generic_component_fault.findings}
        != {"component.unconnected_power_input"}
        or {item.subject for item in generic_component_fault.findings}
        != {expected_component_subject}
        or generic_component_no_connect.status != "REVIEW"
        or {item.rule_id for item in generic_component_no_connect.findings}
        != {"component.unconnected_power_input"}
        or {item.subject for item in generic_component_no_connect.findings}
        != {expected_component_subject}
        or generic_component_control.status != "PASS"
        or generic_component_control.findings
        or generic_component_dnp.status != "PASS"
        or generic_component_dnp.findings
        or observed_contracts[
            ("unconnected-generic-component-power-input-fault", "first")
        ].pin_electrical_types
        != {"U1.1": "power_in", "U1.2": "passive"}
        or observed_contracts[
            ("unconnected-generic-component-power-input-control", "first")
        ].nets.get("POWER_INPUT_TEST")
        != ("U1.1",)
        or "U1"
        not in observed_contracts[
            ("unconnected-generic-component-power-input-dnp-control", "first")
        ].dnp_components
    ):
        raise ValueError(
            "Generic component power-input fixture lost its exact native fault/control result"
        )

    channel_fault = reports[("channel-power-fault", "first")]
    channel_fault_rails = next(
        (
            finding
            for finding in channel_fault.findings
            if finding.rule_id == "net.numbered_power_rails"
        ),
        None,
    )
    if (
        channel_fault.status != "REVIEW"
        or channel_fault_rails is None
        or channel_fault_rails.subject != "CH VDD"
        or dict(channel_fault_rails.evidence) != {"CH2_VDD": ("J1.3",), "CH3_VDD": ("J2.3",)}
    ):
        raise ValueError("Channel-prefixed power-name fault lost its exact native lint evidence")

    channel_control = reports[("channel-power-control", "first")]
    if channel_control.status != "PASS" or channel_control.findings:
        raise ValueError("Common channel-prefixed supply control no longer passes")
    if observed_contracts[("channel-power-control", "first")].nets.get("CH2_VDD") != (
        "J1.3",
        "J2.3",
    ):
        raise ValueError("Channel-prefixed common-net control lost its native connector pins")

    db9_fault = reports[("four-db9-fault", "first")]
    db9_repeated = next(
        (
            finding
            for finding in db9_fault.findings
            if finding.rule_id == "connector.repeated_pin_function"
        ),
        None,
    )
    expected_db9_pins = {
        f"J{reference}.{pin}": (f"0V PWM {reference}",)
        for reference in range(1, 5)
        for pin in (7, 9)
    }
    db9_numbered = next(
        (finding for finding in db9_fault.findings if finding.rule_id == "net.numbered_returns"),
        None,
    )
    if (
        db9_fault.status != "REVIEW"
        or {finding.rule_id for finding in db9_fault.findings}
        != {"connector.repeated_pin_function", "net.numbered_returns"}
        or db9_repeated is None
        or dict(db9_repeated.evidence) != expected_db9_pins
        or db9_numbered is None
        or dict(db9_numbered.evidence)
        != {
            f"0V PWM {reference}": (f"J{reference}.7", f"J{reference}.9")
            for reference in range(1, 5)
        }
    ):
        actual = {
            "status": db9_fault.status,
            "findings": tuple(
                (finding.rule_id, finding.subject, dict(finding.evidence))
                for finding in db9_fault.findings
            ),
            "nets": observed_contracts[("four-db9-fault", "first")].nets,
            "pin_functions": observed_contracts[("four-db9-fault", "first")].pin_functions,
        }
        raise ValueError(
            f"Four-port DB9 return fault lost exact pins 7/9 REVIEW evidence: {actual!r}"
        )
    db9_control = reports[("four-db9-control", "first")]
    if db9_control.status != "PASS" or db9_control.findings:
        raise ValueError("Common four-port DB9 return control no longer passes cleanly")
    db9_control_nets = observed_contracts[("four-db9-control", "first")].nets
    if db9_control_nets.get("0V PWM") != tuple(
        f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)
    ):
        raise ValueError("Common four-port DB9 control lost its eight native pin assignments")

    db9_return_pins = tuple(f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9))
    common_grounding = GroundingAnalysis(
        basis="Synthetic approved DB9 pinout requires all return contacts on one domain",
        domains=(GroundDomain(net="0V PWM", pins=db9_return_pins),),
    )
    isolated_grounding = GroundingAnalysis(
        basis="Synthetic approved DB9 pinout requires one isolated return domain per connector",
        domains=tuple(
            GroundDomain(
                net=f"0V PWM {reference}",
                pins=(f"J{reference}.7", f"J{reference}.9"),
            )
            for reference in range(1, 5)
        ),
    )
    expected_grounding_results = {
        "common-fault": {
            "grounding/0V PWM": "FAIL",
            "grounding/component-coverage": "PASS",
            "grounding/return-net-review": "FAIL",
        },
        "common-control": {
            "grounding/0V PWM": "PASS",
            "grounding/component-coverage": "PASS",
        },
        "isolated-fault": {
            **{f"grounding/0V PWM {reference}": "PASS" for reference in range(1, 5)},
            "grounding/component-coverage": "PASS",
            "grounding/return-net-review": "PASS",
        },
        "isolated-control": {
            **{f"grounding/0V PWM {reference}": "FAIL" for reference in range(1, 5)},
            "grounding/component-coverage": "PASS",
        },
    }
    grounding_cases = {
        "common-fault": (common_grounding, "four-db9-fault", "common-net"),
        "common-control": (common_grounding, "four-db9-control", "common-net"),
        "isolated-fault": (isolated_grounding, "four-db9-fault", "separate-per-port"),
        "isolated-control": (isolated_grounding, "four-db9-control", "separate-per-port"),
    }
    for case, (spec, source_case, relationship) in grounding_cases.items():
        checks = {
            item.id: item.status
            for item in grounding_checks(spec, observed_contracts[(source_case, "first")])
        }
        if checks != expected_grounding_results[case]:
            raise ValueError(f"Four-port DB9 {case} grounding requirement changed: {checks}")
        spec_digest = hashlib.sha256(
            json.dumps(
                spec.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        log.event(
            f"connector-return-fixture/ground-contract-{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[source_case],
            netlist_sha256=netlist_hashes[(source_case, "first")],
            repeat_netlist_sha256=netlist_hashes[(source_case, "repeat")],
            normalized_netlist_sha256=normalized_netlist_hashes[(source_case, "first")],
            repeat_normalized_netlist_sha256=normalized_netlist_hashes[(source_case, "repeat")],
            grounding_contract_sha256=spec_digest,
            relationship=relationship,
            contract_status=(
                "FAIL" if any(status == "FAIL" for status in checks.values()) else "PASS"
            ),
            checks=";".join(f"{check_id}={status}" for check_id, status in sorted(checks.items())),
            repeatable=(
                "true"
                if normalized_netlist_hashes[(source_case, "first")]
                == normalized_netlist_hashes[(source_case, "repeat")]
                else "false"
            ),
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    common_pin_connectivity = PinConnectivityAnalysis(
        basis="Synthetic approved DB9 pinout requires all return contacts on one net",
        rules=(
            PinRelationshipRule(
                id="db9-common-return",
                basis="All DB9 return contacts share the approved return net",
                topology="common_net",
                pins=db9_return_pins,
                net="0V PWM",
            ),
        ),
    )
    isolated_pin_connectivity = PinConnectivityAnalysis(
        basis="Synthetic approved DB9 pinout requires isolated per-connector return nets",
        rules=tuple(
            PinRelationshipRule(
                id=f"db9-{reference}-isolated-return",
                basis=f"Connector J{reference} return contacts share its isolated return net",
                topology="common_net",
                pins=(f"J{reference}.7", f"J{reference}.9"),
                net=f"0V PWM {reference}",
            )
            for reference in range(1, 5)
        ),
    )
    peer_common_power = PinConnectivityAnalysis(
        basis="Synthetic approved three-port pinout requires one shared +5V contact net",
        rules=(
            PinRelationshipRule(
                id="peer-common-power",
                basis="All three reviewed connector power contacts share +5V",
                topology="common_net",
                pins=("J1.1", "J2.1", "J3.1"),
                net="+5V",
            ),
        ),
    )
    peer_independent_power = PinConnectivityAnalysis(
        basis=(
            "Synthetic approved variant has independent J1/J2 power outputs and an unused J3 pin"
        ),
        rules=(
            PinRelationshipRule(
                id="peer-independent-power-outputs",
                basis="J1 and J2 power contacts are separate switched outputs",
                topology="separate_nets",
                pins=("J1.1", "J2.1"),
            ),
            PinRelationshipRule(
                id="peer-j3-power-unused",
                basis="J3.1 is intentionally unconnected on this approved variant",
                topology="unconnected",
                pins=("J3.1",),
            ),
        ),
    )
    stale_pin_reference = PinConnectivityAnalysis(
        basis="Synthetic contract typo must not count an absent symbol pin as unused",
        rules=(
            PinRelationshipRule(
                id="stale-pin-reference",
                basis="J1.99 is intentionally unused",
                topology="unconnected",
                pins=("J1.99",),
            ),
        ),
    )
    expected_pin_connectivity_results = {
        "common-fault": {"pin-connectivity/db9-common-return": "FAIL"},
        "common-control": {"pin-connectivity/db9-common-return": "PASS"},
        "isolated-fault": {
            **{
                f"pin-connectivity/db9-{reference}-isolated-return": "PASS"
                for reference in range(1, 5)
            }
        },
        "isolated-control": {
            **{
                f"pin-connectivity/db9-{reference}-isolated-return": "FAIL"
                for reference in range(1, 5)
            }
        },
        "peer-common-open-fault": {"pin-connectivity/peer-common-power": "FAIL"},
        "peer-common-control": {"pin-connectivity/peer-common-power": "PASS"},
        "peer-independent-control": {
            "pin-connectivity/peer-independent-power-outputs": "PASS",
            "pin-connectivity/peer-j3-power-unused": "PASS",
        },
        "peer-independent-common-net-mismatch": {
            "pin-connectivity/peer-independent-power-outputs": "FAIL",
            "pin-connectivity/peer-j3-power-unused": "FAIL",
        },
        "stale-pin-reference": {"pin-connectivity/stale-pin-reference": "FAIL"},
    }
    pin_connectivity_cases = {
        "common-fault": (common_pin_connectivity, "four-db9-fault", "common-net"),
        "common-control": (common_pin_connectivity, "four-db9-control", "common-net"),
        "isolated-fault": (
            isolated_pin_connectivity,
            "four-db9-fault",
            "separate-per-port",
        ),
        "isolated-control": (
            isolated_pin_connectivity,
            "four-db9-control",
            "separate-per-port",
        ),
        "peer-common-open-fault": (
            peer_common_power,
            "peer-pin-outlier-fault",
            "common-net",
        ),
        "peer-common-control": (
            peer_common_power,
            "peer-pin-outlier-control",
            "common-net",
        ),
        "peer-independent-control": (
            peer_independent_power,
            "peer-power-fault",
            "independent-outputs-plus-unused-contact",
        ),
        "peer-independent-common-net-mismatch": (
            peer_independent_power,
            "peer-power-control",
            "independent-outputs-plus-unused-contact",
        ),
        "stale-pin-reference": (
            stale_pin_reference,
            "four-db9-control",
            "stale-symbol-pin",
        ),
    }
    for case, (spec, source_case, relationship) in pin_connectivity_cases.items():
        check_results = pin_relationship_checks(spec, observed_contracts[(source_case, "first")])
        checks = {item.id: item.status for item in check_results}
        check_details = {item.id: item.detail for item in check_results}
        if checks != expected_pin_connectivity_results[case]:
            raise ValueError(f"Pin-connectivity requirement {case} changed: {checks}")
        spec_digest = hashlib.sha256(
            json.dumps(
                spec.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        log.event(
            f"connector-return-fixture/pin-connectivity-contract-{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[source_case],
            netlist_sha256=netlist_hashes[(source_case, "first")],
            repeat_netlist_sha256=netlist_hashes[(source_case, "repeat")],
            normalized_netlist_sha256=normalized_netlist_hashes[(source_case, "first")],
            repeat_normalized_netlist_sha256=normalized_netlist_hashes[(source_case, "repeat")],
            pin_connectivity_contract_sha256=spec_digest,
            relationship=relationship,
            check_details=json.dumps(
                check_details,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ),
            contract_status=(
                "FAIL" if any(status == "FAIL" for status in checks.values()) else "PASS"
            ),
            checks=";".join(f"{check_id}={status}" for check_id, status in sorted(checks.items())),
            repeatable=(
                "true"
                if normalized_netlist_hashes[(source_case, "first")]
                == normalized_netlist_hashes[(source_case, "repeat")]
                else "false"
            ),
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    db9_neutral_fault = reports[("four-db9-neutral-fault", "first")]
    db9_neutral_findings = {
        finding.subject: finding
        for finding in db9_neutral_fault.findings
        if finding.rule_id == "connector.repeated_pin_function"
    }
    expected_neutral_fault_pins = {
        f"J{reference}.{pin}": (f"NET_{chr(64 + reference)}",)
        for reference in range(1, 5)
        for pin in (7, 9)
    }
    if (
        db9_neutral_fault.status != "REVIEW"
        or {finding.rule_id for finding in db9_neutral_fault.findings}
        != {"connector.repeated_pin_function", "connector.no_connected_return"}
        or set(db9_neutral_findings) != {"Lint:DB9: 7", "Lint:DB9: 9"}
        or {
            finding.subject
            for finding in db9_neutral_fault.findings
            if finding.rule_id == "connector.no_connected_return"
        }
        != {f"J{reference}: no connected return" for reference in range(1, 5)}
        or {
            pin: assignment
            for finding in db9_neutral_findings.values()
            for pin, assignment in finding.evidence.items()
        }
        != expected_neutral_fault_pins
        or observed_contracts[("four-db9-neutral-fault", "first")].pin_functions.get("J1.7") != "7"
        or observed_contracts[("four-db9-neutral-fault", "first")].pin_functions.get("J1.9") != "9"
    ):
        actual = {
            "status": db9_neutral_fault.status,
            "findings": tuple(
                (finding.rule_id, finding.subject, dict(finding.evidence))
                for finding in db9_neutral_fault.findings
            ),
            "nets": observed_contracts[("four-db9-neutral-fault", "first")].nets,
            "pin_functions": observed_contracts[("four-db9-neutral-fault", "first")].pin_functions,
        }
        raise ValueError(f"Numeric DB9 neutral-net fixture lost exact REVIEW evidence: {actual!r}")
    db9_neutral_control = reports[("four-db9-neutral-control", "first")]
    if (
        db9_neutral_control.status != "REVIEW"
        or {finding.rule_id for finding in db9_neutral_control.findings}
        != {"connector.no_connected_return"}
        or {finding.subject for finding in db9_neutral_control.findings}
        != {f"J{reference}: no connected return" for reference in range(1, 5)}
    ):
        raise ValueError("Neutral common-net control lost its return-role coverage prompts")
    if observed_contracts[("four-db9-neutral-control", "first")].nets.get("NET_COMMON") != tuple(
        f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)
    ):
        raise ValueError("Common neutral-net DB9 control lost its eight native pin assignments")

    peer_power_fault = reports[("peer-power-fault", "first")]
    peer_power_findings = {finding.rule_id: finding for finding in peer_power_fault.findings}
    if (
        peer_power_fault.status != "REVIEW"
        or set(peer_power_findings)
        != {"connector.repeated_pin_function", "net.numbered_power_rails"}
        or dict(peer_power_findings["connector.repeated_pin_function"].evidence)
        != {"J1.1": ("+5V_1",), "J2.1": ("5V-2",), "J3.1": ()}
        or dict(peer_power_findings["net.numbered_power_rails"].evidence)
        != {"+5V_1": ("J1.1",), "5V-2": ("J2.1",)}
    ):
        raise ValueError("Generic peer power fault lost its exact open-pin REVIEW evidence")
    peer_power_control = reports[("peer-power-control", "first")]
    if peer_power_control.status != "PASS" or peer_power_control.findings:
        raise ValueError("Common generic peer power control no longer passes cleanly")
    if observed_contracts[("peer-power-control", "first")].nets.get("+5V") != (
        "J1.1",
        "J2.1",
        "J3.1",
    ):
        raise ValueError("Common generic peer power control lost its three native pin assignments")

    peer_pin_fault = reports[("peer-pin-outlier-fault", "first")]
    peer_pin_findings = {finding.rule_id: finding for finding in peer_pin_fault.findings}
    if (
        peer_pin_fault.status != "REVIEW"
        or set(peer_pin_findings) != {"connector.peer_pin_assignment_outlier"}
        or peer_pin_findings["connector.peer_pin_assignment_outlier"].subject
        != "Lint:PeerPowerPort pin 1"
        or dict(peer_pin_findings["connector.peer_pin_assignment_outlier"].evidence)
        != {
            "J1.1": ("+5V",),
            "J2.1": ("+5V",),
            "J3.1": (),
            "symbol": ("Lint:PeerPowerPort",),
            "pin_number": ("1",),
            "outlier_pins": ("J3.1",),
        }
    ):
        raise ValueError("Generic exact-symbol peer pin fault lost its exact native evidence")
    peer_pin_control = reports[("peer-pin-outlier-control", "first")]
    if peer_pin_control.status != "PASS" or peer_pin_control.findings:
        raise ValueError("Common generic exact-symbol peer pin control no longer passes cleanly")
    peer_pin_coverage_receipts: dict[str, str] = {}
    for (
        case,
        expected_connector_count,
        expected_outlier_findings,
        expected_common_groups,
        expected_open_groups,
    ) in (
        ("peer-pin-outlier-fault", 3, 1, 1, 1),
        ("peer-pin-outlier-control", 3, 0, 2, 0),
        ("two-peer-open-fault", 2, 1, 1, 1),
        ("two-peer-no-connect-fault", 2, 1, 1, 1),
        ("two-peer-common-control", 2, 0, 2, 0),
    ):
        report = reports[(case, "first")]
        coverage = report.connector_peer_pin_coverage
        if (
            coverage is None
            or coverage.status != "EVALUATED"
            or coverage.netlist_sha256 != netlist_hashes[(case, "first")]
            or coverage.connector_candidate_count != expected_connector_count
            or coverage.fitted_connector_count != expected_connector_count
            or coverage.exact_symbol_peer_group_count != 1
            or coverage.exact_symbol_pin_group_count != 2
            or coverage.incomplete_pin_inventory_references
            or coverage.exact_symbol_pin_groups_with_common_assignment_count
            != expected_common_groups
            or coverage.exact_symbol_pin_groups_with_open_assignment_count != expected_open_groups
            or coverage.peer_pin_outlier_finding_count != expected_outlier_findings
        ):
            raise ValueError(f"Native {case} lost source-bound connector peer-pin coverage")
        peer_pin_coverage_receipts[case] = json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    two_peer_fault = reports[("two-peer-open-fault", "first")]
    two_peer_findings = {finding.rule_id: finding for finding in two_peer_fault.findings}
    if (
        two_peer_fault.status != "REVIEW"
        or set(two_peer_findings) != {"connector.peer_pin_assignment_outlier"}
        or dict(two_peer_findings["connector.peer_pin_assignment_outlier"].evidence)
        != {
            "J1.1": ("+5V",),
            "J2.1": (),
            "symbol": ("Lint:PeerPowerPort",),
            "pin_number": ("1",),
            "outlier_pins": ("J2.1",),
        }
        or observed_contracts[("two-peer-open-fault", "first")].nets
        != {"+5V": ("J1.1",), "GND": ("J1.2", "J2.2")}
    ):
        raise ValueError("Two-peer open contact lost its exact native pin-assignment evidence")
    two_peer_no_connect_fault = reports[("two-peer-no-connect-fault", "first")]
    no_connect_findings = {
        finding.rule_id: finding for finding in two_peer_no_connect_fault.findings
    }
    no_connect_observed = observed_contracts[("two-peer-no-connect-fault", "first")]
    no_connect_pins = {
        pin for pins in no_connect_observed.unconnected_nets.values() for pin in pins
    }
    if (
        two_peer_no_connect_fault.status != "REVIEW"
        or set(no_connect_findings) != {"connector.peer_pin_assignment_outlier"}
        or dict(no_connect_findings["connector.peer_pin_assignment_outlier"].evidence)
        != {
            "J1.1": ("+5V",),
            "J2.1": (),
            "symbol": ("Lint:PeerPowerPort",),
            "pin_number": ("1",),
            "outlier_pins": ("J2.1",),
        }
        or no_connect_observed.nets != {"+5V": ("J1.1",), "GND": ("J1.2", "J2.2")}
        or "J2.1" not in no_connect_pins
    ):
        raise ValueError(
            "Explicit no-connect peer contact must retain the REVIEW prompt and native pin evidence"
        )
    two_peer_control = reports[("two-peer-common-control", "first")]
    if (
        two_peer_control.status != "PASS"
        or two_peer_control.findings
        or observed_contracts[("two-peer-common-control", "first")].nets
        != {"+5V": ("J1.1", "J2.1"), "GND": ("J1.2", "J2.2")}
    ):
        raise ValueError("Two-peer common-net control no longer passes with exact native pins")

    offboard_interface = InterfaceRecord(
        id="synthetic-offboard-power-port",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="External 5 V supply",
                role="supply",
                direction="input",
                voltage_domain="5V",
                mating="Synthetic external regulated supply",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="External return",
                role="return",
                direction="bidirectional",
                voltage_domain="0V",
                mating="Synthetic external supply return",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    offboard_catalog_path = scratch / "synthetic-offboard-interface-catalog.json"
    offboard_catalog_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "interfaces": [offboard_interface.model_dump(mode="json")],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    offboard_catalog_sha256 = digest(offboard_catalog_path)
    offboard_observed = observed_contracts[("single-offboard-port-control", "first")]
    offboard_coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-single-offboard-port-control",
        observed=offboard_observed,
        netlist_sha256=netlist_hashes[("single-offboard-port-control", "first")],
    )
    offboard_unreviewed_coverage = evaluate_connector_coverage(offboard_observed, (), ())
    offboard_unreviewed_report = evaluate(
        offboard_coach.project_id,
        offboard_coach,
        DesignLintPolicy(),
        connector_coverage=offboard_unreviewed_coverage,
    )
    if (
        offboard_unreviewed_coverage.status != "UNDECLARED"
        or offboard_unreviewed_report.status != "REVIEW"
        or offboard_unreviewed_report.findings
    ):
        raise ValueError(
            "Unmapped off-board connector must require inventory review without electrical findings"
        )
    log.event(
        "connector-return-fixture/offboard-inventory-unreviewed",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_sha256=source_hashes["single-offboard-port-control"],
        normalized_netlist_sha256=normalized_netlist_hashes[
            ("single-offboard-port-control", "first")
        ],
        coverage_status=offboard_unreviewed_coverage.status,
        lint_status=offboard_unreviewed_report.status,
        findings="none",
        repeatable="true",
        review_basis="candidate connector J1 is undeclared in the project interface map",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    offboard_review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis=(
            "Synthetic project map declares J1.1 as an external 5 V input and J1.2 as its "
            "off-board return endpoint"
        ),
        interface_id=offboard_interface.id,
        pin_map={"1": "1", "2": "2"},
    )
    offboard_coverage = evaluate_connector_coverage(
        offboard_observed,
        (offboard_interface.id,),
        (offboard_review,),
        interfaces={offboard_interface.id: offboard_interface},
        interface_catalog_path=offboard_catalog_path.relative_to(root).as_posix(),
        interface_catalog_sha256=offboard_catalog_sha256,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic project map reviewed the complete connector inventory"
        ),
    )
    if offboard_coverage.status != "COMPLETE" or any(
        item.status != "COVERED" for item in offboard_coverage.entries
    ):
        raise ValueError("Synthetic off-board connector control lacks complete pinout coverage")
    offboard_report = evaluate(
        offboard_coach.project_id,
        offboard_coach,
        DesignLintPolicy(),
        connector_coverage=offboard_coverage,
    )
    if (
        offboard_observed.nets != {"+5V": ("J1.1",), "GND": ("J1.2",)}
        or offboard_report.status != "PASS"
        or offboard_report.findings
    ):
        raise ValueError(
            "Complete off-board supply/return map no longer passes without local lint findings"
        )
    log.event(
        "connector-return-fixture/offboard-interface-control",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_sha256=source_hashes["single-offboard-port-control"],
        netlist_sha256=netlist_hashes[("single-offboard-port-control", "first")],
        repeat_netlist_sha256=netlist_hashes[("single-offboard-port-control", "repeat")],
        normalized_netlist_sha256=normalized_netlist_hashes[
            ("single-offboard-port-control", "first")
        ],
        repeat_normalized_netlist_sha256=normalized_netlist_hashes[
            ("single-offboard-port-control", "repeat")
        ],
        interface_catalog_sha256=offboard_catalog_sha256,
        coverage_status=offboard_coverage.status,
        lint_status=offboard_report.status,
        findings="none",
        repeatable="true",
        repeatability_basis="normalized_netlist_contract",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    if observed_contracts[("peer-pin-outlier-control", "first")].nets.get("+5V") != (
        "J1.1",
        "J2.1",
        "J3.1",
    ):
        raise ValueError("Common generic peer-pin control lost its three native assignments")

    peer_pin_minority = reports[("peer-pin-minority-fault", "first")]
    minority_findings = {finding.rule_id: finding for finding in peer_pin_minority.findings}
    if (
        peer_pin_minority.status != "REVIEW"
        or set(minority_findings) != {"connector.peer_pin_assignment_outlier"}
        or minority_findings["connector.peer_pin_assignment_outlier"].subject
        != "Lint:PeerPowerPort pin 1"
        or dict(minority_findings["connector.peer_pin_assignment_outlier"].evidence)
        != {
            "J1.1": ("+5V",),
            "J2.1": ("+5V",),
            "J3.1": ("+3V3",),
            "symbol": ("Lint:PeerPowerPort",),
            "pin_number": ("1",),
            "outlier_pins": ("J3.1",),
        }
    ):
        raise ValueError("Generic exact-symbol minority assignment lost its native evidence")

    peer_pin_divergence = reports[("peer-pin-divergence-fault", "first")]
    divergence_findings = {finding.rule_id: finding for finding in peer_pin_divergence.findings}
    if (
        peer_pin_divergence.status != "REVIEW"
        or set(divergence_findings) != {"connector.peer_pin_assignment_divergence"}
        or divergence_findings["connector.peer_pin_assignment_divergence"].subject
        != "Lint:PeerPowerPort pin 1"
        or dict(divergence_findings["connector.peer_pin_assignment_divergence"].evidence)
        != {
            "J1.1": ("+5V",),
            "J2.1": ("+3V3",),
            "J3.1": ("+12V",),
            "symbol": ("Lint:PeerPowerPort",),
            "pin_number": ("1",),
            "missing_pin_function_pins": ("J1.1", "J2.1", "J3.1"),
        }
    ):
        raise ValueError("Generic exact-symbol no-majority divergence lost its native evidence")

    placeholder_divergence = reports[("generic-placeholder-divergence-fault", "first")]
    placeholder_findings = {finding.rule_id: finding for finding in placeholder_divergence.findings}
    if (
        placeholder_divergence.status != "REVIEW"
        or set(placeholder_findings) != {"connector.peer_pin_assignment_divergence"}
        or placeholder_findings["connector.peer_pin_assignment_divergence"].subject
        != "Lint:PeerPowerPort pin 1"
        or dict(placeholder_findings["connector.peer_pin_assignment_divergence"].evidence)
        != {
            "J1.1": ("+5V",),
            "J2.1": ("+3V3",),
            "J3.1": ("+12V",),
            "symbol": ("Lint:PeerPowerPort",),
            "pin_number": ("1",),
            "missing_pin_function_pins": ("J1.1", "J2.1", "J3.1"),
        }
        or observed_contracts[("generic-placeholder-divergence-fault", "first")].pin_functions.get(
            "J1.1"
        )
        != "Pin_1"
    ):
        raise ValueError("Generic Pin_N placeholder lost lower-confidence peer evidence")
    placeholder_control = reports[("generic-placeholder-control", "first")]
    if placeholder_control.status != "PASS" or placeholder_control.findings:
        raise ValueError("Common generic Pin_N placeholder control no longer passes cleanly")

    cross_fault = reports[("cross-symbol-fault", "first")]
    cross_fault_findings = tuple(
        item for item in cross_fault.findings if item.rule_id == "connector.repeated_pin_function"
    )
    cross_fault_by_subject = {item.subject: item for item in cross_fault_findings}
    if (
        cross_fault.status != "REVIEW"
        or {item.rule_id for item in cross_fault.findings} != {"connector.repeated_pin_function"}
        or set(cross_fault_by_subject)
        != {
            "multiple connector symbols: ground/return",
            "multiple connector symbols: PWR",
        }
        or dict(cross_fault_by_subject["multiple connector symbols: ground/return"].evidence)
        != {"J1.4": ("USB_RETURN",), "J2.7": ("SERIAL_RETURN",)}
        or dict(cross_fault_by_subject["multiple connector symbols: PWR"].evidence)
        != {"J1.1": ("USB_SUPPLY",), "J2.9": ("SERIAL_SUPPLY",)}
    ):
        raise ValueError("Mixed-symbol return/supply fault lost its exact native lint evidence")

    cross_control = reports[("cross-symbol-control", "first")]
    if cross_control.status != "PASS" or cross_control.findings:
        raise ValueError("Mixed-symbol common-return/supply control no longer passes")

    cross_open = reports[("cross-symbol-open", "first")]
    open_return = next(
        (
            item
            for item in cross_open.findings
            if item.subject == "multiple connector symbols: ground/return"
        ),
        None,
    )
    if (
        cross_open.status != "REVIEW"
        or {item.subject for item in cross_open.findings}
        != {"multiple connector symbols: ground/return"}
        or open_return is None
        or dict(open_return.evidence) != {"J1.4": ("COMMON_RETURN",), "J2.7": ()}
    ):
        raise ValueError("Mixed-symbol open-return fault lost its exact native pin evidence")

    mapped_return_interface = InterfaceRecord(
        id="synthetic-db9",
        revision="synthetic-1",
        pins=tuple(
            InterfacePin(
                number=str(number),
                signal=f"Contact {number}",
                role="return" if number in {7, 9} else "signal",
                direction="bidirectional",
                voltage_domain="synthetic-domain",
                mating=f"Contact {number}",
                orientation="straight",
                mechanical_clearance="synthetic",
            )
            for number in range(1, 10)
        ),
    )
    mapped_return_catalog_path = scratch / "synthetic-interface-catalog.json"
    mapped_return_catalog_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "interfaces": [mapped_return_interface.model_dump(mode="json")],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    mapped_return_catalog_sha256 = digest(mapped_return_catalog_path)
    mapped_return_reviews = tuple(
        ConnectorInterfaceReview(
            reference=f"J{reference}",
            disposition="interface",
            basis="Synthetic interface contact-role map reviewed for the native regression",
            interface_id="synthetic-db9",
            pin_map={str(number): str(number) for number in range(1, 10)},
        )
        for reference in range(1, 5)
    )
    mapped_return_reports: dict[str, DesignLintReport] = {}
    for case in ("four-db9-neutral-fault", "four-db9-neutral-control"):
        observed = observed_contracts[(case, "first")]
        connector_coverage = evaluate_connector_coverage(
            observed,
            ("synthetic-db9",),
            mapped_return_reviews,
            interfaces={"synthetic-db9": mapped_return_interface},
            interface_catalog_path=mapped_return_catalog_path.relative_to(root).as_posix(),
            interface_catalog_sha256=mapped_return_catalog_sha256,
            inventory_review=ConnectorInventoryReview(
                basis="Synthetic fixture reviewed the complete connector inventory"
            ),
        )
        if connector_coverage.status != "COMPLETE" or any(
            entry.status != "COVERED" for entry in connector_coverage.entries
        ):
            raise ValueError("Synthetic mapped-return fixture did not produce complete coverage")
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=f"synthetic-mapped-returns-{case}",
            observed=observed,
            netlist_sha256=netlist_hashes[(case, "first")],
        )
        mapped_report = evaluate(
            coach.project_id,
            coach,
            DesignLintPolicy(),
            connector_coverage=connector_coverage,
        )
        mapped_return_reports[case] = mapped_report
        expected_finding_ids: set[str] = (
            {"connector.repeated_pin_function"} if case == "four-db9-neutral-fault" else set()
        )
        if (
            mapped_report.status != ("REVIEW" if expected_finding_ids else "PASS")
            or {item.rule_id for item in mapped_report.findings} != expected_finding_ids
        ):
            raise ValueError(
                f"Reviewed contact roles changed unexpected {case} result: "
                f"{mapped_report.status} {tuple(item.rule_id for item in mapped_report.findings)}"
            )
        if case == "four-db9-neutral-fault":
            repeated = next(
                item
                for item in mapped_report.findings
                if item.rule_id == "connector.repeated_pin_function"
            )
            expected_pin_evidence: dict[str, tuple[str, ...]] = {
                f"J{reference}.{pin}": (f"NET_{chr(64 + reference)}",)
                for reference in range(1, 5)
                for pin in (7, 9)
            }
            expected_pin_evidence["role_classification_sources"] = tuple(
                f"J{reference}.{pin}: project interface catalog role=return; "
                f"native symbol function={pin}"
                for reference in range(1, 5)
                for pin in (7, 9)
            )
            if dict(repeated.evidence) != expected_pin_evidence:
                raise ValueError(
                    "Mapped DB9 returns lost exact native pin and role-source evidence"
                )
        log.event(
            f"connector-return-fixture/reviewed-role-{case.removeprefix('four-db9-neutral-')}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            catalog_sha256=mapped_return_catalog_sha256,
            netlist_sha256=netlist_hashes[(case, "first")],
            normalized_netlist_sha256=normalized_netlist_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_netlist_hashes[(case, "repeat")],
            coverage_status=connector_coverage.status,
            lint_status=mapped_report.status,
            findings=",".join(item.rule_id for item in mapped_report.findings) or "none",
            subjects=";".join(item.subject for item in mapped_report.findings) or "none",
            source_role_classification="7=signal-number; 9=signal-number; catalog roles classify both as return",
            repeatable=(
                "true"
                if normalized_netlist_hashes[(case, "first")]
                == normalized_netlist_hashes[(case, "repeat")]
                else "false"
            ),
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    def mapped_supply_catalog(serial_voltage_domain: str) -> dict[str, InterfaceRecord]:
        definitions: dict[str, tuple[tuple[str, str, ConnectorPinRole, str], ...]] = {
            "synthetic-usb-port": (
                ("4", "RETURN", "return", "signal-return"),
                ("1", "POWER", "supply", "external-5v"),
            ),
            "synthetic-serial-port": (
                ("7", "RETURN", "return", "signal-return"),
                ("9", "POWER", "supply", serial_voltage_domain),
            ),
            "synthetic-shield-port": (("1", "SHIELD", "shield", "chassis"),),
        }
        return {
            interface_id: InterfaceRecord(
                id=interface_id,
                revision="synthetic-1",
                pins=tuple(
                    InterfacePin(
                        number=number,
                        signal=signal,
                        role=role,
                        direction="passive",
                        voltage_domain=voltage_domain,
                        mating=signal,
                        orientation="straight",
                        mechanical_clearance="synthetic",
                    )
                    for number, signal, role, voltage_domain in pins
                ),
            )
            for interface_id, pins in definitions.items()
        }

    mapped_supply_reviews = (
        ConnectorInterfaceReview(
            reference="J1",
            disposition="interface",
            basis="Synthetic USB return and supply contacts reviewed",
            interface_id="synthetic-usb-port",
            pin_map={"4": "4", "1": "1"},
        ),
        ConnectorInterfaceReview(
            reference="J2",
            disposition="interface",
            basis="Synthetic serial return and supply contacts reviewed",
            interface_id="synthetic-serial-port",
            pin_map={"7": "7", "9": "9"},
        ),
        ConnectorInterfaceReview(
            reference="J3",
            disposition="interface",
            basis="Synthetic shield contact reviewed separately",
            interface_id="synthetic-shield-port",
            pin_map={"1": "1"},
        ),
    )
    for case, serial_voltage_domain in (
        ("mapped-supply-fault", "external-5v"),
        ("mapped-supply-control", "external-5v"),
        ("mapped-supply-fault", "isolated-5v"),
    ):
        domain_control = serial_voltage_domain == "isolated-5v"
        report_key = "mapped-supply-domain-control" if domain_control else case
        observed = observed_contracts[(case, "first")]
        interfaces = mapped_supply_catalog(serial_voltage_domain)
        catalog_path = scratch / f"{report_key}-interface-catalog.json"
        catalog_path.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "interfaces": [item.model_dump(mode="json") for item in interfaces.values()],
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        catalog_sha256 = digest(catalog_path)
        connector_coverage = evaluate_connector_coverage(
            observed,
            tuple(interfaces),
            mapped_supply_reviews,
            interfaces=interfaces,
            interface_catalog_path=catalog_path.relative_to(root).as_posix(),
            interface_catalog_sha256=catalog_sha256,
            inventory_review=ConnectorInventoryReview(
                basis="Synthetic fixture reviewed the complete connector inventory"
            ),
        )
        if connector_coverage.status != "COMPLETE" or any(
            entry.status != "COVERED" for entry in connector_coverage.entries
        ):
            raise ValueError("Synthetic mapped-supply fixture did not produce complete coverage")
        project_id = f"synthetic-mapped-supply-{report_key}"
        mapped_report = evaluate(
            project_id,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=netlist_hashes[(case, "first")],
            ),
            DesignLintPolicy(),
            connector_coverage=connector_coverage,
        )
        expected_finding_ids: set[str] = (
            {"connector.repeated_pin_function"}
            if case == "mapped-supply-fault" and not domain_control
            else set()
        )
        if (
            mapped_report.status != ("REVIEW" if expected_finding_ids else "PASS")
            or {item.rule_id for item in mapped_report.findings} != expected_finding_ids
        ):
            raise ValueError(
                f"Reviewed supply domains changed unexpected {report_key} result: "
                f"{mapped_report.status} {tuple(item.rule_id for item in mapped_report.findings)}"
            )
        if expected_finding_ids:
            repeated = next(
                item
                for item in mapped_report.findings
                if item.rule_id == "connector.repeated_pin_function"
            )
            expected_evidence = {
                "J1.1": ("SUPPLY_ALPHA",),
                "J2.9": ("SUPPLY_BETA",),
                "role_classification_sources": (
                    (
                        "J1.1: project interface catalog role=supply; "
                        "voltage_domain=external-5v; native symbol function=Pin_1"
                    ),
                    (
                        "J2.9: project interface catalog role=supply; "
                        "voltage_domain=external-5v; native symbol function=Pin_9"
                    ),
                ),
                "reviewed_voltage_domain": ("external-5v",),
            }
            if dict(repeated.evidence) != expected_evidence:
                raise ValueError("Mapped supply fault lost exact pin, domain, or role evidence")
        event_name = (
            "domain-control"
            if domain_control
            else "fault"
            if case == "mapped-supply-fault"
            else "control"
        )
        log.event(
            f"connector-return-fixture/reviewed-supply-{event_name}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            catalog_sha256=catalog_sha256,
            netlist_sha256=netlist_hashes[(case, "first")],
            normalized_netlist_sha256=normalized_netlist_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_netlist_hashes[(case, "repeat")],
            coverage_status=connector_coverage.status,
            lint_status=mapped_report.status,
            findings=",".join(item.rule_id for item in mapped_report.findings) or "none",
            subjects=";".join(item.subject for item in mapped_report.findings) or "none",
            source_role_classification=(
                f"role=supply; USB domain=external-5v; serial domain={serial_voltage_domain}; "
                "native supply functions are generic Pin_1 and Pin_9"
            ),
            repeatable=(
                "true"
                if normalized_netlist_hashes[(case, "first")]
                == normalized_netlist_hashes[(case, "repeat")]
                else "false"
            ),
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    peer_scope_interface = InterfaceRecord(
        id="synthetic-peer-return",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="2",
                signal="RETURN",
                role="return",
                direction="bidirectional",
                voltage_domain="signal-return",
                mating="RETURN",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    peer_scope_catalog_path = scratch / "peer-scope-interface-catalog.json"
    peer_scope_catalog_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "interfaces": [peer_scope_interface.model_dump(mode="json")],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    peer_scope_catalog_sha256 = digest(peer_scope_catalog_path)
    for report_name, source_case, shared_group in (
        ("separate-fault", "peer-scope-split-return-fault", False),
        ("shared-fault", "peer-scope-split-return-fault", True),
        ("shared-control", "generic-placeholder-control", True),
    ):
        observed = observed_contracts[(source_case, "first")]
        peer_scope_reviews = tuple(
            ConnectorInterfaceReview(
                reference=f"J{reference}",
                disposition="interface",
                basis=f"Synthetic review maps J{reference} return contact",
                interface_id="synthetic-peer-return",
                pin_map={"2": "2"},
                unlisted_pin_reasons={
                    "1": "Generic Pin_1 signal contact has no reviewed role in this fixture"
                },
                peer_assignment_group=(
                    "uart-peer-set" if shared_group else f"uart-port-{reference}"
                ),
                peer_assignment_basis=(
                    "Reviewed generic signal contacts as one UART peer set"
                    if shared_group
                    else f"Reviewed J{reference} as an independent UART interface"
                ),
            )
            for reference in range(1, 4)
        )
        peer_scope_coverage = evaluate_connector_coverage(
            observed,
            ("synthetic-peer-return",),
            peer_scope_reviews,
            interfaces={"synthetic-peer-return": peer_scope_interface},
            interface_catalog_path=peer_scope_catalog_path.relative_to(root).as_posix(),
            interface_catalog_sha256=peer_scope_catalog_sha256,
            inventory_review=ConnectorInventoryReview(
                basis="Synthetic regression reviewed the complete connector inventory"
            ),
        )
        if peer_scope_coverage.status != "COMPLETE" or any(
            entry.status != "COVERED" for entry in peer_scope_coverage.entries
        ):
            raise ValueError("Peer-scope fixture did not produce complete interface coverage")

        project_id = f"synthetic-peer-scope-{report_name}"
        peer_scope_report = evaluate(
            project_id,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=netlist_hashes[(source_case, "first")],
            ),
            DesignLintPolicy(),
            connector_coverage=peer_scope_coverage,
        )
        expected_peer_scope_findings = {
            "separate-fault": {"connector.repeated_pin_function"},
            "shared-fault": {
                "connector.repeated_pin_function",
                "connector.peer_pin_assignment_divergence",
            },
            "shared-control": set[str](),
        }[report_name]
        peer_scope_findings = {item.rule_id: item for item in peer_scope_report.findings}
        if (
            peer_scope_report.status != ("REVIEW" if expected_peer_scope_findings else "PASS")
            or set(peer_scope_findings) != expected_peer_scope_findings
        ):
            raise ValueError(
                f"Peer-assignment scope changed unexpected {report_name} result: "
                f"{peer_scope_report.status} {tuple(peer_scope_findings)}"
            )
        if report_name != "shared-control":
            return_finding = peer_scope_findings["connector.repeated_pin_function"]
            if {pin: return_finding.evidence[pin] for pin in ("J1.2", "J2.2", "J3.2")} != {
                "J1.2": ("RETURN_A",),
                "J2.2": ("RETURN_B",),
                "J3.2": ("RETURN_C",),
            }:
                raise ValueError("Peer grouping suppressed or changed cross-port return evidence")
        if report_name == "shared-fault":
            divergence = peer_scope_findings["connector.peer_pin_assignment_divergence"]
            if (
                divergence.evidence.get("peer_assignment_group") != ("uart-peer-set",)
                or len(divergence.evidence.get("peer_assignment_basis", ())) != 3
            ):
                raise ValueError("Shared peer divergence omitted its reviewed group evidence")
        log.event(
            f"connector-return-fixture/peer-scope-{report_name}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            catalog_sha256=peer_scope_catalog_sha256,
            source_case=source_case,
            netlist_sha256=netlist_hashes[(source_case, "first")],
            normalized_netlist_sha256=normalized_netlist_hashes[(source_case, "first")],
            repeat_normalized_netlist_sha256=normalized_netlist_hashes[(source_case, "repeat")],
            coverage_status=peer_scope_coverage.status,
            lint_status=peer_scope_report.status,
            findings=",".join(peer_scope_findings) or "none",
            subjects=";".join(item.subject for item in peer_scope_report.findings) or "none",
            group_scope=("shared uart-peer-set" if shared_group else "separate per-port groups"),
            repeatable=(
                "true"
                if normalized_netlist_hashes[(source_case, "first")]
                == normalized_netlist_hashes[(source_case, "repeat")]
                else "false"
            ),
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    for case in cases:
        repeatable = (
            normalized_netlist_hashes[(case, "first")]
            == normalized_netlist_hashes[(case, "repeat")]
        )
        if not repeatable:
            raise ValueError(
                f"Native {case} exports differ after normalization to the parsed netlist contract"
            )
        report = reports[(case, "first")]
        log.event(
            f"connector-return-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=netlist_hashes[(case, "first")],
            repeat_netlist_sha256=netlist_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_netlist_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_netlist_hashes[(case, "repeat")],
            lint_status=report.status,
            findings=",".join(finding.rule_id for finding in report.findings) or "none",
            subjects=";".join(finding.subject for finding in report.findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}"
                for pin, name in sorted(observed_contracts[(case, "first")].pin_functions.items())
            ),
            pin_electrical_types=";".join(
                f"{pin}={name}"
                for pin, name in sorted(
                    observed_contracts[(case, "first")].pin_electrical_types.items()
                )
            ),
            **(
                {"connector_peer_pin_coverage": peer_pin_coverage_receipts[case]}
                if case in peer_pin_coverage_receipts
                else {}
            ),
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )


def i2c_pullup_native_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Exercise mapped I2C resistor-array requirements from pinned native exports."""
    import hashlib

    from .hwrepo.bus_heuristics import i2c_pullup_checks
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ElectricalCheck,
        I2cPullupAnalysis,
        I2cPullupArrayChannelRequirement,
        I2cPullupArrayRequirement,
        I2cPullupBusRequirement,
        I2cPullupLineRequirement,
        NetlistContract,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"I2C pull-up fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/i2c-array-native"
    )
    fixtures = {case: fixture_root / f"{case}.kicad_sch" for case in ("control", "fault")}
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    expected_source_hashes = {
        "control": "922e40c8815a302e8af30e3eb7e4a53b1b3361be419cc0c56fe3025619a7243d",
        "fault": "062648e3ec3d9c71e976fc40370d4d7a1ab4d6064e73d79fe191878ee052efc4",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("I2C pull-up fixture sources differ from the reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"native-i2c-pullup-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        shutil.copyfile(fixture, inputs / fixture.name)
        if digest(inputs / fixture.name) != source_hashes[case]:
            raise ValueError(f"Synthetic I2C {case} fixture changed while preparing native input")
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
        "    kicad-cli sch export netlist --format kicadxml \\\n"
        '      --output "/output/${case}.${run}.netlist.xml" \\\n'
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
        "HOME=/tmp/kicad-i2c-pullup-fixtures",
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
        "i2c-pullup-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "i2c-pullup-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native I2C pull-up export failed: {command.stderr or command.error}")
    log.event(
        "i2c-pullup-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in fixtures),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    requirement = I2cPullupAnalysis(
        basis="Synthetic reviewed resistor-array and local I2C bus requirements",
        buses=(
            I2cPullupBusRequirement(
                id="array-bus",
                basis="Synthetic two-line bus",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
            ),
        ),
        arrays=(
            I2cPullupArrayRequirement(
                reference="RN1",
                expected_symbol="Synthetic:ResistorArray",
                expected_footprint="Synthetic:RA4",
                expected_value="4x4.7k",
                basis="Synthetic array pin map and nominal channel values",
                channels=(
                    I2cPullupArrayChannelRequirement(
                        id="sda",
                        signal_pin="RN1.1",
                        rail_pin="RN1.2",
                        signal_net="I2C_SDA",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic SDA resistor-array channel",
                    ),
                    I2cPullupArrayChannelRequirement(
                        id="scl",
                        signal_pin="RN1.3",
                        rail_pin="RN1.4",
                        signal_net="I2C_SCL",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic SCL resistor-array channel",
                    ),
                ),
            ),
        ),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    observations: dict[tuple[str, str], NetlistContract] = {}
    reports: dict[tuple[str, str], tuple[ElectricalCheck, ...]] = {}
    for case, fixture in fixtures.items():
        if (
            digest(fixture) != source_hashes[case]
            or digest(inputs / fixture.name) != source_hashes[case]
        ):
            raise ValueError("Synthetic I2C fixture changed during native export")
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native I2C fixture omitted {netlist_path.name}")
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
            reports[(case, run)] = i2c_pullup_checks(requirement, observed)

    control = observations[("control", "first")]
    if (
        control.components.get("RN1") is None
        or control.components["RN1"].value != "4x4.7k"
        or control.components["RN1"].footprint != "Synthetic:RA4"
        or control.component_symbols.get("RN1") != "Synthetic:ResistorArray"
        or set(control.component_pin_numbers.get("RN1", ())) != {"1", "2", "3", "4"}
        or control.nets.get("I2C_SDA") != ("RN1.1", "U1.1")
        or control.nets.get("I2C_SCL") != ("RN1.3", "U1.2")
        or control.nets.get("+3V3") != ("RN1.2", "RN1.4")
    ):
        raise ValueError(
            "Native I2C control lost its exact array identity, pins, or net assignments"
        )
    control_checks = {item.id: item for item in reports[("control", "first")]}
    if any(
        control_checks[f"i2c-pullup/array-bus/{line}"].status != "PASS" for line in ("sda", "scl")
    ):
        raise ValueError("Native mapped I2C resistor-array control did not pass both lines")

    fault = observations[("fault", "first")]
    fault_checks = {item.id: item for item in reports[("fault", "first")]}
    sda_fault = fault_checks["i2c-pullup/array-bus/sda"]
    if (
        fault.nets.get("SDA_WRONG") != ("RN1.1",)
        or sda_fault.status != "FAIL"
        or "RN1.1 is on SDA_WRONG" not in sda_fault.detail
        or fault_checks["i2c-pullup/array-bus/scl"].status != "PASS"
    ):
        raise ValueError("Native I2C array pin/net fault lost its exact line-specific failure")

    for case in fixtures:
        first_hash = normalized_hashes[(case, "first")]
        repeat_hash = normalized_hashes[(case, "repeat")]
        if first_hash != repeat_hash:
            raise ValueError(f"Native I2C {case} exports differ after typed normalization")
        checks = {item.id: item for item in reports[(case, "first")]}
        log.event(
            f"i2c-pullup-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=first_hash,
            repeat_normalized_netlist_sha256=repeat_hash,
            sda=checks["i2c-pullup/array-bus/sda"].status,
            scl=checks["i2c-pullup/array-bus/scl"].status,
            repeatable="true",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )


def can_termination_native_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Exercise split CAN termination requirements from pinned native exports."""
    import hashlib
    import json
    import os

    from .hwrepo.bus_heuristics import can_termination_checks
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        CanTerminationAnalysis,
        CanTerminationBusRequirement,
        CanTerminationEndpointRequirement,
        CanTerminationMidpointCapacitorRequirement,
        CanTerminationResistorRequirement,
        ElectricalCheck,
        NetlistContract,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"CAN termination fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/can-split-midpoint-native"
    )
    fixtures = {case: fixture_root / f"{case}.kicad_sch" for case in ("control", "fault")}
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    expected_source_hashes = {
        "control": "f69f9084482ce5455740c4ac33628fd226e5243650acd9a2e022984aec830726",
        "fault": "0c84ea82f7ff60be1d8a1ea6f2815fe9e6593ad1e8ae192f362c02af73bb8db6",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("CAN termination fixture sources differ from the reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"native-can-termination-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        shutil.copyfile(fixture, inputs / fixture.name)
        if digest(inputs / fixture.name) != source_hashes[case]:
            raise ValueError(f"Synthetic CAN {case} fixture changed while preparing native input")
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
        "    kicad-cli sch export netlist --format kicadxml \\\n"
        '      --output "/output/${case}.${run}.netlist.xml" \\\n'
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
        "HOME=/tmp/kicad-can-termination-fixtures",
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
        "can-termination-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "can-termination-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native CAN termination export failed: {command.stderr or command.error}")
    log.event(
        "can-termination-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in fixtures),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    requirement = CanTerminationAnalysis(
        basis="Synthetic reviewed split CAN topology with mapped midpoint capacitor",
        buses=(
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Synthetic controller CAN interface",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=("U1.1",),
                low_pins=("U1.2",),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="local",
                        basis="Synthetic split termination at a local endpoint",
                        topology="split",
                        midpoint_net="CAN_TERM_MID",
                        resistors=(
                            CanTerminationResistorRequirement(
                                reference="R4",
                                first_net="CAN_H",
                                second_net="CAN_TERM_MID",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                            CanTerminationResistorRequirement(
                                reference="R5",
                                first_net="CAN_L",
                                second_net="CAN_TERM_MID",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                        ),
                        midpoint_capacitor=CanTerminationMidpointCapacitorRequirement(
                            reference="C1",
                            expected_symbol="Synthetic:CanMidpointCapacitor",
                            expected_footprint="Synthetic:CAP",
                            midpoint_pin="C1.1",
                            reference_pin="C1.2",
                            reference_net="GND",
                            minimum_nominal_capacitance_pf=90,
                            maximum_nominal_capacitance_pf=110,
                        ),
                    ),
                ),
            ),
        ),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    observations: dict[tuple[str, str], NetlistContract] = {}
    reports: dict[tuple[str, str], tuple[ElectricalCheck, ...]] = {}
    for case, fixture in fixtures.items():
        if (
            digest(fixture) != source_hashes[case]
            or digest(inputs / fixture.name) != source_hashes[case]
        ):
            raise ValueError("Synthetic CAN termination fixture changed during native export")
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native CAN termination fixture omitted {netlist_path.name}")
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
            reports[(case, run)] = can_termination_checks(requirement, observed)

    control = observations[("control", "first")]
    if (
        control.components.get("R4") is None
        or control.components["R4"].value != "60R"
        or control.components["R4"].footprint != "Synthetic:R_0603"
        or control.components.get("R5") is None
        or control.components["R5"].value != "60R"
        or control.components["R5"].footprint != "Synthetic:R_0603"
        or control.component_symbols.get("R4") != "Device:R"
        or control.component_symbols.get("R5") != "Device:R"
        or set(control.component_pin_numbers.get("R4", ())) != {"1", "2"}
        or set(control.component_pin_numbers.get("R5", ())) != {"1", "2"}
        or control.components.get("C1") is None
        or control.components["C1"].value != "100pF"
        or control.components["C1"].footprint != "Synthetic:CAP"
        or control.component_symbols.get("C1") != "Synthetic:CanMidpointCapacitor"
        or set(control.component_pin_numbers.get("C1", ())) != {"1", "2"}
        or set(control.nets.get("CAN_H", ())) != {"R4.1", "U1.1"}
        or set(control.nets.get("CAN_L", ())) != {"R5.1", "U1.2"}
        or control.pin_functions.get("U1.1") != "CANH"
        or control.pin_functions.get("U1.2") != "CANL"
        or set(control.nets.get("CAN_TERM_MID", ())) != {"C1.1", "R4.2", "R5.2"}
        or tuple(control.nets.get("GND", ())) != ("C1.2",)
    ):
        raise ValueError(
            "Native CAN control lost its exact component identity, pins, or net assignments"
        )

    expected_check_ids = {
        "can-termination/fieldbus/signal-pins",
        "can-termination/fieldbus/unlisted-direct",
        "can-termination/fieldbus/local",
        "can-termination/fieldbus/local/midpoint-capacitor",
    }
    control_checks = {item.id: item for item in reports[("control", "first")]}
    if set(control_checks) != expected_check_ids or any(
        item.status != "PASS" for item in control_checks.values()
    ):
        raise ValueError("Native split CAN termination control did not pass every declared check")

    fault = observations[("fault", "first")]
    fault_checks = {item.id: item for item in reports[("fault", "first")]}
    capacitor_id = "can-termination/fieldbus/local/midpoint-capacitor"
    capacitor_check = fault_checks.get(capacitor_id)
    if (
        set(fault_checks) != expected_check_ids
        or fault.nets.get("GND_ALT") != ("C1.2",)
        or capacitor_check is None
        or capacitor_check.status != "FAIL"
        or "C1.2 is assigned to GND_ALT; expected only GND" not in capacitor_check.detail
        or any(
            fault_checks[check_id].status != "PASS"
            for check_id in expected_check_ids - {capacitor_id}
        )
    ):
        raise ValueError("Native CAN midpoint-reference fault lost its exact isolated failure")

    for case in fixtures:
        first_hash = normalized_hashes[(case, "first")]
        repeat_hash = normalized_hashes[(case, "repeat")]
        if first_hash != repeat_hash:
            raise ValueError(f"Native CAN {case} exports differ after typed normalization")
        checks = {item.id: item for item in reports[(case, "first")]}
        log.event(
            f"can-termination-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=first_hash,
            repeat_normalized_netlist_sha256=repeat_hash,
            signal_pins=checks["can-termination/fieldbus/signal-pins"].status,
            unlisted_direct=checks["can-termination/fieldbus/unlisted-direct"].status,
            split_path=checks["can-termination/fieldbus/local"].status,
            midpoint_capacitor=checks[capacitor_id].status,
            repeatable="true",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )


def connector_inventory_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Check connector-candidate coverage from repeated pinned native netlists."""
    import hashlib
    import json
    import os

    from .hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
    from .hwrepo.connector_pins import connector_candidate_references
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ConnectorCoverageReport, ConnectorInventoryReview
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Connector inventory fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/design_lint/connector-inventory-native"
    )
    cases = ("fault", "control")
    source_hashes = {case: digest(fixture_root / f"{case}.kicad_sch") for case in cases}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"connector-inventory-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case in cases:
        shutil.copyfile(fixture_root / f"{case}.kicad_sch", inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} connector inventory fixture changed during copy")
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
        "HOME=/tmp/kicad-connector-inventory-fixtures",
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
        "connector-inventory-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "connector-inventory-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native connector inventory export failed: {command.stderr or command.error}"
        )

    if any(
        digest(fixture_root / f"{case}.kicad_sch") != source_hashes[case]
        or digest(inputs / f"{case}.kicad_sch") != source_hashes[case]
        for case in cases
    ):
        raise ValueError("Synthetic connector inventory source changed during native export")

    normalized_hashes: dict[tuple[str, str], str] = {}
    netlist_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], ConnectorCoverageReport] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native connector inventory fixture omitted {netlist_path.name}")
            netlist_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()

            if case == "fault":
                if observed.component_symbols.get("U7") != "Connector_Generic:Conn_01x02":
                    raise ValueError(
                        "Native netlist did not retain the standard connector library identity "
                        "under reference U7"
                    )
                inventory_review = None
            else:
                if observed.component_symbols.get("U8") != "Connector:TestPoint_Alt":
                    raise ValueError(
                        "Native netlist did not retain the test-point control identity"
                    )
                inventory_review = ConnectorInventoryReview(
                    basis="Synthetic control reviewed its complete symbol inventory"
                )

            candidates = connector_candidate_references(observed)
            expected_candidates = ("U7",) if case == "fault" else ()
            if candidates != expected_candidates:
                raise ValueError(
                    f"Native connector inventory {case} candidates differ: "
                    f"expected {expected_candidates}, observed {candidates}"
                )
            reports[(case, run)] = evaluate_connector_coverage(
                observed,
                (),
                (),
                inventory_review=inventory_review,
            )

    for case in cases:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(
                f"Native connector inventory {case} netlists differ after normalization"
            )
        report = reports[(case, "first")]
        repeat_report = reports[(case, "repeat")]
        if report != repeat_report:
            raise ValueError(f"Native connector inventory {case} coverage report is not repeatable")
        expected_status = "UNDECLARED" if case == "fault" else "COMPLETE"
        if report.status != expected_status:
            raise ValueError(
                f"Native connector inventory {case} expected {expected_status}, got {report.status}"
            )
        report_path = scratch / f"{case}.coverage.json"
        write_model(report_path, report)
        log.event(
            f"connector-inventory-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=netlist_hashes[(case, "first")],
            repeat_netlist_sha256=netlist_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            coverage_sha256=digest(report_path),
            coverage_status=report.status,
            candidate_references=",".join(item.reference for item in report.entries) or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_connector_coverage_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "connector-inventory-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )


def serial_peer_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify serial-peer coverage prompts against repeated pinned native exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.contracts import read_model
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        DesignLintRuleOverride,
        NetlistContract,
        SerialPeerAnalysis,
    )
    from .hwrepo.serial_participants import SerialPeerRosterContext
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Serial peer fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/serial-peer-native"
    fixture = fixture_root / "endpoints.kicad_sch"
    source_hash = digest(fixture)
    scratch = Path(tempfile.mkdtemp(prefix=f"serial-peer-{project}-", dir=log.directory.resolve()))
    inputs = scratch / "input"
    inputs.mkdir()
    source = inputs / "endpoints.kicad_sch"
    shutil.copyfile(fixture, source)
    if digest(source) != source_hash:
        raise ValueError("Synthetic serial-peer fixture changed while preparing native input")
    map_fixtures = {
        "partial": fixture_root / "peer-map-partial.json",
        "complete": fixture_root / "peer-map-complete.json",
    }
    map_source_hashes = {case: digest(path) for case, path in map_fixtures.items()}
    map_inputs = {case: inputs / path.name for case, path in map_fixtures.items()}
    for case, path in map_fixtures.items():
        shutil.copyfile(path, map_inputs[case])
        if digest(map_inputs[case]) != map_source_hashes[case]:
            raise ValueError(f"Synthetic serial-peer {case} map changed while preparing input")
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
        "for run in first repeat; do\n"
        "  kicad-cli sch export netlist --format kicadxml "
        '    --output "/output/endpoints.${run}.netlist.xml" '
        '    "/fixtures/endpoints.kicad_sch"\n'
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
        "HOME=/tmp/kicad-serial-peer-fixtures",
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
        "serial-peer-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "serial-peer-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native serial-peer fixture command failed: {command.stderr or command.error}"
        )

    if (
        digest(fixture) != source_hash
        or digest(source) != source_hash
        or any(
            digest(map_fixtures[case]) != map_source_hashes[case]
            or digest(map_inputs[case]) != map_source_hashes[case]
            for case in map_fixtures
        )
    ):
        raise ValueError("Synthetic serial-peer fixture source changed during native export")
    contracts: dict[str, NetlistContract] = {}
    hashes: dict[str, str] = {}
    normalized_hashes: dict[str, str] = {}
    for run in ("first", "repeat"):
        path = output / f"endpoints.{run}.netlist.xml"
        if not path.is_file():
            raise ValueError(f"Native serial-peer fixture omitted {path.name}")
        hashes[run] = digest(path)
        contracts[run] = read_netlist(path)
        normalized = json.dumps(
            contracts[run].model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
    if normalized_hashes["first"] != normalized_hashes["repeat"]:
        raise ValueError("Native serial-peer exports differ after typed-netlist normalization")

    observed = contracts["first"]
    expected_functions = {
        f"J{reference}.{pin}": function
        for reference in range(1, 5)
        for pin, function in ((1, "TX"), (2, "RX"))
    }
    if observed.pin_functions != expected_functions:
        raise ValueError(
            "Native serial-peer netlist changed the exact endpoint function inventory: "
            f"{observed.pin_functions}"
        )
    if observed.component_symbols != {
        f"J{reference}": "Synthetic:UART_Endpoint" for reference in range(1, 5)
    }:
        raise ValueError("Native serial-peer netlist changed synthetic connector identities")
    if observed.component_pin_numbers != {f"J{reference}": ("1", "2") for reference in range(1, 5)}:
        raise ValueError("Native serial-peer netlist changed the full connector pin inventory")
    expected_nets = {
        "SERIAL_A_TX": {"J1.1", "J2.2"},
        "SERIAL_A_RX": {"J1.2", "J2.1"},
        "SERIAL_B_TX": {"J3.1", "J4.2"},
        "SERIAL_B_RX": {"J3.2", "J4.1"},
    }
    actual_nets = {
        net: set(pins) for net, pins in observed.nets.items() if net.startswith("SERIAL_")
    }
    if actual_nets != expected_nets:
        raise ValueError(f"Native serial-peer netlist changed connector assignments: {actual_nets}")

    cases: dict[str, SerialPeerRosterContext] = {
        "unrostered": SerialPeerRosterContext(state="not_configured"),
    }
    for case, path in map_inputs.items():
        analysis = read_model(path, SerialPeerAnalysis)
        cases[case] = SerialPeerRosterContext(
            state="required",
            analysis=analysis,
            source_path=map_fixtures[case].relative_to(repository).as_posix(),
            source_sha256=map_source_hashes[case],
        )
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="connector.repeated_pin_function",
                mode="off",
                reason="Isolate synthetic serial-peer map coverage from repeated connector functions.",
            ),
        )
    )
    reports: dict[str, DesignLintReport] = {}
    for case, roster in cases.items():
        report_runs: list[DesignLintReport] = []
        for run in ("first", "repeat"):
            project_id = f"synthetic-serial-peer-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=contracts[run],
                netlist_sha256=hashes[run],
            )
            report_runs.append(evaluate(project_id, coach, policy, serial_peer_roster=roster))
        first, repeated = report_runs
        first_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.disposition, item.evidence)
            for item in first.findings
        )
        repeat_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.disposition, item.evidence)
            for item in repeated.findings
        )
        if first.status != repeated.status or first_signature != repeat_signature:
            raise ValueError(f"Native serial-peer {case} review changed on repeated export")
        reports[case] = first

    expected: dict[str, tuple[str, set[str]]] = {
        "unrostered": ("REVIEW", {"J1", "J2", "J3", "J4"}),
        "partial": ("REVIEW", {"J3", "J4"}),
        "complete": ("PASS", set()),
    }
    for case, (status, references) in expected.items():
        report = reports[case]
        findings = tuple(
            item for item in report.findings if item.rule_id == "bus.serial_unmapped_peer"
        )
        if (
            report.status != status
            or {item.subject.split(":", 1)[0] for item in findings} != references
        ):
            raise ValueError(
                f"Native serial-peer {case} case no longer matches expected coverage: "
                f"status={report.status}; findings="
                f"{[(item.rule_id, item.subject, item.mode) for item in report.findings]}"
            )
        if any(item.mode != "review" for item in findings):
            raise ValueError("Serial peer coverage heuristic no longer defaults to REVIEW")
        if case == "partial" and any(
            item.evidence["serial_peer_map_state"] != ("required",) for item in findings
        ):
            raise ValueError("Native serial-peer findings lost authored-map state evidence")
        log.event(
            f"serial-peer-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hash,
            netlist_sha256=hashes["first"],
            repeat_netlist_sha256=hashes["repeat"],
            normalized_netlist_sha256=normalized_hashes["first"],
            repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
            lint_status=report.status,
            findings=";".join(item.subject for item in findings) or "none",
            authored_map_sha256=cases[case].source_sha256 or "none",
            pin_functions=";".join(
                f"{pin}={function}" for pin, function in sorted(observed.pin_functions.items())
            ),
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    log.event(
        "serial-peer-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_sha256=source_hash,
        netlist_sha256=hashes["first"],
        repeat_netlist_sha256=hashes["repeat"],
        normalized_netlist_sha256=normalized_hashes["first"],
        repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
        repeatable="true",
        repeatability_basis="normalized_native_netlist_contract",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )


def serial_peer_net_label_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify UART net-label discovery for MCU alternate-function pins on native exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.contracts import read_model
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        DesignLintRuleOverride,
        NetlistContract,
        SerialPeerAnalysis,
    )
    from .hwrepo.serial_participants import SerialPeerRosterContext
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Serial peer fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/serial-peer-native"
    fixture = fixture_root / "alternate-function-endpoint.kicad_sch"
    fixture_hash = digest(fixture)
    map_fixture = fixture_root / "peer-map-alternate-function.json"
    map_hash = digest(map_fixture)
    scratch = Path(
        tempfile.mkdtemp(prefix=f"serial-peer-net-label-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    source = inputs / fixture.name
    map_input = inputs / map_fixture.name
    shutil.copyfile(fixture, source)
    shutil.copyfile(map_fixture, map_input)
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
        "for run in first repeat; do\n"
        "  kicad-cli sch export netlist --format kicadxml "
        '    --output "/output/alternate.${run}.netlist.xml" '
        '    "/fixtures/alternate-function-endpoint.kicad_sch"\n'
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
        "HOME=/tmp/kicad-serial-net-label-fixtures",
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
        "serial-peer-net-label-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "serial-peer-net-label-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native serial-peer net-label fixture failed: {command.stderr or command.error}"
        )
    if (
        digest(fixture) != fixture_hash
        or digest(source) != fixture_hash
        or digest(map_fixture) != map_hash
        or digest(map_input) != map_hash
    ):
        raise ValueError("Synthetic serial-peer net-label fixture changed during native export")

    contracts: dict[str, NetlistContract] = {}
    netlist_hashes: dict[str, str] = {}
    normalized_hashes: dict[str, str] = {}
    for run in ("first", "repeat"):
        path = output / f"alternate.{run}.netlist.xml"
        if not path.is_file():
            raise ValueError(f"Native serial-peer net-label export omitted {path.name}")
        netlist_hashes[run] = digest(path)
        contracts[run] = read_netlist(path)
        normalized = json.dumps(
            contracts[run].model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
    if normalized_hashes["first"] != normalized_hashes["repeat"]:
        raise ValueError("Alternate-function UART native exports differ after normalization")
    observed = contracts["first"]
    expected_functions = {
        "U1.1": "PA2",
        "U1.2": "PA3",
        "J5.1": "Pin_1",
        "J5.2": "Pin_2",
    }
    if observed.pin_functions != expected_functions:
        raise ValueError(
            "Alternate-function UART fixture changed its exact pin-function inventory: "
            f"{observed.pin_functions}"
        )
    if observed.nets != {
        "UART_RX": ("J5.2", "U1.2"),
        "UART_TX": ("J5.1", "U1.1"),
    }:
        raise ValueError(f"Alternate-function UART fixture changed native nets: {observed.nets}")

    analysis = read_model(map_input, SerialPeerAnalysis)
    mapped_roster = SerialPeerRosterContext(
        state="required",
        analysis=analysis,
        source_path=map_fixture.relative_to(repository).as_posix(),
        source_sha256=map_hash,
    )
    rosters = {
        "unrostered": SerialPeerRosterContext(state="not_configured"),
        "mapped": mapped_roster,
    }
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="connector.repeated_pin_function",
                mode="off",
                reason="Keep the alternate-function UART fixture focused on serial-map discovery.",
            ),
        )
    )
    for case, roster in rosters.items():
        repeated_reports: list[DesignLintReport] = []
        for run in ("first", "repeat"):
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-serial-net-label-{case}",
                observed=contracts[run],
                netlist_sha256=netlist_hashes[run],
            )
            repeated_reports.append(
                evaluate(
                    f"synthetic-serial-net-label-{case}", coach, policy, serial_peer_roster=roster
                )
            )
        first, repeated = repeated_reports

        def report_signature(report: DesignLintReport) -> tuple[tuple[object, ...], ...]:
            return tuple(
                (item.fingerprint, item.rule_id, item.mode, item.disposition, item.evidence)
                for item in report.findings
            )

        if first.status != repeated.status or report_signature(first) != report_signature(repeated):
            raise ValueError(f"Alternate-function serial-map {case} report is not repeatable")
        findings = tuple(
            item for item in first.findings if item.rule_id == "bus.serial_unmapped_peer"
        )
        expected = ("REVIEW", 1, "net_label") if case == "unrostered" else ("PASS", 0, None)
        actual_basis = findings[0].evidence.get("discovery_basis", (None,))[0] if findings else None
        if (first.status, len(findings), actual_basis) != expected:
            raise ValueError(
                f"Alternate-function serial-map {case} result changed: "
                f"status={first.status}; findings={findings}"
            )
        if (
            findings
            and "does not assert that a peer or connection is required" not in findings[0].message
        ):
            raise ValueError("UART net-label finding no longer states its review-only boundary")
        log.event(
            f"serial-peer-net-label-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=fixture_hash,
            netlist_sha256=netlist_hashes["first"],
            repeat_netlist_sha256=netlist_hashes["repeat"],
            normalized_netlist_sha256=normalized_hashes["first"],
            repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
            lint_status=first.status,
            findings=";".join(item.subject for item in findings) or "none",
            discovery_basis=actual_basis or "none",
            authored_map_sha256=roster.source_sha256 or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "serial-peer-net-label-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_sha256=fixture_hash,
        netlist_sha256=netlist_hashes["first"],
        repeat_netlist_sha256=netlist_hashes["repeat"],
        normalized_netlist_sha256=normalized_hashes["first"],
        repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
        pin_functions=";".join(
            f"{pin}={function}" for pin, function in sorted(observed.pin_functions.items())
        ),
        repeatable="true",
        repeatability_basis="normalized_native_netlist_contract",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )


def serial_peer_reference_bond_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify an authored serial reference bond against repeated pinned exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.contracts import read_model
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ElectricalCheck, SerialPeerAnalysis
    from .hwrepo.serial_heuristics import serial_peer_checks
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Serial reference-bond fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)

    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/serial-peer-reference-bond-native"
    fixtures = {
        "control": fixture_root / "serial-reference-bond-control.kicad_sch",
        "fault": fixture_root / "serial-reference-bond-fault.kicad_sch",
    }
    fixture_hashes = {case: digest(path) for case, path in fixtures.items()}
    map_fixture = fixture_root / "serial-peer-map.json"
    map_hash = digest(map_fixture)
    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"serial-peer-reference-bond-{project}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    input_fixtures = {case: inputs / path.name for case, path in fixtures.items()}
    for case, path in fixtures.items():
        shutil.copyfile(path, input_fixtures[case])
        if digest(input_fixtures[case]) != fixture_hashes[case]:
            raise ValueError(
                f"Synthetic serial reference-bond {case} fixture changed while copying"
            )
    map_input = inputs / map_fixture.name
    shutil.copyfile(map_fixture, map_input)
    if digest(map_input) != map_hash:
        raise ValueError("Synthetic serial reference-bond map changed while copying")

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
        '      "/fixtures/serial-reference-bond-${case}.kicad_sch"\n'
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
        "HOME=/tmp/kicad-serial-peer-reference-bond-fixtures",
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
        "serial-peer-reference-bond-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "serial-peer-reference-bond-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            "Native serial reference-bond fixture failed: "
            f"{command.stderr or command.error or command.returncode}"
        )
    if (
        any(digest(fixtures[case]) != fixture_hashes[case] for case in fixtures)
        or any(digest(input_fixtures[case]) != fixture_hashes[case] for case in fixtures)
        or digest(map_fixture) != map_hash
        or digest(map_input) != map_hash
    ):
        raise ValueError("Synthetic serial reference-bond inputs changed during native export")

    requirement = read_model(map_input, SerialPeerAnalysis)
    if len(requirement.links) != 1 or requirement.links[0].reference_policy != "bonded":
        raise ValueError("Synthetic serial reference-bond map no longer declares one bonded link")
    netlist_hashes: dict[tuple[str, str], str] = {}
    normalized_hashes: dict[tuple[str, str], str] = {}
    check_reports: dict[tuple[str, str], tuple[ElectricalCheck, ...]] = {}
    for case in ("control", "fault"):
        for run in ("first", "repeat"):
            path = output / f"{case}.{run}.netlist.xml"
            if not path.is_file():
                raise ValueError(f"Native serial reference-bond fixture omitted {path.name}")
            netlist_hashes[(case, run)] = digest(path)
            observed = read_netlist(path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            check_reports[(case, run)] = serial_peer_checks(requirement, observed)
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(
                f"Native serial reference-bond {case} exports differ after normalization"
            )
        first = check_reports[(case, "first")]
        repeated = check_reports[(case, "repeat")]
        first_signature = tuple((item.id, item.status, item.detail) for item in first)
        repeated_signature = tuple((item.id, item.status, item.detail) for item in repeated)
        if first_signature != repeated_signature:
            raise ValueError(
                f"Native serial reference-bond {case} checks differ on repeated export"
            )
        by_id = {item.id: item for item in first}
        reference = by_id.get("serial/serial-bond/reference")
        if reference is None:
            raise ValueError(f"Native serial reference-bond {case} omitted its reference check")
        failed = tuple(sorted(item.id for item in first if item.status == "FAIL"))
        expected_failed = ("serial/serial-bond/reference",) if case == "fault" else ()
        if failed != expected_failed or reference.status != ("FAIL" if case == "fault" else "PASS"):
            raise ValueError(
                f"Native serial reference-bond {case} mismatch: failed={failed}; "
                f"reference={reference.status}: {reference.detail}"
            )
        if case == "fault" and "R3.2 is on FLOATING_GND; expected GND_B" not in reference.detail:
            raise ValueError(
                "Native serial reference-bond fault lost the exact floating-pin evidence"
            )
        report_bytes = json.dumps(
            [item.model_dump(mode="json") for item in first],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        report_hash = hashlib.sha256(report_bytes).hexdigest()
        log.event(
            f"serial-peer-reference-bond-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=fixture_hashes[case],
            authored_map_sha256=map_hash,
            netlist_sha256=netlist_hashes[(case, "first")],
            repeat_netlist_sha256=netlist_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            check_report_sha256=report_hash,
            reference_status=reference.status,
            reference_detail=reference.detail,
            failed_checks=";".join(failed) or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_typed_serial_peer_checks",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "serial-peer-reference-bond-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{fixture_hashes[case]}" for case in ("control", "fault")),
        authored_map_sha256=map_hash,
        normalized_netlist_sha256=";".join(
            f"{case}:{normalized_hashes[(case, 'first')]}" for case in ("control", "fault")
        ),
        repeatable="true",
        repeatability_basis="normalized_native_netlist_contract",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )


def digital_peer_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify SPI and peer-voltage lint from repeated, pinned native exports."""
    import hashlib
    import json
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.digital_peer_voltages import digital_peer_voltage_checks
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        DesignLintRuleOverride,
        DigitalLogicInputLimits,
        DigitalLogicOutputLimits,
        DigitalPeerPinRequirement,
        DigitalPeerVoltageAnalysis,
        DigitalPeerVoltageLink,
        NetlistContract,
        SpiAnalysis,
        SpiBusRequirement,
        SpiControllerRequirement,
        SpiDeviceRequirement,
        SpiMisoConnectedRequirement,
        SpiPinNetRequirement,
    )
    from .hwrepo.spi_participants import SpiRosterContext
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Digital-peer fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    fixture = fixture_root / "spi-participant-native/multi-device.kicad_sch"
    source_hash = digest(fixture)
    scratch = Path(
        tempfile.mkdtemp(prefix=f"spi-participant-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    source = inputs / "multi-device.kicad_sch"
    shutil.copyfile(fixture, source)
    if digest(source) != source_hash:
        raise ValueError("Synthetic SPI fixture changed while preparing native input")
    peer_fixtures = {
        case: fixture_root / f"spi-peer-voltage-native/{case}.kicad_sch"
        for case in ("peer-control", "peer-fault", "peer-translator-control")
    }
    peer_source_hashes = {case: digest(path) for case, path in peer_fixtures.items()}
    for case, path in peer_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != peer_source_hashes[case]:
            raise ValueError(f"Synthetic SPI {case} fixture changed while preparing native input")
    serial_peer_fixtures = {
        case: fixture_root / f"serial-peer-voltage-native/{case}.kicad_sch"
        for case in ("serial-control", "serial-fault", "serial-reference-fault")
    }
    serial_peer_source_hashes = {case: digest(path) for case, path in serial_peer_fixtures.items()}
    for case, path in serial_peer_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != serial_peer_source_hashes[case]:
            raise ValueError(f"Synthetic UART {case} fixture changed while preparing native input")
    serial_connector_reference_fixtures = {
        case: fixture_root / f"serial-peer-connector-reference-native/{case}.kicad_sch"
        for case in ("serial-connector-control", "serial-connector-fault")
    }
    serial_connector_reference_source_hashes = {
        case: digest(path) for case, path in serial_connector_reference_fixtures.items()
    }
    for case, path in serial_connector_reference_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != serial_connector_reference_source_hashes[case]:
            raise ValueError(
                f"Synthetic UART connector {case} fixture changed while preparing native input"
            )
    serial_label_reference_fixtures = {
        case: fixture_root / f"serial-peer-connector-reference-native/{case}.kicad_sch"
        for case in ("serial-label-control", "serial-label-fault")
    }
    serial_label_reference_source_hashes = {
        case: digest(path) for case, path in serial_label_reference_fixtures.items()
    }
    for case, path in serial_label_reference_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != serial_label_reference_source_hashes[case]:
            raise ValueError(
                f"Synthetic UART label {case} fixture changed while preparing native input"
            )
    component_peer_fixtures = {
        f"component-peer-{case}": fixture_root / f"component-peer-power-native/{case}.kicad_sch"
        for case in ("control", "fault")
    }
    component_peer_source_hashes = {
        case: digest(path) for case, path in component_peer_fixtures.items()
    }
    for case, path in component_peer_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != component_peer_source_hashes[case]:
            raise ValueError(
                f"Synthetic component peer {case} fixture changed while preparing native input"
            )
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
        "for case in multi-device peer-control peer-fault peer-translator-control "
        "serial-control serial-fault "
        "serial-reference-fault serial-connector-control serial-connector-fault "
        "serial-label-control serial-label-fault "
        "component-peer-control component-peer-fault; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
        '      "/fixtures/${case}.kicad_sch"\n'
        '    case "$case" in component-peer-*)\n'
        "      kicad-cli sch erc --format json --severity-all "
        '        --output "/output/${case}.${run}.erc.json" '
        '        "/fixtures/${case}.kicad_sch" ;;\n'
        "    esac\n"
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
        "HOME=/tmp/kicad-spi-fixtures",
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
        "spi-participant-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "spi-participant-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native SPI fixture command failed: {command.stderr or command.error}")
    log.event(
        "spi-participant-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_sha256=source_hash,
        peer_source_hashes=";".join(f"{case}:{peer_source_hashes[case]}" for case in peer_fixtures),
        serial_peer_source_hashes=";".join(
            f"{case}:{serial_peer_source_hashes[case]}" for case in serial_peer_fixtures
        ),
        serial_connector_reference_source_hashes=";".join(
            f"{case}:{serial_connector_reference_source_hashes[case]}"
            for case in serial_connector_reference_fixtures
        ),
        serial_label_reference_source_hashes=";".join(
            f"{case}:{serial_label_reference_source_hashes[case]}"
            for case in serial_label_reference_fixtures
        ),
        component_peer_source_hashes=";".join(
            f"{case}:{component_peer_source_hashes[case]}" for case in component_peer_fixtures
        ),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    if (
        digest(fixture) != source_hash
        or digest(source) != source_hash
        or any(
            digest(peer_fixtures[case]) != peer_source_hashes[case]
            or digest(inputs / f"{case}.kicad_sch") != peer_source_hashes[case]
            for case in peer_fixtures
        )
        or any(
            digest(serial_peer_fixtures[case]) != serial_peer_source_hashes[case]
            or digest(inputs / f"{case}.kicad_sch") != serial_peer_source_hashes[case]
            for case in serial_peer_fixtures
        )
        or any(
            digest(serial_connector_reference_fixtures[case])
            != serial_connector_reference_source_hashes[case]
            or digest(inputs / f"{case}.kicad_sch")
            != serial_connector_reference_source_hashes[case]
            for case in serial_connector_reference_fixtures
        )
        or any(
            digest(serial_label_reference_fixtures[case])
            != serial_label_reference_source_hashes[case]
            or digest(inputs / f"{case}.kicad_sch") != serial_label_reference_source_hashes[case]
            for case in serial_label_reference_fixtures
        )
        or any(
            digest(component_peer_fixtures[case]) != component_peer_source_hashes[case]
            or digest(inputs / f"{case}.kicad_sch") != component_peer_source_hashes[case]
            for case in component_peer_fixtures
        )
    ):
        raise ValueError("Synthetic SPI fixture source changed during native export")

    contracts: dict[str, dict[str, NetlistContract]] = {}
    hashes: dict[str, dict[str, str]] = {}
    normalized_hashes: dict[str, dict[str, str]] = {}
    normalized_erc_hashes: dict[str, dict[str, str]] = {}
    erc_report_versions: dict[str, dict[str, str]] = {}
    erc_warning_types: dict[str, dict[str, tuple[str, ...]]] = {}
    erc_error_types: dict[str, dict[str, tuple[str, ...]]] = {}
    fixture_cases = (
        "multi-device",
        *peer_fixtures,
        *serial_peer_fixtures,
        *serial_connector_reference_fixtures,
        *serial_label_reference_fixtures,
        *component_peer_fixtures,
    )
    for fixture_case in fixture_cases:
        contracts[fixture_case] = {}
        hashes[fixture_case] = {}
        normalized_hashes[fixture_case] = {}
        for run in ("first", "repeat"):
            path = output / f"{fixture_case}.{run}.netlist.xml"
            if not path.is_file():
                raise ValueError(f"Native SPI fixture omitted {path.name}")
            hashes[fixture_case][run] = digest(path)
            observed = read_netlist(path)
            contracts[fixture_case][run] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[fixture_case][run] = hashlib.sha256(normalized).hexdigest()

    for case in component_peer_fixtures:
        normalized_erc_hashes[case] = {}
        erc_report_versions[case] = {}
        erc_warning_types[case] = {}
        erc_error_types[case] = {}
        for run in ("first", "repeat"):
            erc_path = output / f"{case}.{run}.erc.json"
            if not erc_path.is_file():
                raise ValueError(f"Native component peer fixture omitted {erc_path.name}")
            erc_report = read_kicad_erc_report(erc_path)
            if erc_report.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native component peer {case} ERC report version differs from KiCad "
                    f"{config.kicad_version}"
                )
            erc_report_versions[case][run] = erc_report.kicad_version
            erc_rows = [
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted(
                            [(detail.description, detail.x, detail.y) for detail in item.items],
                            key=lambda detail: json.dumps(
                                detail,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            ),
                        )
                    ),
                )
                for item in erc_report.violations
            ]
            erc_rows.sort(
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc_report.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[case][run] = hashlib.sha256(normalized_erc).hexdigest()
            erc_warning_types[case][run] = tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "warning")
            )
            erc_error_types[case][run] = tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "error")
            )

    expected_functions = {
        "U1.1": "SPI1_SCLK",
        "U1.2": "SPI1_COPI",
        "U1.3": "SPI1_CIPO",
        "U1.4": "SPI1_NSS",
        "U2.1": "SPI1_SCLK",
        "U2.2": "SPI1_COPI",
        "U2.3": "SPI1_CIPO",
        "U2.4": "SPI1_NSS",
    }
    observed = contracts["multi-device"]["first"]
    if observed.pin_functions != expected_functions:
        raise ValueError(
            "Native netlist no longer preserves the exact SPI pin-function aliases: "
            f"{observed.pin_functions}"
        )
    if observed.component_symbols != {"U1": "Synthetic:SPI_Node", "U2": "Synthetic:SPI_Node"}:
        raise ValueError("Native netlist changed the synthetic SPI component identities")
    if normalized_hashes["multi-device"]["first"] != normalized_hashes["multi-device"]["repeat"]:
        raise ValueError("Native SPI exports differ after normalization to the typed netlist")

    def digital_peer_limits(output_high_maximum_v: float) -> DigitalPeerVoltageAnalysis:
        basis = "Synthetic SPI controller and peripheral voltage specifications"
        return DigitalPeerVoltageAnalysis(
            basis=basis,
            links=(
                DigitalPeerVoltageLink(
                    id="spi-mosi",
                    basis="Controller MOSI directly drives the peripheral SDI pin",
                    driver=DigitalPeerPinRequirement(
                        reference="U1",
                        symbol="Synthetic:SPI_Node",
                        footprint="Synthetic:QFN",
                        pin="U1.2",
                        net="SPI_MOSI",
                    ),
                    receiver=DigitalPeerPinRequirement(
                        reference="U2",
                        symbol="Synthetic:SPI_Node",
                        footprint="Synthetic:QFN",
                        pin="U2.2",
                        net="SPI_MOSI",
                    ),
                    output_limits=DigitalLogicOutputLimits(
                        low_minimum_v=0.0,
                        low_maximum_v=0.4,
                        high_minimum_v=2.8,
                        high_maximum_v=output_high_maximum_v,
                        source="Synthetic controller datasheet Rev A, Table 1",
                        conditions="VDD=3.3 V, specified output load, full operating range",
                    ),
                    input_limits=DigitalLogicInputLimits(
                        absolute_minimum_v=-0.3,
                        low_maximum_v=0.8,
                        high_minimum_v=2.0,
                        absolute_maximum_v=3.6,
                        source="Synthetic peripheral datasheet Rev B, Table 2",
                        conditions="VDD=3.3 V, full operating range",
                    ),
                ),
            ),
        )

    voltage_cases = {
        "voltage-control": (digital_peer_limits(3.3), "PASS"),
        "voltage-fault": (digital_peer_limits(5.0), "FAIL"),
    }
    for case, (spec, expected_status) in voltage_cases.items():
        by_run = {
            run: digital_peer_voltage_checks(spec, contracts["multi-device"][run])
            for run in ("first", "repeat")
        }
        if by_run["first"] != by_run["repeat"]:
            raise ValueError(f"Native SPI {case} voltage evidence changed on repeated export")
        checks = {item.id: item for item in by_run["first"]}
        compatibility = checks["digital-peer-voltage/spi-mosi/compatibility"]
        if (
            compatibility.status != expected_status
            or compatibility.observed is None
            or checks["digital-peer-voltage/spi-mosi/driver/identity"].status != "PASS"
            or checks["digital-peer-voltage/spi-mosi/driver/pin"].status != "PASS"
            or checks["digital-peer-voltage/spi-mosi/receiver/identity"].status != "PASS"
            or checks["digital-peer-voltage/spi-mosi/receiver/pin"].status != "PASS"
        ):
            raise ValueError(f"Native SPI {case} voltage check lost its exact pin or limit result")
        log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hash,
            netlist_sha256=hashes["multi-device"]["first"],
            repeat_netlist_sha256=hashes["multi-device"]["repeat"],
            normalized_netlist_sha256=normalized_hashes["multi-device"]["first"],
            repeat_normalized_netlist_sha256=normalized_hashes["multi-device"]["repeat"],
            compatibility_status=compatibility.status,
            minimum_margin_v=compatibility.observed,
            driver="U1.2/SPI_MOSI",
            receiver="U2.2/SPI_MOSI",
            repeated_checks_match="true",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_electrical_checks",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    basis = "Synthetic exact native netlist comparison for roster fault/control coverage"
    controller = SpiControllerRequirement(
        reference="U1",
        symbol="Synthetic:SPI_Node",
        footprint="Synthetic:QFN",
        sck=SpiPinNetRequirement(pin="U1.1", net="SPI_SCK"),
        mosi=SpiPinNetRequirement(pin="U1.2", net="SPI_MOSI"),
        miso=SpiMisoConnectedRequirement(mode="connected", pin="U1.3", net="SPI_MISO"),
        chip_selects=(SpiPinNetRequirement(pin="U1.4", net="SPI_CS"),),
    )
    device = SpiDeviceRequirement(
        id="PERIPHERAL",
        reference="U2",
        symbol="Synthetic:SPI_Node",
        footprint="Synthetic:QFN",
        sck=SpiPinNetRequirement(pin="U2.1", net="SPI_SCK"),
        mosi=SpiPinNetRequirement(pin="U2.2", net="SPI_MOSI"),
        miso=SpiMisoConnectedRequirement(mode="connected", pin="U2.3", net="SPI_MISO"),
        chip_select=SpiPinNetRequirement(pin="U2.4", net="SPI_CS"),
    )
    roster = SpiAnalysis(
        basis=basis,
        buses=(
            SpiBusRequirement(
                id="MAIN",
                basis=basis,
                controller=controller,
                devices=(device,),
            ),
        ),
    )

    reports: dict[str, DesignLintReport] = {}
    for case, context in (
        ("unrostered", SpiRosterContext(state="not_configured")),
        ("rostered", SpiRosterContext(state="required", analysis=roster)),
    ):
        project_id = f"synthetic-spi-participants-{case}"
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=project_id,
            observed=observed,
            netlist_sha256=hashes["multi-device"]["first"],
        )
        reports[case] = evaluate(
            project_id,
            coach,
            DesignLintPolicy(),
            spi_roster=context,
        )

    unrostered = reports["unrostered"]
    spi_findings = tuple(
        item for item in unrostered.findings if item.rule_id == "bus.spi_unmapped_participant"
    )
    if unrostered.status != "REVIEW" or {item.subject for item in spi_findings} != {
        "U1: SPI roster coverage",
        "U2: SPI roster coverage",
    }:
        raise ValueError(
            "Unrostered native SPI participants no longer produce exact review findings"
        )
    if any(item.evidence["SPI_roster_state"] != ("not_configured",) for item in spi_findings):
        raise ValueError("Native SPI findings lost the unconfigured-roster evidence")

    rostered = reports["rostered"]
    if rostered.status != "PASS" or rostered.findings:
        raise ValueError("The exact SPI roster control no longer suppresses all review findings")

    for case, report in reports.items():
        log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hash,
            netlist_sha256=hashes["multi-device"]["first"],
            repeat_netlist_sha256=hashes["multi-device"]["repeat"],
            normalized_netlist_sha256=normalized_hashes["multi-device"]["first"],
            repeat_normalized_netlist_sha256=normalized_hashes["multi-device"]["repeat"],
            lint_status=report.status,
            findings=";".join(item.subject for item in report.findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}" for pin, name in sorted(observed.pin_functions.items())
            ),
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    peer_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="bus.spi_unmapped_participant",
                mode="off",
                reason="Isolate the synthetic peer-voltage native fixture.",
            ),
            DesignLintRuleOverride(
                rule_id="power.ic_rail_without_fitted_capacitor",
                mode="off",
                reason="Isolate peer-domain review from decoupling coverage.",
            ),
        )
    )
    for case, expected_status in (
        ("peer-control", "PASS"),
        ("peer-fault", "REVIEW"),
        ("peer-translator-control", "PASS"),
    ):
        peer_contracts = contracts[case]
        peer_observed = peer_contracts["first"]
        if normalized_hashes[case]["first"] != normalized_hashes[case]["repeat"]:
            raise ValueError(f"Native SPI {case} exports differ after typed-netlist normalization")
        if case == "peer-translator-control":
            expected_pin_functions = {
                "U1.1": "SPI1_SCLK",
                "U1.2": "VDD",
                "U1.3": "GND",
                "U2.1": "SPI1_SCLK",
                "U2.2": "VDD",
                "U2.3": "GND",
                "U3.1": "A_SCLK",
                "U3.2": "B_SCLK",
                "U3.3": "VCCA",
                "U3.4": "VCCB",
                "U3.5": "GND",
            }
            expected_pin_types = {
                "U1.1": "output",
                "U1.2": "power_in",
                "U1.3": "power_in",
                "U2.1": "input",
                "U2.2": "power_in",
                "U2.3": "power_in",
                "U3.1": "input",
                "U3.2": "output",
                "U3.3": "power_in",
                "U3.4": "power_in",
                "U3.5": "power_in",
            }
            expected_symbols = {
                "U1": "Synthetic:SPI_Controller",
                "U2": "Synthetic:SPI_Peripheral",
                "U3": "Synthetic:SPI_LevelTranslator",
            }
            expected_pin_numbers = {
                "U1": ("1", "2", "3"),
                "U2": ("1", "2", "3"),
                "U3": ("1", "2", "3", "4", "5"),
            }
        else:
            expected_pin_functions = {
                "U1.1": "SPI1_SCLK",
                "U1.2": "VDD",
                "U2.1": "SPI1_SCLK",
                "U2.2": "VDD",
            }
            expected_pin_types = {
                "U1.1": "output",
                "U1.2": "power_in",
                "U2.1": "input",
                "U2.2": "power_in",
            }
            expected_symbols = {
                "U1": "Synthetic:SPI_Controller",
                "U2": "Synthetic:SPI_Peripheral",
            }
            expected_pin_numbers = {"U1": ("1", "2"), "U2": ("1", "2")}
        if peer_observed.pin_functions != expected_pin_functions:
            raise ValueError(
                f"Native SPI {case} export lost the exact signal and supply pin functions: "
                f"{peer_observed.pin_functions}"
            )
        if peer_observed.pin_electrical_types != expected_pin_types:
            raise ValueError(
                f"Native SPI {case} export lost the complete pin-type inventory: "
                f"{peer_observed.pin_electrical_types}"
            )
        if peer_observed.component_symbols != expected_symbols:
            raise ValueError(f"Native SPI {case} export changed synthetic component identities")
        if peer_observed.component_pin_numbers != expected_pin_numbers:
            raise ValueError(f"Native SPI {case} export changed the full component pin inventory")
        expected_rails = (
            {"+3V3": ("U2.2", "U3.4"), "+5V": ("U1.2", "U3.3")}
            if case == "peer-translator-control"
            else (
                {"+3V3": ("U1.2", "U2.2")}
                if case == "peer-control"
                else {"+3V3": ("U2.2",), "+5V": ("U1.2",)}
            )
        )
        if {net: pins for net, pins in peer_observed.nets.items() if net in {"+3V3", "+5V"}} != (
            expected_rails
        ):
            raise ValueError(f"Native SPI {case} export changed its synthetic supply assignments")
        expected_signal_nets: dict[str, tuple[str, ...]] = {}
        if case == "peer-translator-control":
            expected_signal_nets = {
                "SPI_A_SIDE": ("U1.1", "U3.1"),
                "SPI_B_SIDE": ("U2.1", "U3.2"),
            }
            observed_signal_nets = {
                net: pins for net, pins in peer_observed.nets.items() if net.startswith("SPI_")
            }
            if observed_signal_nets != expected_signal_nets:
                raise ValueError(
                    "Native SPI translator control no longer separates its A- and B-side nets"
                )
        peer_reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            report_coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-spi-peer-voltage-{case}",
                observed=peer_contracts[run],
                netlist_sha256=hashes[case][run],
            )
            peer_reports[run] = evaluate(
                report_coach.project_id,
                report_coach,
                peer_policy,
            )
        findings = tuple(
            item
            for item in peer_reports["first"].findings
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        repeated_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in peer_reports["repeat"].findings
        )
        first_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in peer_reports["first"].findings
        )
        if (
            peer_reports["first"].status != expected_status
            or peer_reports["repeat"].status != expected_status
            or first_findings != repeated_findings
            or (case == "peer-control" and findings)
            or (case == "peer-fault" and len(findings) != 1)
        ):
            raise ValueError(f"Native SPI {case} no longer matches its peer-voltage review case")
        if findings and findings[0].mode != "review":
            raise ValueError("SPI peer-voltage heuristic no longer defaults to REVIEW")
        if case == "peer-fault" and dict(findings[0].evidence) != {
            "authored_voltage_map_state": ("not_configured",),
            "input_component": ("U2",),
            "input_supply_label_value": ("3.3 V",),
            "input_supply_net": ("+3V3",),
            "output_component": ("U1",),
            "output_supply_label_value": ("5 V",),
            "output_supply_net": ("+5V",),
            "shared_SPI_pin_assignments": (
                "SPI_SCK: U1.1 (SPI1_SCLK, output) -> U2.1 (SPI1_SCLK, input)",
            ),
        }:
            raise ValueError("Native SPI peer-voltage finding lost exact rail or pin evidence")
        log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=peer_source_hashes[case],
            netlist_sha256=hashes[case]["first"],
            repeat_netlist_sha256=hashes[case]["repeat"],
            normalized_netlist_sha256=normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=normalized_hashes[case]["repeat"],
            lint_status=peer_reports["first"].status,
            peer_voltage_findings=";".join(item.rule_id for item in findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}" for pin, name in sorted(peer_observed.pin_functions.items())
            ),
            pin_types=";".join(
                f"{pin}={name}" for pin, name in sorted(peer_observed.pin_electrical_types.items())
            ),
            rail_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_rails)
            ),
            signal_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_signal_nets)
            )
            or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    serial_peer_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="power.ic_rail_without_fitted_capacitor",
                mode="off",
                reason="Isolate the synthetic serial peer-voltage fixture.",
            ),
        )
    )
    for case, expected_status in (
        ("serial-control", "PASS"),
        ("serial-fault", "REVIEW"),
        ("serial-reference-fault", "REVIEW"),
    ):
        peer_observed = contracts[case]["first"]
        if normalized_hashes[case]["first"] != normalized_hashes[case]["repeat"]:
            raise ValueError(f"Native UART {case} exports differ after typed-netlist normalization")
        expected_functions = {
            "U1.1": "UART1_TX",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "UART1_RX",
            "U2.2": "VDD",
            "U2.3": "GND",
        }
        expected_pin_types = {
            "U1.1": "output",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "input",
            "U2.2": "power_in",
            "U2.3": "power_in",
        }
        expected_symbols = {
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
        }
        if peer_observed.pin_functions != expected_functions:
            raise ValueError(
                f"Native UART {case} export lost exact signal or supply functions: "
                f"{peer_observed.pin_functions}"
            )
        if peer_observed.pin_electrical_types != expected_pin_types:
            raise ValueError(
                f"Native UART {case} export lost complete native pin types: "
                f"{peer_observed.pin_electrical_types}"
            )
        if peer_observed.component_symbols != expected_symbols:
            raise ValueError(f"Native UART {case} export changed synthetic component identities")
        if peer_observed.component_pin_numbers != {
            "U1": ("1", "2", "3"),
            "U2": ("1", "2", "3"),
        }:
            raise ValueError(
                f"Native UART {case} export changed complete component pin inventories"
            )
        expected_rails = (
            {"+3V3": ("U1.2", "U2.2")}
            if case in {"serial-control", "serial-reference-fault"}
            else {"+5V": ("U1.2",), "+3V3": ("U2.2",)}
        )
        if {
            net: pins for net, pins in peer_observed.nets.items() if net in {"+3V3", "+5V"}
        } != expected_rails:
            raise ValueError(f"Native UART {case} export changed exact supply assignments")
        expected_references = (
            {"GND": ("U1.3", "U2.3")}
            if case in {"serial-control", "serial-fault"}
            else {"GND_A": ("U1.3",), "GND_B": ("U2.3",)}
        )
        if {
            net: pins
            for net, pins in peer_observed.nets.items()
            if net in {"GND", "GND_A", "GND_B"}
        } != expected_references:
            raise ValueError(f"Native UART {case} export changed exact reference assignments")

        reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            report_coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-uart-peer-voltage-{case}",
                observed=contracts[case][run],
                netlist_sha256=hashes[case][run],
            )
            reports[run] = evaluate(report_coach.project_id, report_coach, serial_peer_policy)
        findings = tuple(
            item
            for item in reports["first"].findings
            if item.rule_id == "bus.serial_peer_voltage_review"
        )
        reference_findings = tuple(
            item
            for item in reports["first"].findings
            if item.rule_id == "bus.serial_peer_reference_review"
        )
        first_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["first"].findings
        )
        repeated_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["repeat"].findings
        )
        if (
            reports["first"].status != expected_status
            or reports["repeat"].status != expected_status
            or first_signature != repeated_signature
            or (case in {"serial-control", "serial-reference-fault"} and findings)
            or (case == "serial-fault" and len(findings) != 1)
            or (case in {"serial-control", "serial-fault"} and reference_findings)
            or (case == "serial-reference-fault" and len(reference_findings) != 1)
        ):
            raise ValueError(f"Native UART {case} no longer matches its peer-review cases")
        if findings and (
            findings[0].mode != "review"
            or dict(findings[0].evidence)
            != {
                "authored_voltage_map_state": ("not_configured",),
                "input_component": ("U2",),
                "input_supply_label_value": ("3.3 V",),
                "input_supply_net": ("+3V3",),
                "output_component": ("U1",),
                "output_supply_label_value": ("5 V",),
                "output_supply_net": ("+5V",),
                "shared_serial_pin_assignments": (
                    "UART_TX: U1.1 (UART1_TX, output) -> U2.1 (UART1_RX, input)",
                ),
            }
        ):
            raise ValueError("Native UART peer-voltage finding lost exact review evidence")
        if reference_findings and (
            reference_findings[0].mode != "review"
            or dict(reference_findings[0].evidence)
            != {
                "first_component": ("U1",),
                "first_reference_net": ("GND_A",),
                "first_reference_pin_assignments": ("U1.3 (GND, power_in)=GND_A",),
                "second_component": ("U2",),
                "second_reference_net": ("GND_B",),
                "second_reference_pin_assignments": ("U2.3 (GND, power_in)=GND_B",),
                "shared_serial_pin_assignments": (
                    "UART_TX: U1.1 (UART1_TX, output) -> U2.1 (UART1_RX, input)",
                ),
                "serial_peer_map_state": ("not_configured",),
            }
        ):
            raise ValueError("Native UART peer-reference finding lost exact pin/net evidence")
        log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=serial_peer_source_hashes[case],
            netlist_sha256=hashes[case]["first"],
            repeat_netlist_sha256=hashes[case]["repeat"],
            normalized_netlist_sha256=normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=normalized_hashes[case]["repeat"],
            lint_status=reports["first"].status,
            peer_voltage_findings=";".join(item.rule_id for item in findings) or "none",
            peer_reference_findings=";".join(item.rule_id for item in reference_findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}" for pin, name in sorted(peer_observed.pin_functions.items())
            ),
            pin_types=";".join(
                f"{pin}={name}" for pin, name in sorted(peer_observed.pin_electrical_types.items())
            ),
            rail_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_rails)
            ),
            reference_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_references)
            ),
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    for case in ("serial-connector-control", "serial-connector-fault"):
        peer_contracts = contracts[case]
        peer_observed = peer_contracts["first"]
        if normalized_hashes[case]["first"] != normalized_hashes[case]["repeat"]:
            raise ValueError(
                f"Native UART connector {case} exports differ after typed-netlist normalization"
            )
        expected_functions = {
            "J1.1": "UART1_RX",
            "J1.2": "UART1_TX",
            "J1.3": "VDD",
            "J1.4": "GND",
            "U1.1": "UART1_TX",
            "U1.2": "UART1_RX",
            "U1.3": "VDD",
            "U1.4": "GND",
        }
        expected_pin_types = {
            "J1.1": "input",
            "J1.2": "output",
            "J1.3": "passive",
            "J1.4": "passive",
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
        }
        expected_symbols = {
            "J1": "Synthetic:UartHeader",
            "U1": "Synthetic:UartController",
        }
        expected_pin_numbers = {"J1": ("1", "2", "3", "4"), "U1": ("1", "2", "3", "4")}
        expected_references = (
            {"GND_A": ("J1.4", "U1.4")}
            if case == "serial-connector-control"
            else {"GND_A": ("U1.4",), "GND_B": ("J1.4",)}
        )
        if (
            peer_observed.pin_functions != expected_functions
            or peer_observed.pin_electrical_types != expected_pin_types
            or peer_observed.component_symbols != expected_symbols
            or peer_observed.component_pin_numbers != expected_pin_numbers
        ):
            raise ValueError(f"Native UART connector {case} export lost exact symbol pin evidence")
        if {net: pins for net, pins in peer_observed.nets.items() if net.startswith("GND")} != (
            expected_references
        ):
            raise ValueError(
                f"Native UART connector {case} export changed its reference assignments"
            )
        expected_signal_nets = {
            "UART_RX": ("J1.2", "U1.2"),
            "UART_TX": ("J1.1", "U1.1"),
        }
        if {
            net: pins for net, pins in peer_observed.nets.items() if net.startswith("UART_")
        } != expected_signal_nets:
            raise ValueError(f"Native UART connector {case} export changed its TX/RX assignments")

        reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            report_coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-uart-connector-reference-{case}",
                observed=peer_contracts[run],
                netlist_sha256=hashes[case][run],
            )
            reports[run] = evaluate(
                report_coach.project_id,
                report_coach,
                serial_peer_policy,
            )
        reference_findings = tuple(
            item
            for item in reports["first"].findings
            if item.rule_id == "bus.serial_peer_reference_review"
        )
        first_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["first"].findings
        )
        repeated_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["repeat"].findings
        )
        expected_reference_count = 0 if case == "serial-connector-control" else 1
        if (
            first_signature != repeated_signature
            or reports["first"].status != "REVIEW"
            or reports["repeat"].status != "REVIEW"
            or len(reference_findings) != expected_reference_count
        ):
            raise ValueError(
                f"Native UART connector {case} no longer matches its reference review case"
            )
        if reference_findings and (
            reference_findings[0].mode != "review"
            or reference_findings[0].subject != "J1 / U1: serial reference-domain review"
            or dict(reference_findings[0].evidence)
            != {
                "first_component": ("J1",),
                "first_reference_net": ("GND_B",),
                "first_reference_pin_assignments": ("J1.4 (GND, passive)=GND_B",),
                "second_component": ("U1",),
                "second_reference_net": ("GND_A",),
                "second_reference_pin_assignments": ("U1.4 (GND, power_in)=GND_A",),
                "shared_serial_pin_assignments": (
                    "UART_RX: J1.2 (UART1_TX, output) -> U1.2 (UART1_RX, input)",
                    "UART_TX: U1.1 (UART1_TX, output) -> J1.1 (UART1_RX, input)",
                ),
                "serial_peer_map_state": ("not_configured",),
            }
        ):
            raise ValueError("Native UART connector reference finding lost exact pin/net evidence")
        log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=serial_connector_reference_source_hashes[case],
            netlist_sha256=hashes[case]["first"],
            repeat_netlist_sha256=hashes[case]["repeat"],
            normalized_netlist_sha256=normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=normalized_hashes[case]["repeat"],
            lint_status=reports["first"].status,
            peer_reference_findings=";".join(item.rule_id for item in reference_findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}" for pin, name in sorted(peer_observed.pin_functions.items())
            ),
            pin_types=";".join(
                f"{pin}={name}" for pin, name in sorted(peer_observed.pin_electrical_types.items())
            ),
            signal_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_signal_nets)
            ),
            reference_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_references)
            ),
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    expected_signal_data = read_model(
        fixture_root / "serial-peer-connector-reference-native/serial-label-expected-nets.json",
        SerialLabelFixtureExpectedNets,
    )
    expected_signal_nets = {
        "UART.0.RX": expected_signal_data.rx,
        "UART.0.TX": expected_signal_data.tx,
    }

    for case in ("serial-label-control", "serial-label-fault"):
        peer_contracts = contracts[case]
        peer_observed = peer_contracts["first"]
        if normalized_hashes[case]["first"] != normalized_hashes[case]["repeat"]:
            raise ValueError(
                f"Native UART label {case} exports differ after typed-netlist normalization"
            )
        expected_functions = {
            "U1.1": "B2",
            "U1.2": "B1",
            "U1.3": "VDD",
            "U1.4": "GND",
            "U2.1": "ADBUS0",
            "U2.2": "ADBUS1",
            "U2.3": "VDD",
            "U2.4": "GND",
        }
        expected_pin_types = {
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
            "U2.1": "input",
            "U2.2": "output",
            "U2.3": "passive",
            "U2.4": "passive",
        }
        expected_symbols = {
            "U1": "Synthetic:UartController",
            "U2": "Synthetic:UartBridge",
        }
        expected_pin_numbers = {"U1": ("1", "2", "3", "4"), "U2": ("1", "2", "3", "4")}
        expected_references = (
            {"GND_A": ("U1.4", "U2.4")}
            if case == "serial-label-control"
            else {"GND_A": ("U1.4",), "GND_B": ("U2.4",)}
        )
        if (
            peer_observed.pin_functions != expected_functions
            or peer_observed.pin_electrical_types != expected_pin_types
            or peer_observed.component_symbols != expected_symbols
            or peer_observed.component_pin_numbers != expected_pin_numbers
        ):
            raise ValueError(f"Native UART label {case} export lost exact generic pin evidence")
        if {
            net: pins for net, pins in peer_observed.nets.items() if net.startswith("GND")
        } != expected_references:
            raise ValueError(f"Native UART label {case} export changed its reference assignments")
        if {
            net: pins for net, pins in peer_observed.nets.items() if net.startswith("UART.")
        } != expected_signal_nets:
            raise ValueError(f"Native UART label {case} export changed its labeled TX/RX nets")

        reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            report_coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-uart-label-reference-{case}",
                observed=peer_contracts[run],
                netlist_sha256=hashes[case][run],
            )
            reports[run] = evaluate(report_coach.project_id, report_coach, DesignLintPolicy())
        reference_findings = tuple(
            item
            for item in reports["first"].findings
            if item.rule_id == "bus.serial_peer_reference_review"
        )
        first_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["first"].findings
        )
        repeated_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["repeat"].findings
        )
        expected_reference_count = 0 if case == "serial-label-control" else 1
        if (
            first_signature != repeated_signature
            or reports["first"].status != "REVIEW"
            or reports["repeat"].status != "REVIEW"
            or len(reference_findings) != expected_reference_count
        ):
            raise ValueError(
                f"Native UART label {case} no longer matches its reference review case"
            )
        if reference_findings and (
            reference_findings[0].mode != "review"
            or reference_findings[0].subject != "U1 / U2: serial reference-domain review"
            or dict(reference_findings[0].evidence)
            != {
                "discovery_basis": ("net_label",),
                "first_component": ("U1",),
                "first_reference_net": ("GND_A",),
                "first_reference_pin_assignments": ("U1.4 (GND, power_in)=GND_A",),
                "second_component": ("U2",),
                "second_reference_net": ("GND_B",),
                "second_reference_pin_assignments": ("U2.4 (GND, passive)=GND_B",),
                "serial_label_link_assignments": (
                    "uart0: TX UART.0.TX (U1.1, U2.1); RX UART.0.RX (U1.2, U2.2)",
                ),
                "serial_peer_map_state": ("not_configured",),
            }
        ):
            raise ValueError("Native UART label reference finding lost exact pin/net evidence")
        log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=serial_label_reference_source_hashes[case],
            netlist_sha256=hashes[case]["first"],
            repeat_netlist_sha256=hashes[case]["repeat"],
            normalized_netlist_sha256=normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=normalized_hashes[case]["repeat"],
            lint_status=reports["first"].status,
            peer_reference_findings=";".join(item.rule_id for item in reference_findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}" for pin, name in sorted(peer_observed.pin_functions.items())
            ),
            pin_types=";".join(
                f"{pin}={name}" for pin, name in sorted(peer_observed.pin_electrical_types.items())
            ),
            signal_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_signal_nets)
            ),
            reference_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_references)
            ),
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    component_peer_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="bus.spi_unmapped_participant",
                mode="off",
                reason="Isolate the synthetic component peer power-pin fixture.",
            ),
            DesignLintRuleOverride(
                rule_id="power.ic_rail_without_fitted_capacitor",
                mode="off",
                reason="Isolate peer pin assignment review from decoupling coverage.",
            ),
        )
    )
    for case, expected_status, expected_count in (
        ("component-peer-control", "PASS", 0),
        ("component-peer-fault", "REVIEW", 2),
    ):
        peer_contracts = contracts[case]
        peer_observed = peer_contracts["first"]
        if normalized_hashes[case]["first"] != normalized_hashes[case]["repeat"]:
            raise ValueError(
                f"Native component peer {case} exports differ after typed-netlist normalization"
            )
        if normalized_erc_hashes[case]["first"] != normalized_erc_hashes[case]["repeat"]:
            raise ValueError(f"Native component peer {case} ERC reports are not repeatable")
        expected_pin_functions = {
            "U1.1": "IO",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "IO",
            "U2.2": "VDD",
            "U2.3": "GND",
        }
        expected_pin_types = {
            "U1.1": "passive",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "passive",
            "U2.2": "power_in",
            "U2.3": "power_in",
        }
        if peer_observed.pin_functions != expected_pin_functions:
            raise ValueError(
                f"Native component peer {case} export changed pin functions: "
                f"{peer_observed.pin_functions}"
            )
        if peer_observed.pin_electrical_types != expected_pin_types:
            raise ValueError(
                f"Native component peer {case} export changed pin types: "
                f"{peer_observed.pin_electrical_types}"
            )
        if peer_observed.component_symbols != {
            "U1": "Synthetic:PeerModule",
            "U2": "Synthetic:PeerModule",
        }:
            raise ValueError(f"Native component peer {case} lost the shared exact symbol identity")
        if peer_observed.component_pin_numbers != {
            "U1": ("1", "2", "3"),
            "U2": ("1", "2", "3"),
        }:
            raise ValueError(f"Native component peer {case} changed the complete pin inventory")

        reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-component-peer-power-{case}",
                observed=peer_contracts[run],
                netlist_sha256=hashes[case][run],
            )
            reports[run] = evaluate(
                coach.project_id,
                coach,
                component_peer_policy,
            )
        findings = tuple(
            item
            for item in reports["first"].findings
            if item.rule_id == "component.peer_power_pin_assignment_divergence"
        )
        active_findings = tuple(item for item in reports["first"].findings if item.mode != "off")
        first_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["first"].findings
        )
        repeat_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["repeat"].findings
        )
        if (
            reports["first"].status != expected_status
            or reports["repeat"].status != expected_status
            or len(active_findings) != expected_count
            or any(
                item.rule_id != "component.peer_power_pin_assignment_divergence"
                for item in active_findings
            )
            or len(findings) != expected_count
            or first_findings != repeat_findings
            or any(item.mode != "review" for item in findings)
        ):
            raise ValueError(
                f"Native component peer {case} no longer matches its power-pin review case"
            )
        divergence_roles = tuple(
            sorted(
                (
                    item.evidence["pin_number"][0],
                    item.evidence["pin_function"][0],
                    item.evidence["peer_role"][0],
                )
                for item in findings
            )
        )
        expected_roles = (
            (("2", "VDD", "supply"), ("3", "GND", "ground/return"))
            if case == "component-peer-fault"
            else ()
        )
        if divergence_roles != expected_roles:
            raise ValueError(
                f"Native component peer {case} changed its exact divergent pin roles: "
                f"{divergence_roles}"
            )
        pin_assignments = {
            pin: net
            for net, pins in peer_observed.nets.items()
            for pin in pins
            if pin.startswith(("U1.", "U2."))
        }
        log.event(
            f"component-peer-power-fixture/{case.removeprefix('component-peer-')}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=component_peer_source_hashes[case],
            netlist_sha256=hashes[case]["first"],
            repeat_netlist_sha256=hashes[case]["repeat"],
            normalized_netlist_sha256=normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=normalized_hashes[case]["repeat"],
            erc_report_version=erc_report_versions[case]["first"],
            normalized_erc_sha256=normalized_erc_hashes[case]["first"],
            repeat_normalized_erc_sha256=normalized_erc_hashes[case]["repeat"],
            erc_warning_types=";".join(erc_warning_types[case]["first"]) or "none",
            erc_error_types=";".join(erc_error_types[case]["first"]) or "none",
            lint_status=reports["first"].status,
            peer_power_findings=";".join(item.rule_id for item in findings) or "none",
            divergent_pin_roles=";".join(
                f"{pin}:{function}:{role}" for pin, function, role in divergence_roles
            )
            or "none",
            pin_assignments=";".join(
                f"{pin}={net}" for pin, net in sorted(pin_assignments.items())
            ),
            pin_functions=";".join(
                f"{pin}={name}" for pin, name in sorted(peer_observed.pin_functions.items())
            ),
            pin_types=";".join(
                f"{pin}={name}" for pin, name in sorted(peer_observed.pin_electrical_types.items())
            ),
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )


def can_peer_assignment_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify cross-peer CAN pair review from repeated pinned native exports."""
    import hashlib

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintFinding,
        DesignLintPolicy,
        DesignLintReport,
        NetlistContract,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"CAN peer fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/can-peer-native"
    )
    cases = ("peer-control", "peer-fault")
    source_hashes = {case: digest(fixture_root / f"{case}.kicad_sch") for case in cases}
    scratch = Path(tempfile.mkdtemp(prefix=f"can-peer-{project}-", dir=log.directory.resolve()))
    inputs = scratch / "input"
    inputs.mkdir()
    for case in cases:
        fixture = fixture_root / f"{case}.kicad_sch"
        copied = inputs / fixture.name
        shutil.copyfile(fixture, copied)
        if digest(copied) != source_hashes[case]:
            raise ValueError(f"Synthetic CAN {case} fixture changed while preparing native input")
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
        "for case in peer-control peer-fault; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
        '      "/fixtures/${case}.kicad_sch"\n'
        "    kicad-cli sch erc --format json --severity-all "
        '      --output "/output/${case}.${run}.erc.json" '
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
        "HOME=/tmp/kicad-can-peer-fixtures",
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
        "can-peer-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "can-peer-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native CAN peer fixture command failed: {command.stderr or command.error}"
        )

    logs: dict[
        str,
        tuple[DesignLintReport, tuple[DesignLintFinding, ...], str, tuple[str, ...]],
    ] = {}
    for case in cases:
        observed_by_run: dict[str, NetlistContract] = {}
        normalized_hashes: dict[str, str] = {}
        normalized_erc_hashes: dict[str, str] = {}
        erc_warning_types: dict[str, tuple[str, ...]] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native CAN peer {case} export omitted an expected report")
            observed = read_netlist(netlist_path)
            observed_by_run[run] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native CAN peer {case} ERC report version differs from KiCad "
                    f"{config.kicad_version}"
                )
            erc_rows = [
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted(
                            [(detail.description, detail.x, detail.y) for detail in item.items],
                            key=lambda detail: json.dumps(
                                detail,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            ),
                        )
                    ),
                )
                for item in erc.violations
            ]
            erc_rows.sort(
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[run] = hashlib.sha256(normalized_erc).hexdigest()
            erc_errors = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            if erc_errors:
                raise ValueError(f"Native CAN peer {case} has unexpected ERC errors: {erc_errors}")
            erc_warning_types[run] = tuple(
                sorted({item.type for item in erc.violations if item.severity == "warning"})
            )
        if normalized_hashes["first"] != normalized_hashes["repeat"]:
            raise ValueError(f"Native CAN peer {case} exports are not repeatable")
        if normalized_erc_hashes["first"] != normalized_erc_hashes["repeat"]:
            raise ValueError(f"Native CAN peer {case} ERC reports are not repeatable")
        observed = observed_by_run["first"]
        expected_functions: dict[str, str] = {
            "U1.1": "CANH",
            "U1.2": "CAN_L",
            "U2.1": "CANH",
            "U2.2": "CAN_L",
            "U3.1": "CANH",
            "U3.2": "CAN_L",
        }
        if observed.pin_functions != expected_functions:
            raise ValueError(f"Native CAN peer {case} lost exact pair pin functions")
        if any(
            observed.component_pin_numbers.get(reference) != ("1", "2")
            for reference in ("U1", "U2", "U3", "R1", *(("R2",) if case == "peer-fault" else ()))
        ):
            raise ValueError(f"Native CAN peer {case} lost a complete component pin inventory")
        expected_nets = (
            {"NET_A": {"U1.1", "U2.1", "U3.1", "R1.1"}, "NET_B": {"U1.2", "U2.2", "U3.2", "R1.2"}}
            if case == "peer-control"
            else {
                "NET_A": {"U1.1", "U2.1", "U3.1", "R1.1", "R2.1"},
                "NET_B": {"U1.2", "U2.2", "R1.2"},
                "NET_C": {"U3.2", "R2.2"},
            }
        )
        if {net: set(observed.nets.get(net, ())) for net in expected_nets} != expected_nets:
            raise ValueError(f"Native CAN peer {case} changed the expected net assignments")
        report = evaluate(
            f"synthetic-can-peer-{case}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-can-peer-{case}",
                observed=observed,
                netlist_sha256=digest(output / f"{case}.first.netlist.xml"),
            ),
            DesignLintPolicy(),
        )
        matching = tuple(
            item for item in report.findings if item.rule_id == "bus.can_peer_assignment_divergence"
        )
        expected_status = "PASS" if case == "peer-control" else "REVIEW"
        expected_evidence = {
            "shared_role": ("CANH",),
            "shared_net": ("NET_A",),
            "complementary_role": ("CANL",),
            "complementary_nets": ("NET_B", "NET_C"),
            "participants": (
                "U1:U1.1=CANH/NET_A;U1.2=CANL/NET_B",
                "U2:U2.1=CANH/NET_A;U2.2=CANL/NET_B",
                "U3:U3.1=CANH/NET_A;U3.2=CANL/NET_C",
            ),
        }
        if (
            report.status != expected_status
            or len(report.findings) != len(matching)
            or len(matching) != (0 if case == "peer-control" else 1)
            or (case == "peer-fault" and matching[0].mode != "review")
            or (case == "peer-fault" and dict(matching[0].evidence) != expected_evidence)
        ):
            raise ValueError(f"Native CAN peer {case} no longer matches its lint control/fault")
        report_repeat = evaluate(
            f"synthetic-can-peer-{case}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-can-peer-{case}",
                observed=observed_by_run["repeat"],
                netlist_sha256=digest(output / f"{case}.repeat.netlist.xml"),
            ),
            DesignLintPolicy(),
        )
        semantic_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence) for item in report.findings
        )
        repeated_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in report_repeat.findings
        )
        if semantic_findings != repeated_findings:
            raise ValueError(f"Native CAN peer {case} lint report is not repeatable")
        logs[case] = (
            report,
            matching,
            normalized_hashes["first"],
            erc_warning_types["first"],
        )

    for case in cases:
        report, findings, normalized_sha256, warning_types = logs[case]
        log.event(
            f"can-peer-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_sha256,
            lint_status=report.status,
            findings=";".join(item.rule_id for item in findings) or "none",
            erc_errors="0",
            erc_warning_types=";".join(warning_types) or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_erc_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "can-peer-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )


def open_drain_bias_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify open-output bias candidates from repeated pinned native exports."""
    import hashlib

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintFinding,
        DesignLintPolicy,
        NetlistContract,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Open-output bias fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/open-drain-native"
    )
    cases = {
        "collector-control": (
            "open_collector",
            "pull-up to a recognized positive rail",
            "+3V3",
            False,
        ),
        "collector-fault": (
            "open_collector",
            "pull-up to a recognized positive rail",
            "+3V3",
            True,
        ),
        "emitter-control": ("open_emitter", "pull-down to a recognized return", "GND", False),
        "emitter-fault": ("open_emitter", "pull-down to a recognized return", "GND", True),
    }
    source_hashes = {case: digest(fixture_root / f"{case}.kicad_sch") for case in cases}
    expected_source_hashes = {
        "collector-control": "bdb0b34256ef9bac90b7fba687abe5998400c29da2f2467cd1a43e8b1029c177",
        "collector-fault": "bb4d7075d2892bf2991a3b840ba1db956cdf6a2f6caba1538ef1381c0d937714",
        "emitter-control": "3f2bcdb733865867bef38ba1fe790518e8aa35225e04117220dcac07e53645f0",
        "emitter-fault": "b987e6f281edc13de3587614cb3bb19ed80bfeeaccde783dcf1492ef598826e1",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("Open-output bias fixture sources differ from their reviewed hashes")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"open-drain-bias-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case in cases:
        fixture = fixture_root / f"{case}.kicad_sch"
        shutil.copyfile(fixture, inputs / fixture.name)
        if digest(inputs / fixture.name) != source_hashes[case]:
            raise ValueError(f"Synthetic {case} fixture changed while preparing native input")
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
        f"for case in {' '.join(cases)}; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
        '      "/fixtures/${case}.kicad_sch"\n'
        "    kicad-cli sch erc --format json --severity-all "
        '      --output "/output/${case}.${run}.erc.json" '
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
        "HOME=/tmp/kicad-open-drain-fixtures",
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
        "open-drain-bias-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "open-drain-bias-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native open-output bias fixture command failed: {command.stderr or command.error}"
        )

    for case, (output_type, bias_description, rail, is_fault) in cases.items():
        is_emitter = output_type == "open_emitter"
        observations: dict[str, NetlistContract] = {}
        normalized_netlist_hashes: dict[str, str] = {}
        normalized_erc_hashes: dict[str, str] = {}
        erc_warning_types: dict[str, tuple[str, ...]] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native open-output {case} export omitted an expected report")
            observed = read_netlist(netlist_path)
            observations[run] = observed
            normalized_netlist = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_netlist_hashes[run] = hashlib.sha256(normalized_netlist).hexdigest()

            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native open-output {case} ERC report version differs from KiCad "
                    f"{config.kicad_version}"
                )
            erc_rows = [
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted(
                            [(detail.description, detail.x, detail.y) for detail in item.items],
                            key=lambda detail: json.dumps(
                                detail,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            ),
                        )
                    ),
                )
                for item in erc.violations
            ]
            erc_rows.sort(
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[run] = hashlib.sha256(normalized_erc).hexdigest()
            erc_errors = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            if erc_errors:
                raise ValueError(
                    f"Native open-output {case} has unexpected ERC errors: {erc_errors}"
                )
            erc_warning_types[run] = tuple(
                sorted({item.type for item in erc.violations if item.severity == "warning"})
            )

        if normalized_netlist_hashes["first"] != normalized_netlist_hashes["repeat"]:
            raise ValueError(f"Native open-output {case} netlists are not repeatable")
        if normalized_erc_hashes["first"] != normalized_erc_hashes["repeat"]:
            raise ValueError(f"Native open-output {case} ERC reports are not repeatable")
        observed = observations["first"]
        expected_types = {"U2.1": output_type, "U1.2": "input"}
        if any(
            observed.pin_electrical_types.get(pin) != value for pin, value in expected_types.items()
        ):
            raise ValueError(f"Native open-output {case} lost exact native pin electrical types")
        expected_functions = {"U2.1": "OPEN_OUTPUT", "U1.2": "INPUT_PEER"}
        if any(
            observed.pin_functions.get(pin) != value for pin, value in expected_functions.items()
        ):
            raise ValueError(f"Native open-output {case} lost exact pin functions")
        expected_nets = {"ALERT_N": {"U2.1", "U1.2", "R1.1"}, rail: {"R1.2"}}
        actual_nets = {net: set(observed.nets.get(net, ())) for net in expected_nets}
        if actual_nets != expected_nets:
            raise ValueError(
                f"Native open-output {case} net assignments differ: "
                f"expected {expected_nets}, observed {actual_nets}"
            )
        expected_dnp = ("R1",) if is_fault else ()
        if observed.dnp_components != expected_dnp:
            raise ValueError(f"Native open-output {case} changed DNP resistor evidence")
        if observed.component_pin_numbers.get("R1") != ("1", "2"):
            raise ValueError(f"Native open-output {case} lost the complete resistor pin inventory")
        expected_erc_warning_types = {
            "footprint_link_issues",
            "isolated_pin_label",
            "lib_symbol_issues",
        }
        for run, warning_types in erc_warning_types.items():
            if set(warning_types) != expected_erc_warning_types:
                raise ValueError(
                    f"Native open-output {case} has unexpected ERC warning types in {run}: "
                    f"{warning_types}"
                )

        report = evaluate(
            f"synthetic-open-output-{case}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-open-output-{case}",
                observed=observed,
                netlist_sha256=digest(output / f"{case}.first.netlist.xml"),
            ),
            DesignLintPolicy(),
        )
        matching = tuple(
            item
            for item in report.findings
            if item.rule_id
            == (
                "signal.open_emitter_input_without_visible_bias"
                if is_emitter
                else "signal.open_collector_input_without_visible_bias"
            )
        )
        expected_status = "REVIEW" if is_fault else "PASS"
        expected_evidence = {
            "net": ("ALERT_N",),
            "expected_bias": (bias_description,),
            "open_output_pins": ("U2.1",),
            "input_pins": ("U1.2",),
            "visible_resistors_on_signal_net": (),
        }
        if (
            report.status != expected_status
            or len(report.findings) != len(matching)
            or len(matching) != (1 if is_fault else 0)
            or (is_fault and matching[0].mode != "review")
            or (is_fault and dict(matching[0].evidence) != expected_evidence)
        ):
            raise ValueError(f"Native open-output {case} no longer matches its lint control/fault")
        repeated = evaluate(
            f"synthetic-open-output-{case}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-open-output-{case}",
                observed=observations["repeat"],
                netlist_sha256=digest(output / f"{case}.repeat.netlist.xml"),
            ),
            DesignLintPolicy(),
        )

        def finding_key(finding: DesignLintFinding) -> tuple[object, ...]:
            return finding.fingerprint, finding.rule_id, finding.mode, finding.evidence

        if tuple(map(finding_key, report.findings)) != tuple(map(finding_key, repeated.findings)):
            raise ValueError(f"Native open-output {case} lint report is not repeatable")

        log.event(
            f"open-drain-bias-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_netlist_hashes["first"],
            repeat_normalized_netlist_sha256=normalized_netlist_hashes["repeat"],
            normalized_erc_sha256=normalized_erc_hashes["first"],
            repeat_normalized_erc_sha256=normalized_erc_hashes["repeat"],
            lint_status=report.status,
            findings=";".join(item.rule_id for item in matching) or "none",
            expected_bias=bias_description,
            bias_rail=rail,
            open_output_type=output_type,
            input_type="input",
            open_output_pin="U2.1",
            input_pin="U1.2",
            signal_net="ALERT_N",
            net_assignments=";".join(
                f"{net}={','.join(sorted(pins, key=str.casefold))}"
                for net, pins in sorted(expected_nets.items())
            ),
            dnp_resistor="R1" if is_fault else "none",
            erc_errors="0",
            erc_warning_types=";".join(erc_warning_types["first"]) or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_erc_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "open-drain-bias-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )


def usb_c_port_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify USB-C CC pin-function coverage from repeated pinned native exports."""
    import hashlib
    import os

    from .hwrepo.bus_heuristics import usb_c_vbus_capacitance_check
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        AnalysisNotApplicable,
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        NetlistContract,
        UsbCAnalysis,
        UsbCcLineRequirement,
        UsbCcResistorAttachment,
        UsbCNetPinAssignment,
        UsbCPortRequirement,
        UsbCVbusCapacitanceRequirement,
        UsbCVbusCapacitorRequirement,
    )
    from .hwrepo.usb_c_ports import UsbCPortRosterContext
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"USB-C port fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    fixtures = {
        "connector": fixture_root / "usb-c-port-native/connector.kicad_sch",
        "source-rp-control": fixture_root / "cohort-usb-c-roles/source-rp-control.kicad_sch",
        "sink-rd-control": fixture_root / "cohort-usb-c-roles/sink-rd-control.kicad_sch",
        "vbus-capacitance-control": (
            fixture_root / "usb-c-vbus-capacitance-native/control.kicad_sch"
        ),
        "vbus-capacitance-fault": (fixture_root / "usb-c-vbus-capacitance-native/fault.kicad_sch"),
    }
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    scratch = Path(tempfile.mkdtemp(prefix=f"usb-c-port-{project}-", dir=log.directory.resolve()))
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        source = inputs / f"{case}.kicad_sch"
        shutil.copyfile(fixture, source)
        if digest(source) != source_hashes[case]:
            raise ValueError(f"Synthetic USB-C {case} fixture changed while preparing native input")
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
        "for case in connector source-rp-control sink-rd-control "
        "vbus-capacitance-control vbus-capacitance-fault; do\n"
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
        "HOME=/tmp/kicad-usb-c-fixtures",
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
        "usb-c-port-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "usb-c-port-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native USB-C fixture command failed: {command.stderr or command.error}")
    log.event(
        "usb-c-port-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_sha256=source_hashes["connector"],
        fixture_source_sha256s=";".join(f"{case}:{source_hashes[case]}" for case in fixtures),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    if any(
        digest(fixture) != source_hashes[case]
        or digest(inputs / f"{case}.kicad_sch") != source_hashes[case]
        for case, fixture in fixtures.items()
    ):
        raise ValueError("Synthetic USB-C fixture source changed during native export")

    contracts: dict[str, dict[str, NetlistContract]] = {}
    netlist_hashes: dict[str, dict[str, str]] = {}
    normalized_hashes: dict[str, dict[str, str]] = {}
    for fixture_case in fixtures:
        contracts[fixture_case] = {}
        netlist_hashes[fixture_case] = {}
        normalized_hashes[fixture_case] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{fixture_case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native USB-C fixture omitted {netlist_path.name}")
            netlist_hashes[fixture_case][run] = digest(netlist_path)
            parsed = read_netlist(netlist_path)
            contracts[fixture_case][run] = parsed
            normalized = json.dumps(
                parsed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[fixture_case][run] = hashlib.sha256(normalized).hexdigest()
        if normalized_hashes[fixture_case]["first"] != normalized_hashes[fixture_case]["repeat"]:
            raise ValueError(
                f"Native USB-C {fixture_case} exports differ after normalization to the typed netlist"
            )

    observed = contracts["connector"]["first"]
    expected_functions = {"J1.4": "CC1", "J1.5": "CC2"}
    if observed.pin_functions != expected_functions:
        raise ValueError(
            "Native netlist no longer preserves exact USB-C CC pin functions: "
            f"{observed.pin_functions}"
        )
    if observed.component_symbols != {"J1": "Synthetic:TypeCConnector"}:
        raise ValueError("Native netlist changed the synthetic USB-C connector identity")

    expected_control_symbols = {
        "source-rp-control": "Connector:USB_C_Receptacle",
        "sink-rd-control": "Connector:USB_C_Receptacle",
    }
    for case, expected_symbol in expected_control_symbols.items():
        control = contracts[case]["first"]
        if control.pin_functions != expected_functions:
            raise ValueError(
                f"Native USB-C {case} fixture lost its CC pin functions: {control.pin_functions}"
            )
        if control.component_symbols.get("J1") != expected_symbol:
            raise ValueError(f"Native USB-C {case} fixture changed connector symbol identity")
    source_control = contracts["source-rp-control"]["first"]
    if (
        set(source_control.components) != {"J1", "R1", "R2"}
        or source_control.dnp_components
        or source_control.component_symbols.get("R1") != "Device:R"
        or source_control.component_symbols.get("R2") != "Device:R"
        or source_control.components.get("R1") is None
        or source_control.components["R1"].value != "56k"
        or source_control.components.get("R2") is None
        or source_control.components["R2"].value != "56k"
        or set(source_control.nets.get("CC1_NET", ())) != {"J1.4", "R1.1"}
        or set(source_control.nets.get("CC2_NET", ())) != {"J1.5", "R2.1"}
        or set(source_control.nets.get("+5V", ())) != {"R1.2", "R2.2"}
    ):
        raise ValueError("Native USB-C source control no longer has its synthetic 56 kΩ Rp paths")
    sink_control = contracts["sink-rd-control"]["first"]
    if (
        set(sink_control.components) != {"J1", "R1", "R2"}
        or sink_control.dnp_components
        or sink_control.component_symbols.get("R1") != "Device:R"
        or sink_control.component_symbols.get("R2") != "Device:R"
        or sink_control.components.get("R1") is None
        or sink_control.components["R1"].value != "5.1k"
        or sink_control.components.get("R2") is None
        or sink_control.components["R2"].value != "5.1k"
        or set(sink_control.nets.get("CC1_NET", ())) != {"J1.4", "R1.1"}
        or set(sink_control.nets.get("CC2_NET", ())) != {"J1.5", "R2.1"}
        or set(sink_control.nets.get("GND", ())) != {"R1.2", "R2.2"}
    ):
        raise ValueError("Native USB-C sink control no longer has its synthetic 5.1 kΩ Rd paths")

    capacitance_requirement = UsbCVbusCapacitanceRequirement(
        basis="Synthetic fixture contract with an explicit nominal capacitance window",
        minimum_nf=4500,
        maximum_nf=5000,
        capacitors=(
            UsbCVbusCapacitorRequirement(
                reference="C1",
                symbol="Device:C",
                footprint="Synthetic:C_0603",
                pins=(
                    UsbCNetPinAssignment(pin="C1.1", net="VBUS_PORT"),
                    UsbCNetPinAssignment(pin="C1.2", net="GND"),
                ),
            ),
        ),
    )
    expected_capacitance = {
        "vbus-capacitance-control": ("PASS", 4700.0, "4.7uF"),
        "vbus-capacitance-fault": ("FAIL", 2200.0, "2.2uF"),
    }
    for case, (expected_status, expected_nf, expected_value) in expected_capacitance.items():
        observed_capacitance = contracts[case]["first"]
        if (
            set(observed_capacitance.components) != {"C1"}
            or observed_capacitance.component_symbols != {"C1": "Device:C"}
            or observed_capacitance.components["C1"].value != expected_value
            or observed_capacitance.components["C1"].footprint != "Synthetic:C_0603"
            or set(observed_capacitance.component_pin_numbers.get("C1", ())) != {"1", "2"}
            or set(observed_capacitance.nets.get("VBUS_PORT", ())) != {"C1.1"}
            or set(observed_capacitance.nets.get("GND", ())) != {"C1.2"}
        ):
            raise ValueError(
                f"Native USB-C {case} fixture changed its exact synthetic capacitor map"
            )
        capacitance_check = usb_c_vbus_capacitance_check(
            capacitance_requirement,
            vbus_net="VBUS_PORT",
            ground_net="GND",
            observed=observed_capacitance,
            check_id="usb-c/native-port/vbus-capacitance",
        )
        observed_nf = capacitance_check.observed
        if (
            capacitance_check.status != expected_status
            or observed_nf is None
            or observed_nf != expected_nf
        ):
            raise ValueError(
                f"Native USB-C {case} capacitance result changed: "
                f"{capacitance_check.status}/{capacitance_check.observed}"
            )
        log.event(
            f"usb-c-port-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            fixture_case=case,
            source_sha256=source_hashes[case],
            netlist_sha256=netlist_hashes[case]["first"],
            repeat_netlist_sha256=netlist_hashes[case]["repeat"],
            normalized_netlist_sha256=normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=normalized_hashes[case]["repeat"],
            repeatable=str(
                normalized_hashes[case]["first"] == normalized_hashes[case]["repeat"]
            ).lower(),
            check_status=capacitance_check.status,
            observed_nf=observed_nf,
            expected_check_status=expected_status,
            detail=capacitance_check.detail,
        )

    analysis = UsbCAnalysis(
        basis="Synthetic exact native netlist comparison for USB-C roster fault/control coverage",
        ports=(
            UsbCPortRequirement(
                id="native-port",
                basis="Synthetic USB-C connector role map control",
                connector="J1",
                role="source",
                cc1=UsbCcLineRequirement(
                    connector_pin="J1.4",
                    net="CC1_NET",
                    attachment=UsbCcResistorAttachment(
                        kind="resistor",
                        behavior="rp",
                        reference="R1",
                        rail_net="+5V",
                        minimum_ohms=50_000,
                        maximum_ohms=60_000,
                    ),
                ),
                cc2=UsbCcLineRequirement(
                    connector_pin="J1.5",
                    net="CC2_NET",
                    attachment=UsbCcResistorAttachment(
                        kind="resistor",
                        behavior="rp",
                        reference="R2",
                        rail_net="+5V",
                        minimum_ohms=50_000,
                        maximum_ohms=60_000,
                    ),
                ),
                vbus_net="VBUS_PORT",
                vbus_pins=(
                    UsbCNetPinAssignment(pin="J1.1", net="VBUS_PORT"),
                    UsbCNetPinAssignment(pin="U1.1", net="VBUS_SYSTEM"),
                ),
                ground_net="GND",
                ground_pins=("J1.2", "U1.2"),
                vbus_capacitance=AnalysisNotApplicable(
                    mode="not_applicable",
                    reason="Native roster fixture does not assess port-side capacitance.",
                ),
                source_rail="+5V",
                protection=AnalysisNotApplicable(
                    mode="not_applicable",
                    reason="Native roster fixture tests membership only.",
                ),
            ),
        ),
    )
    reports: dict[str, DesignLintReport] = {}
    for case, context in (
        ("unmapped", UsbCPortRosterContext(state="not_configured")),
        ("mapped", UsbCPortRosterContext(state="required", analysis=analysis)),
    ):
        project_id = f"synthetic-usb-c-port-{case}"
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=project_id,
            observed=observed,
            netlist_sha256=netlist_hashes["connector"]["first"],
        )
        reports[case] = evaluate(
            project_id,
            coach,
            DesignLintPolicy(),
            usb_c_port_roster=context,
        )

    unmapped = reports["unmapped"]
    cc_findings = tuple(
        item for item in unmapped.findings if item.rule_id == "bus.usb_c_unreviewed_port"
    )
    if unmapped.status != "REVIEW" or tuple(item.subject for item in cc_findings) != (
        "J1: USB-C role-map coverage",
    ):
        raise ValueError("Unmapped native USB-C port no longer produces the expected review hint")
    mapped = reports["mapped"]
    if mapped.status != "PASS" or mapped.findings:
        raise ValueError("The exact USB-C role-map control no longer suppresses review findings")

    for case in ("source-rp-control", "sink-rd-control"):
        control = contracts[case]["first"]
        project_id = f"synthetic-usb-c-port-{case}-unmapped"
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=project_id,
            observed=control,
            netlist_sha256=netlist_hashes[case]["first"],
        )
        report = evaluate(
            project_id,
            coach,
            DesignLintPolicy(),
            usb_c_port_roster=UsbCPortRosterContext(state="not_configured"),
        )
        findings = tuple(
            item for item in report.findings if item.rule_id == "bus.usb_c_unreviewed_port"
        )
        if report.status != "REVIEW" or tuple(item.subject for item in findings) != (
            "J1: USB-C role-map coverage",
        ):
            raise ValueError(
                f"Unmapped native USB-C {case} no longer produces the expected role-map prompt"
            )
        reports[case] = report

    for case, report in reports.items():
        fixture_case = "connector" if case in {"unmapped", "mapped"} else case
        observed_case = contracts[fixture_case]["first"]
        log.event(
            f"usb-c-port-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            fixture_case=fixture_case,
            source_sha256=source_hashes[fixture_case],
            netlist_sha256=netlist_hashes[fixture_case]["first"],
            repeat_netlist_sha256=netlist_hashes[fixture_case]["repeat"],
            normalized_netlist_sha256=normalized_hashes[fixture_case]["first"],
            repeat_normalized_netlist_sha256=normalized_hashes[fixture_case]["repeat"],
            lint_status=report.status,
            findings=";".join(item.subject for item in report.findings) or "none",
            cc_pin_functions=";".join(
                f"{pin}={name}" for pin, name in sorted(observed_case.pin_functions.items())
            ),
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )


def usb_data_path_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Compare mapped USB PHY topologies with repeated, pinned native netlist exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        ReferenceBondRequirement,
        UsbDataInterfaceRequirement,
        UsbDataPathLineRequirement,
        UsbDataPathMap,
        UsbDataSeriesResistorRequirement,
        UsbReferencePinRequirement,
    )
    from .hwrepo.usb_data_paths import usb_data_path_mismatches
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"USB data-path fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    cases = {
        "integrated-direct": fixture_root / "usb-data-path-native/integrated-phy-direct.kicad_sch",
        "external-series": fixture_root
        / "usb-data-path-native/external-phy-series-control.kicad_sch",
        "external-series-reference-bond-control": fixture_root
        / "usb-data-path-native/external-phy-series-reference-bond-control.kicad_sch",
        "external-series-reference-fault": fixture_root
        / "usb-data-path-native/external-phy-series-reference-fault.kicad_sch",
        "external-bypass": fixture_root
        / "usb-data-path-native/external-phy-direct-bypass-fault.kicad_sch",
        "peer-reference-fault": fixture_root / "usb-peer-reference-native/fault.kicad_sch",
        "peer-reference-control": fixture_root / "usb-peer-reference-native/control.kicad_sch",
        "usb-c-peer-reference-fault": fixture_root / "usb-c-peer-reference-native/fault.kicad_sch",
        "usb-c-peer-reference-control": fixture_root
        / "usb-c-peer-reference-native/control.kicad_sch",
        "usb-multiport-peer-reference-fault": fixture_root
        / "usb-multiport-peer-reference-native/fault.kicad_sch",
        "usb-multiport-peer-reference-control": fixture_root
        / "usb-multiport-peer-reference-native/control.kicad_sch",
    }
    source_hashes = {case: digest(path) for case, path in cases.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"usb-data-path-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source_path in cases.items():
        shutil.copyfile(source_path, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} USB fixture changed while preparing native input")
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
    for case in cases:
        export_command = (
            f"for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{case}.kicad_sch"; done\n'
        )
        source_lines.append(export_command)
    script = "".join(source_lines)
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
        "HOME=/tmp/kicad-usb-fixtures",
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
        "usb-data-path-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "usb-data-path-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native USB fixture command failed: {command.stderr or command.error}")
    log.event(
        "usb-data-path-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    def series_line(
        line: Literal["D+", "D-"], connector_net: str, phy_net: str, resistor: str
    ) -> UsbDataPathLineRequirement:
        return UsbDataPathLineRequirement(
            line=line,
            connector_pin=f"J1.{1 if line == 'D+' else 2}",
            phy_pin=f"U1.{1 if line == 'D+' else 2}",
            connector_net=connector_net,
            phy_net=phy_net,
            topology="series_resistor",
            series_resistor=UsbDataSeriesResistorRequirement(
                reference=resistor,
                expected_symbol="Device:R",
                expected_footprint="Synthetic:0603",
                minimum_ohms=27,
                maximum_ohms=27,
            ),
        )

    series_map = UsbDataPathMap(
        basis="Synthetic source-backed TUSB2036 series-resistor requirement",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="external-usb-phy",
                basis="TI TUSB2036 synthetic fixture requires 27 ohm series resistors",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:TUSB2036",
                expected_phy_footprint="Synthetic:QFN",
                positive=series_line("D+", "USB_D+", "USB_DP_PHY", "R1"),
                negative=series_line("D-", "USB_D-", "USB_DM_PHY", "R2"),
            ),
        ),
    )
    bonded_reference_map = series_map.model_copy(
        update={
            "interfaces": (
                series_map.interfaces[0].model_copy(
                    update={
                        "connector_reference_pins": (
                            UsbReferencePinRequirement(pin="J1.4", net="USB_GND"),
                        ),
                        "phy_reference_pins": (
                            UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),
                        ),
                        "reference_policy": "bonded",
                        "reference_bond": ReferenceBondRequirement(
                            reference="R3",
                            expected_symbol="Device:R",
                            expected_footprint="Synthetic:0603",
                            expected_value="0R",
                            side_a_pin="R3.1",
                            side_b_pin="R3.2",
                            side_a_net="USB_GND",
                            side_b_net="BOARD_GND",
                        ),
                    }
                ),
            )
        }
    )
    direct_map = UsbDataPathMap(
        basis="Synthetic source-backed integrated STM32 full-speed PHY disposition",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="integrated-usb-phy",
                basis="ST AN4879 synthetic fixture selects the integrated direct PHY path",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:STM32F103C8T6",
                expected_phy_footprint="Synthetic:QFN",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.1",
                    phy_pin="U1.1",
                    connector_net="USB_D+",
                    phy_net="USB_D+",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.2",
                    phy_pin="U1.2",
                    connector_net="USB_D-",
                    phy_net="USB_D-",
                    topology="direct",
                ),
            ),
        ),
    )
    usb_c_direct_map = UsbDataPathMap(
        basis="Synthetic USB-C duplicate-contact direct-path fixture",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-c-direct-phy",
                basis="Synthetic USB-C D+/D- contacts share direct nets with one integrated PHY",
                connector_reference="J1",
                expected_connector_symbol="Synthetic:UsbCConnector",
                expected_connector_footprint="Synthetic:USB-C",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbPhy",
                expected_phy_footprint="Synthetic:QFN",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.A6",
                    connector_parallel_pins=("J1.B6",),
                    phy_pin="U1.1",
                    connector_net="USB_D+",
                    phy_net="USB_D+",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.A7",
                    connector_parallel_pins=("J1.B7",),
                    phy_pin="U1.2",
                    connector_net="USB_D-",
                    phy_net="USB_D-",
                    topology="direct",
                ),
            ),
        ),
    )
    multiport_map = UsbDataPathMap(
        basis="Synthetic exact mappings for two USB hub ports",
        interfaces=tuple(
            UsbDataInterfaceRequirement(
                id=f"usb-port-{port_group}",
                basis=f"Synthetic exact native path for hub port {port_group}",
                connector_reference=connector,
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbHub",
                expected_phy_footprint="Synthetic:QFN",
                data_port_group=port_group,
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin=f"{connector}.1",
                    phy_pin=f"U1.{positive_pin}",
                    connector_net=f"USB{port_group}_DP",
                    phy_net=f"USB{port_group}_DP",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin=f"{connector}.2",
                    phy_pin=f"U1.{negative_pin}",
                    connector_net=f"USB{port_group}_DM",
                    phy_net=f"USB{port_group}_DM",
                    topology="direct",
                ),
            )
            for connector, port_group, positive_pin, negative_pin in (
                ("J1", "1", "1", "2"),
                ("J2", "2", "4", "5"),
            )
        ),
    )
    requirements = {
        "integrated-direct": direct_map,
        "external-series": series_map,
        "external-series-reference-bond-control": bonded_reference_map,
        "external-series-reference-fault": series_map,
        "external-bypass": series_map,
        "peer-reference-fault": direct_map,
        "peer-reference-control": direct_map,
        "usb-c-peer-reference-fault": usb_c_direct_map,
        "usb-c-peer-reference-control": usb_c_direct_map,
        "usb-multiport-peer-reference-fault": multiport_map,
        "usb-multiport-peer-reference-control": multiport_map,
    }

    normalized_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native USB fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            expected_assignments = (
                {"U1.2": ("VOUT",), "U2.2": ()}
                if case == "fault"
                else {"U1.2": ("VOUT_A",), "U2.2": ("VOUT_B",)}
            )
            actual_assignments = {
                pin: tuple(sorted(net for net, pins in observed.nets.items() if pin in pins))
                for pin in expected_assignments
            }
            if actual_assignments != expected_assignments:
                raise ValueError(
                    f"Native {case} expected schematic output assignments "
                    f"{expected_assignments}, observed {actual_assignments}"
                )
            if (
                observed.component_symbols.get("U1") != "Synthetic:PowerModule"
                or observed.component_symbols.get("U2") != "Synthetic:PowerModule"
                or observed.component_pin_numbers.get("U1") != ("1", "2")
                or observed.component_pin_numbers.get("U2") != ("1", "2")
                or observed.pin_electrical_types.get("U1.2") != "power_out"
                or observed.pin_electrical_types.get("U2.2") != "power_out"
            ):
                raise ValueError(
                    f"Native {case} export omitted the exact peer symbol, pin inventory, "
                    "or native power_out pin types"
                )
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            mismatches = usb_data_path_mismatches(requirements[case], observed)
            if case == "external-bypass":
                subjects = {item.line for item in mismatches}
                if subjects != {"D+", "D-"}:
                    raise ValueError(
                        f"Native external-PHY bypass should mismatch both USB data lines; "
                        f"observed {sorted(subjects)}"
                    )
            elif mismatches:
                raise ValueError(
                    f"Native {case} USB control mismatched the authored topology: {mismatches}"
                )

            project_id = f"synthetic-usb-data-path-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(
                project_id,
                coach,
                DesignLintPolicy(usb_data_path_map=requirements[case]),
            )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native USB exports differ after normalization to parsed netlist contracts"
        )

    fault = reports[("external-bypass", "first")]
    fault_findings = tuple(
        item for item in fault.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    if fault.status != "REVIEW":
        raise ValueError("Native external-PHY bypass did not produce the expected REVIEW")
    if {item.subject for item in fault_findings} != {
        "external-usb-phy: USB D+ path",
        "external-usb-phy: USB D- path",
    }:
        raise ValueError("Native external-PHY bypass did not emit one path finding per data line")
    for case in (
        "integrated-direct",
        "external-series",
        "external-series-reference-bond-control",
    ):
        if any(
            item.rule_id == "bus.usb_data_path_mismatch"
            for item in reports[(case, "first")].findings
        ):
            raise ValueError(f"Native {case} control produced a USB data-path finding")
    if any(
        item.rule_id == "bus.usb_peer_reference_review"
        for item in reports[("external-series", "first")].findings
    ):
        raise ValueError("Native common-reference series USB control produced a reference review")
    if any(
        item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
        for item in reports[("external-series-reference-bond-control", "first")].findings
    ):
        raise ValueError("Native exact bonded-reference USB control produced a reference finding")

    series_peer_faults = tuple(
        item
        for item in reports[("external-series-reference-fault", "first")].findings
        if item.rule_id == "bus.usb_peer_reference_review"
    )
    if len(series_peer_faults) != 1:
        raise ValueError(
            "Native split-reference USB peer with series resistors should produce one review"
        )
    series_peer_evidence = series_peer_faults[0].evidence
    if series_peer_evidence.get("USB_D+_series_resistor") != (
        "R1 (Device:R, 27R; R1.1=USB_D+, R1.2=USB_DP_PHY)",
    ) or series_peer_evidence.get("USB_D-_series_resistor") != (
        "R2 (Device:R, 27R; R2.1=USB_D-, R2.2=USB_DM_PHY)",
    ):
        raise ValueError(
            "Native series-resistor reference review omitted exact resistor pin/net evidence"
        )
    if series_peer_evidence.get("connector_reference_pin_assignments") != (
        "J1.4 (GND, passive)=USB_GND",
    ) or series_peer_evidence.get("phy_reference_pin_assignments") != (
        "U1.3 (AGND, power_in)=PHY_GND",
    ):
        raise ValueError("Native series-resistor review omitted split-reference assignments")

    peer_reference_faults = tuple(
        item
        for item in reports[("peer-reference-fault", "first")].findings
        if item.rule_id == "bus.usb_peer_reference_review"
    )
    if len(peer_reference_faults) != 1:
        raise ValueError(
            "Native split-reference USB peer should produce exactly one bounded review"
        )
    if peer_reference_faults[0].evidence.get("connector_reference_pin_assignments") != (
        "J1.4 (GND, passive)=USB_GND",
    ) or peer_reference_faults[0].evidence.get("phy_reference_pin_assignments") != (
        "U1.3 (AGND, power_in)=PHY_GND",
    ):
        raise ValueError("Native USB peer review did not preserve exact reference-pin evidence")
    if any(
        item.rule_id == "bus.usb_peer_reference_review"
        for item in reports[("peer-reference-control", "first")].findings
    ):
        raise ValueError("Native common-reference USB peer control produced a review")

    usb_c_peer_faults = tuple(
        item
        for item in reports[("usb-c-peer-reference-fault", "first")].findings
        if item.rule_id == "bus.usb_peer_reference_review"
    )
    if len(usb_c_peer_faults) != 1:
        raise ValueError("Native USB-C split-reference peer should produce exactly one review")
    usb_c_peer_evidence = usb_c_peer_faults[0].evidence
    if usb_c_peer_evidence.get("USB_D+_link") != ("J1.A6, J1.B6 / U1.1=USB_D+",) or (
        usb_c_peer_evidence.get("USB_D-_link") != ("J1.A7, J1.B7 / U1.2=USB_D-",)
    ):
        raise ValueError("Native USB-C review did not preserve duplicate-contact pin evidence")
    if usb_c_peer_evidence.get("USB_D+_shunt_branches") != (
        "D1.2 (Synthetic:TVS) to D1.1=USB_GND",
    ) or usb_c_peer_evidence.get("USB_D-_shunt_branches") != (
        "D2.2 (Synthetic:TVS) to D2.1=USB_GND",
    ):
        raise ValueError("Native USB-C review did not preserve two-pin shunt evidence")
    if any(
        item.rule_id == "bus.usb_peer_reference_review"
        for item in reports[("usb-c-peer-reference-control", "first")].findings
    ):
        raise ValueError("Native common-reference USB-C peer control produced a review")

    multiport_faults = tuple(
        item
        for item in reports[("usb-multiport-peer-reference-fault", "first")].findings
        if item.rule_id == "bus.usb_peer_reference_review"
    )
    if tuple((item.subject, item.evidence.get("USB_port_group")) for item in multiport_faults) != (
        ("J1 / U1: USB reference-domain review (port 1)", ("1",)),
        ("J2 / U1: USB reference-domain review (port 2)", ("2",)),
    ):
        raise ValueError("Native multiport USB fault did not localize both exact hub port groups")
    if any(
        item.rule_id == "bus.usb_peer_reference_review"
        for item in reports[("usb-multiport-peer-reference-control", "first")].findings
    ):
        raise ValueError("Native common-reference multiport USB control produced a review")

    for case in cases:
        report = reports[(case, "first")]
        log.event(
            f"usb-data-path-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=report.status,
            usb_path_findings=";".join(
                item.subject
                for item in report.findings
                if item.rule_id == "bus.usb_data_path_mismatch"
            )
            or "none",
            usb_reference_findings=";".join(
                item.subject
                for item in report.findings
                if item.rule_id == "bus.usb_peer_reference_review"
            )
            or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(filename) != source_hashes[case]
        or digest(inputs / f"{case}.kicad_sch") != source_hashes[case]
        for case, filename in cases.items()
    ):
        raise ValueError("Synthetic USB fixture source changed during native export")


def power_path_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Compare mapped and heuristic power paths with repeated pinned exports and ERC."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        PowerPathElementRequirement,
        PowerPathEndpointRequirement,
        PowerPathMap,
        PowerPathRequirement,
    )
    from .hwrepo.power_paths import PowerPathMismatch, power_path_mismatches
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Power-path fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/power-path-native"
    )
    cases = {
        "control": "control.kicad_sch",
        "fault": "fault.kicad_sch",
        "diode-control": "diode-control.kicad_sch",
        "diode-reverse-fault": "diode-reverse-fault.kicad_sch",
        "schottky-diode-control": "schottky-diode-control.kicad_sch",
        "bridged-jumper-control": "bridged-jumper-control.kicad_sch",
        "open-jumper-fault": "open-jumper-fault.kicad_sch",
        "bridged-three-pin12-control": "bridged-three-pin12-control.kicad_sch",
        "bridged-three-pin123-control": "bridged-three-pin123-control.kicad_sch",
        "bridged-three-pin12-unbridged-terminal-fault": (
            "bridged-three-pin12-unbridged-terminal-fault.kicad_sch"
        ),
        "isolated-control": "isolated-control.kicad_sch",
        "custom-capacitor-control": "custom-capacitor-control.kicad_sch",
        "custom-capacitor-fault": "custom-capacitor-fault.kicad_sch",
        "opaque-capacitor-fault": "opaque-capacitor-fault.kicad_sch",
        "external-source-control": "external-source-control.kicad_sch",
        "dnp-external-source-fault": "dnp-external-source-fault.kicad_sch",
        "alternate-source-control": "alternate-source-control.kicad_sch",
        "both-sources-dnp-fault": "both-sources-dnp-fault.kicad_sch",
    }
    source_hashes = {case: digest(fixture_root / filename) for case, filename in cases.items()}
    scratch = Path(tempfile.mkdtemp(prefix=f"power-path-{project}-", dir=log.directory.resolve()))
    inputs = scratch / "input"
    inputs.mkdir()
    for case, filename in cases.items():
        shutil.copyfile(fixture_root / filename, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} power-path fixture changed during native input")
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
        "for case in control fault diode-control diode-reverse-fault schottky-diode-control "
        "bridged-jumper-control open-jumper-fault bridged-three-pin12-control "
        "bridged-three-pin123-control bridged-three-pin12-unbridged-terminal-fault "
        "isolated-control custom-capacitor-control "
        "custom-capacitor-fault opaque-capacitor-fault external-source-control "
        "dnp-external-source-fault alternate-source-control both-sources-dnp-fault; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
        '      "/fixtures/${case}.kicad_sch"\n'
        "    kicad-cli sch erc --format json --severity-all "
        '      --output "/output/${case}.${run}.erc.json" '
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
        "HOME=/tmp/kicad-power-path-fixtures",
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
        "power-path-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "power-path-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native power-path fixture command failed: {command.stderr or command.error}"
        )

    path_map = PowerPathMap(
        basis="Synthetic reviewed source-to-load requirement",
        paths=(
            PowerPathRequirement(
                id="source-through-bead-to-load",
                basis="Synthetic schematic requires the fitted ferrite bead in the path",
                start=PowerPathEndpointRequirement(
                    reference="U1",
                    pin="U1.1",
                    symbol="Synthetic:PowerSource",
                    footprint="Synthetic:PowerSource",
                    net="VIN",
                ),
                end=PowerPathEndpointRequirement(
                    reference="U2",
                    pin="U2.1",
                    symbol="Synthetic:PowerLoad",
                    footprint="Synthetic:PowerLoad",
                    net="VLOAD",
                ),
                elements=(
                    PowerPathElementRequirement(
                        reference="FB1",
                        symbol="Device:FerriteBead",
                        footprint="Synthetic:0603",
                        side_a_pin="FB1.1",
                        side_b_pin="FB1.2",
                        side_a_net="VIN",
                        side_b_net="VLOAD",
                    ),
                ),
            ),
        ),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    normalized_erc_hashes: dict[tuple[str, str], str] = {}
    raw_erc_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    unmapped_reports: dict[tuple[str, str], DesignLintReport] = {}
    mismatches_by_case: dict[tuple[str, str], tuple[PowerPathMismatch, ...]] = {}
    erc_errors_by_case: dict[tuple[str, str], tuple[str, ...]] = {}
    return_nets_by_case: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native power-path fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            erc_path = output / f"{case}.{run}.erc.json"
            if not erc_path.is_file():
                raise ValueError(f"Native power-path fixture omitted {erc_path.name}")
            raw_erc_hashes[(case, run)] = digest(erc_path)
            erc_report = read_kicad_erc_report(erc_path)
            if erc_report.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native {case} ERC report version differs from KiCad {config.kicad_version}"
                )
            erc_rows = [
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted(
                            [(detail.description, detail.x, detail.y) for detail in item.items],
                            key=lambda detail: json.dumps(
                                detail,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            ),
                        )
                    ),
                )
                for item in erc_report.violations
            ]
            erc_rows.sort(
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc_report.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[(case, run)] = hashlib.sha256(normalized_erc).hexdigest()
            erc_errors = tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "error")
            )
            erc_errors_by_case[(case, run)] = erc_errors
            if erc_errors:
                raise ValueError(
                    f"Native power-path {case} has unexpected ERC errors: {erc_errors}"
                )
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            case_path_map = (
                None
                if case
                in {
                    "external-source-control",
                    "dnp-external-source-fault",
                    "alternate-source-control",
                    "both-sources-dnp-fault",
                    "diode-control",
                    "diode-reverse-fault",
                    "schottky-diode-control",
                    "bridged-jumper-control",
                    "open-jumper-fault",
                    "bridged-three-pin12-control",
                    "bridged-three-pin123-control",
                    "bridged-three-pin12-unbridged-terminal-fault",
                }
                else path_map
            )
            mismatches = (
                power_path_mismatches(case_path_map, observed) if case_path_map is not None else ()
            )
            if case in {"diode-control", "diode-reverse-fault", "schottky-diode-control"}:
                expected_source_pin, expected_load_pin = (
                    ("D1.1", "D1.2") if case == "diode-reverse-fault" else ("D1.2", "D1.1")
                )
                expected_symbol = (
                    "Device:D_Schottky" if case == "schottky-diode-control" else "Device:D"
                )
                if (
                    observed.component_symbols.get("D1") != expected_symbol
                    or observed.component_pin_numbers.get("D1") != ("1", "2")
                    or observed.pin_functions.get("D1.1") != "K"
                    or observed.pin_functions.get("D1.2") != "A"
                    or expected_source_pin not in observed.nets.get("VIN", ())
                    or expected_load_pin not in observed.nets.get("VLOAD", ())
                ):
                    raise ValueError(
                        f"Native {case} does not preserve the exact diode identity, pin roles, "
                        "and source/load assignments"
                    )
            if case in {"bridged-jumper-control", "open-jumper-fault"}:
                expected_symbol = (
                    "Jumper:SolderJumper_2_Open"
                    if case == "open-jumper-fault"
                    else "Jumper:SolderJumper_2_Bridged"
                )
                if (
                    observed.component_symbols.get("JP1") != expected_symbol
                    or observed.component_pin_numbers.get("JP1") != ("1", "2")
                    or observed.pin_functions.get("JP1.1") != "A"
                    or observed.pin_functions.get("JP1.2") != "B"
                    or "JP1.1" not in observed.nets.get("VIN", ())
                    or "JP1.2" not in observed.nets.get("VLOAD", ())
                ):
                    raise ValueError(
                        f"Native {case} does not preserve exact solder-jumper identity, "
                        "pin roles, and source/load assignments"
                    )
            if case in {
                "bridged-three-pin12-control",
                "bridged-three-pin123-control",
                "bridged-three-pin12-unbridged-terminal-fault",
            }:
                expected_symbol = (
                    "Jumper:SolderJumper_3_Bridged123"
                    if case == "bridged-three-pin123-control"
                    else "Jumper:SolderJumper_3_Bridged12"
                )
                expected_load_pin = "JP1.2" if case == "bridged-three-pin12-control" else "JP1.3"
                expected_spare_pin = "JP1.3" if case == "bridged-three-pin12-control" else "JP1.2"
                expected_spare_net = (
                    "JP_UNUSED_3" if case == "bridged-three-pin12-control" else "JP_UNUSED_2"
                )
                if (
                    observed.component_symbols.get("JP1") != expected_symbol
                    or observed.component_pin_numbers.get("JP1") != ("1", "2", "3")
                    or observed.pin_functions.get("JP1.1") != "A"
                    or observed.pin_functions.get("JP1.2") != "C"
                    or observed.pin_functions.get("JP1.3") != "B"
                    or "JP1.1" not in observed.nets.get("VIN", ())
                    or expected_load_pin not in observed.nets.get("VLOAD", ())
                    or expected_spare_pin not in observed.nets.get(expected_spare_net, ())
                    or expected_spare_pin in observed.nets.get("VIN", ())
                    or expected_spare_pin in observed.nets.get("VLOAD", ())
                ):
                    raise ValueError(
                        f"Native {case} does not preserve exact three-terminal jumper identity, "
                        "pin roles, bridge-specific endpoints, and separate terminal net"
                    )
            if case in {"control", "isolated-control"} and mismatches:
                raise ValueError(f"Native power-path control mismatched: {mismatches}")
            if case in {"fault", "custom-capacitor-fault", "opaque-capacitor-fault"} and (
                len(mismatches) != 1
                or mismatches[0].issues != ("FB1.1 is assigned to GND; expected VIN",)
            ):
                raise ValueError(
                    f"Native wrong-rail fault differs from the exact mapped expectation: {mismatches}"
                )
            if case == "isolated-control" and (
                tuple(observed.nets.get("ISO_RETURN", ())) != ("C1.2",) or "GND" in observed.nets
            ):
                raise ValueError(
                    "Native isolated-return control does not preserve a separate ISO_RETURN net"
                )
            expected_return_names = ("ISO_RETURN",) if case == "isolated-control" else ("GND",)
            observed_return_names = tuple(
                name for name in ("GND", "ISO_RETURN") if name in observed.nets
            )
            if observed_return_names != expected_return_names:
                raise ValueError(
                    f"Native power-path {case} return-net evidence differs from expectation: "
                    f"{observed_return_names}"
                )
            if case in {"external-source-control", "dnp-external-source-fault"}:
                source_is_dnp = case == "dnp-external-source-fault"
                source_reference = "J1"
                source_net_pins = tuple(observed.nets.get("AUX_INPUT", ()))
                return_net_pins = tuple(observed.nets.get("GND", ()))
                dnp_references = {item.casefold() for item in observed.dnp_components}
                if observed.component_symbols.get(source_reference) != "Synthetic:ExternalSupply":
                    raise ValueError(
                        f"Native {case} does not preserve the external source symbol identity"
                    )
                if observed.component_pin_numbers.get(source_reference) != ("1", "2"):
                    raise ValueError(
                        f"Native {case} does not preserve the two-pin source inventory"
                    )
                if observed.pin_electrical_types.get("J1.1") != "power_out":
                    raise ValueError(f"Native {case} does not preserve J1.1 power_out evidence")
                if "J1.1" not in source_net_pins or "FB1.1" not in source_net_pins:
                    raise ValueError(f"Native {case} does not preserve the custom source rail")
                if "J1.2" not in return_net_pins:
                    raise ValueError(f"Native {case} does not preserve the source return pin")
                if (source_reference.casefold() in dnp_references) != source_is_dnp:
                    raise ValueError(f"Native {case} does not preserve its fitted/DNP source state")
            if case in {"alternate-source-control", "both-sources-dnp-fault"}:
                dnp_references = {item.casefold() for item in observed.dnp_components}
                expected_source_nets = {"J1": "AUX_INPUT", "J2": "ALT_INPUT"}
                for reference, source_net in expected_source_nets.items():
                    if observed.component_symbols.get(reference) != "Synthetic:ExternalSupply":
                        raise ValueError(
                            f"Native {case} does not preserve {reference} source symbol identity"
                        )
                    if observed.component_pin_numbers.get(reference) != ("1", "2"):
                        raise ValueError(
                            f"Native {case} does not preserve {reference} two-pin inventory"
                        )
                    if observed.pin_electrical_types.get(f"{reference}.1") != "power_out":
                        raise ValueError(
                            f"Native {case} does not preserve {reference}.1 power_out evidence"
                        )
                    if f"{reference}.1" not in observed.nets.get(source_net, ()):
                        raise ValueError(
                            f"Native {case} does not preserve {reference} on {source_net}"
                        )
                    if f"{reference}.2" not in observed.nets.get("GND", ()):
                        raise ValueError(f"Native {case} does not preserve {reference} on GND")
                expected_branch_pins = {
                    "AUX_INPUT": {"J1.1", "FB1.1"},
                    "ALT_INPUT": {"J2.1", "FB2.1"},
                    "VLOAD": {"FB1.2", "FB2.2", "U2.1", "C1.1"},
                }
                if any(
                    not pins.issubset(set(observed.nets.get(net, ())))
                    for net, pins in expected_branch_pins.items()
                ) or dnp_references != (
                    {"j1"} if case == "alternate-source-control" else {"j1", "j2"}
                ):
                    raise ValueError(
                        f"Native {case} must preserve distinct source branches converging on VLOAD, "
                        "with expected DNP source population"
                    )
            return_nets_by_case[(case, run)] = observed_return_names
            mismatches_by_case[(case, run)] = mismatches
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-power-path-{case}",
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            unmapped_reports[(case, run)] = evaluate(
                f"synthetic-power-path-{case}",
                coach,
                DesignLintPolicy(),
            )
            reports[(case, run)] = evaluate(
                f"synthetic-power-path-{case}",
                coach,
                DesignLintPolicy(power_path_map=case_path_map),
            )

    fitted_external = read_netlist(output / "external-source-control.first.netlist.xml")
    dnp_external = read_netlist(output / "dnp-external-source-fault.first.netlist.xml")
    normalized_dnp = dnp_external.model_copy(
        update={"dnp_components": fitted_external.dnp_components}
    )
    if normalized_dnp != fitted_external:
        raise ValueError("External-source fitted and DNP fixtures differ beyond population state")
    alternate_fitted = read_netlist(output / "alternate-source-control.first.netlist.xml")
    alternate_both_dnp = read_netlist(output / "both-sources-dnp-fault.first.netlist.xml")
    normalized_alternate_dnp = alternate_both_dnp.model_copy(
        update={"dnp_components": alternate_fitted.dnp_components}
    )
    if normalized_alternate_dnp != alternate_fitted:
        raise ValueError("Alternate-source fixtures differ beyond source population state")

    for case in cases:
        unmapped = unmapped_reports[(case, "first")]
        heuristic_findings = tuple(
            item
            for item in unmapped.findings
            if item.rule_id == "power.input_without_supported_source_path"
        )
        expected_heuristic_faults = {
            "fault",
            "custom-capacitor-fault",
            "dnp-external-source-fault",
            "both-sources-dnp-fault",
            "diode-reverse-fault",
            "open-jumper-fault",
            "bridged-three-pin12-unbridged-terminal-fault",
        }
        expected_ids = (
            ("power.input_without_supported_source_path",)
            if case in expected_heuristic_faults
            else ()
        )
        if tuple(item.rule_id for item in heuristic_findings) != expected_ids:
            raise ValueError(
                f"Native power-path {case} has unexpected no-map source-path findings: "
                f"{heuristic_findings}"
            )
        other_unmapped = tuple(
            item
            for item in unmapped.findings
            if item.rule_id != "power.input_without_supported_source_path"
        )
        expected_other_unmapped = (
            (
                (
                    "power.ic_rail_without_fitted_capacitor",
                    "VLOAD: IC supply decoupling review",
                ),
            )
            if case == "opaque-capacitor-fault"
            else ()
        )
        observed_other_unmapped = tuple((item.rule_id, item.subject) for item in other_unmapped)
        if observed_other_unmapped != expected_other_unmapped:
            raise ValueError(
                f"Native power-path {case} has unexpected other no-map lint findings: "
                f"{observed_other_unmapped}"
            )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native power-path exports differ after normalization to parsed netlist contracts"
        )
    if any(
        normalized_erc_hashes[(case, "first")] != normalized_erc_hashes[(case, "repeat")]
        for case in cases
    ):
        raise ValueError("Native power-path ERC reports differ after normalization")
    if any(
        erc_errors_by_case[(case, "first")] != erc_errors_by_case[(case, "repeat")]
        for case in cases
    ):
        raise ValueError("Native power-path ERC error signatures differ across repeated runs")
    if erc_errors_by_case[("control", "first")] != erc_errors_by_case[("fault", "first")]:
        raise ValueError(
            "Native ERC distinguishes the mapped path control from its wrong-rail fault"
        )
    if any(
        mismatches_by_case[("fault", run)] != mismatches_by_case[("fault", "first")]
        for run in ("first", "repeat")
    ):
        raise ValueError("Native power-path fault mismatches differ across repeated exports")

    for case in cases:
        report = reports[(case, "first")]
        rule_findings = tuple(
            item for item in report.findings if item.rule_id == "power.mapped_series_path_mismatch"
        )
        expected_mapped_faults = {"fault", "custom-capacitor-fault", "opaque-capacitor-fault"}
        if (case not in expected_mapped_faults and rule_findings) or (
            case in expected_mapped_faults and not rule_findings
        ):
            raise ValueError(f"Native power-path {case} produced unexpected lint findings")
        log.event(
            f"power-path-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            source_population=(
                "BOTH_DNP"
                if case == "both-sources-dnp-fault"
                else "J1_DNP_J2_FITTED"
                if case == "alternate-source-control"
                else "DNP"
                if case == "dnp-external-source-fault"
                else "FITTED"
                if case == "external-source-control"
                else "not_applicable"
            ),
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            erc_sha256=raw_erc_hashes[(case, "first")],
            repeat_erc_sha256=raw_erc_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            normalized_erc_sha256=normalized_erc_hashes[(case, "first")],
            repeat_normalized_erc_sha256=normalized_erc_hashes[(case, "repeat")],
            lint_status=report.status,
            power_path_findings=";".join(item.subject for item in rule_findings) or "none",
            power_path_details=";".join(
                issue
                for mismatch in mismatches_by_case[(case, "first")]
                for issue in mismatch.issues
            )
            or "none",
            other_findings=";".join(
                f"{item.rule_id}:{item.subject}"
                for item in report.findings
                if item.rule_id != "power.mapped_series_path_mismatch"
            )
            or "none",
            return_nets=";".join(return_nets_by_case[(case, "first")]) or "none",
            unmapped_lint_status=unmapped_reports[(case, "first")].status,
            unmapped_power_input_findings=";".join(
                f"{item.rule_id}:{item.subject}"
                for item in unmapped_reports[(case, "first")].findings
                if item.rule_id == "power.input_without_supported_source_path"
            )
            or "none",
            unmapped_other_findings=";".join(
                f"{item.rule_id}:{item.subject}"
                for item in unmapped_reports[(case, "first")].findings
                if item.rule_id != "power.input_without_supported_source_path"
            )
            or "none",
            erc_error_types=";".join(erc_errors_by_case[(case, "first")]) or "none",
            erc_violation_types=";".join(
                sorted(
                    {
                        item.type
                        for item in read_kicad_erc_report(
                            output / f"{case}.first.erc.json"
                        ).violations
                    }
                )
            )
            or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract_and_erc",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    log.event(
        "power-path-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    if any(
        digest(fixture_root / filename) != source_hashes[case]
        or digest(inputs / f"{case}.kicad_sch") != source_hashes[case]
        for case, filename in cases.items()
    ):
        raise ValueError("Synthetic power-path fixture source changed during native export")


def stm32_pin_map_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Compare CubeMX pin-map controls and faults with repeated pinned native exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate, scan_stm32_pin_maps
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        Stm32CubeMxPinMap,
        Stm32PinExclusion,
        Stm32PinRequirement,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"STM32 pin-map fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/stm32-pin-map-native"
    )
    cases = {
        "control": ("valid.kicad_sch", "valid.ioc", ()),
        "net-drift": ("net-drift.kicad_sch", "valid.ioc", ("PA0",)),
        "signal-drift": ("valid.kicad_sch", "signal-drift.ioc", ("PA0",)),
    }
    source_hashes = {
        filename: digest(fixture_root / filename)
        for schematic, ioc, _ in cases.values()
        for filename in (schematic, ioc)
    }
    scratch = Path(
        tempfile.mkdtemp(prefix=f"stm32-pin-map-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, (schematic, ioc, _) in cases.items():
        for source in (schematic, ioc):
            destination = inputs / f"{case}-{source}"
            shutil.copyfile(fixture_root / source, destination)
            if digest(destination) != source_hashes[source]:
                raise ValueError(
                    f"Synthetic {case} STM32 fixture changed while preparing native input"
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
    for case, (schematic, _, _) in cases.items():
        source_lines.append(
            f"for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{case}-{schematic}"; done\n'
        )
    script = "".join(source_lines)
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
        "HOME=/tmp/kicad-stm32-pin-map-fixtures",
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
        "stm32-pin-map-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "stm32-pin-map-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native STM32 pin-map fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        "stm32-pin-map-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{path}:{source_hashes[path]}" for path in sorted(source_hashes)),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    pin_map = Stm32CubeMxPinMap(
        id="synthetic-main-mcu",
        basis="Synthetic four-pin fixture package-to-symbol map",
        reference="U1",
        expected_symbol="Synthetic:STM32Fixture",
        expected_part="STM32-TOOLING-FIXTURE",
        ioc_path="firmware/controller.ioc",
        package_pins=("PA0", "PB6", "PB7", "PA13"),
        pins=(
            Stm32PinRequirement(
                port_pin="PA0",
                symbol_pin="1",
                expected_net="USER_BUTTON",
                accepted_ioc_signals=("GPIO_Input",),
                accepted_ioc_gpio_labels=("BUTTON",),
            ),
            Stm32PinRequirement(
                port_pin="PB6",
                symbol_pin="2",
                expected_net="I2C_SCL",
                accepted_ioc_signals=("I2C1_SCL",),
                accepted_ioc_gpio_labels=("SCL",),
            ),
            Stm32PinRequirement(
                port_pin="PB7",
                symbol_pin="3",
                expected_net="I2C_SDA",
                accepted_ioc_signals=("I2C1_SDA",),
                accepted_ioc_gpio_labels=("SDA",),
            ),
        ),
        exclusions=(
            Stm32PinExclusion(
                port_pin="PA13", reason="Reserved for the synthetic SWD debug interface"
            ),
        ),
    )
    policy = DesignLintPolicy(stm32_pin_maps=(pin_map,))
    project_root = scratch / "project"
    ioc_input = project_root / "firmware/controller.ioc"
    ioc_input.parent.mkdir(parents=True)

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case, (_, ioc, expected_pins) in cases.items():
        shutil.copyfile(fixture_root / ioc, ioc_input)
        if digest(ioc_input) != source_hashes[ioc]:
            raise ValueError(f"Synthetic {case} CubeMX input changed while staging native evidence")
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native STM32 fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            coverage = scan_stm32_pin_maps(project_root, policy, observed, raw_hashes[(case, run)])
            observed_pins = tuple(item.port_pin for item in coverage.mismatches)
            if coverage.status != "COMPLETE" or observed_pins != expected_pins:
                raise ValueError(
                    f"Native {case} STM32 coverage expected {expected_pins}, "
                    f"observed {observed_pins} ({coverage.status}: {coverage.issue})"
                )
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-stm32-pin-map-{case}",
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(
                coach.project_id,
                coach,
                policy,
                stm32_pin_map_coverage=coverage,
            )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native STM32 exports differ after normalization to parsed netlist contracts"
        )
    for case, (_, ioc, expected_pins) in cases.items():
        report = reports[(case, "first")]
        rule_findings = tuple(
            item for item in report.findings if item.rule_id == "mcu.stm32_cubemx_pin_map"
        )
        if len(rule_findings) != len(expected_pins):
            raise ValueError(
                f"Native {case} STM32 pin-map findings differ from expected pins {expected_pins}"
            )
        if expected_pins and report.status != "REVIEW":
            raise ValueError(f"Native {case} STM32 pin-map drift did not produce REVIEW")
        if not expected_pins and rule_findings:
            raise ValueError("Native STM32 pin-map control produced an unexpected finding")
        log.event(
            f"stm32-pin-map-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[cases[case][0]],
            ioc_sha256=source_hashes[ioc],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=report.status,
            mismatch_pins=",".join(expected_pins) or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(fixture_root / source) != source_hashes[source]
        or digest(inputs / f"{case}-{source}") != source_hashes[source]
        for case, (schematic, ioc, _) in cases.items()
        for source in (schematic, ioc)
    ):
        raise ValueError("Synthetic STM32 fixture source changed during native export")


def led_rail_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Check native direct-rail and output-driven LED topology fixtures."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.led_heuristics import (
        leds_directly_between_positive_and_return_nets,
        leds_directly_driven_without_visible_series_resistor,
    )
    from .hwrepo.models import (
        ComponentRoleBinding,
        ComponentRoleMap,
        ComponentRolePin,
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"LED rail fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/cohort-led-resistor"
    )
    cases = {
        "direct-rails": "fault-direct-across-rails.kicad_sch",
        "series-control": "control-series-resistor.kicad_sch",
        "parallel-resistor": "fault-parallel-resistor.kicad_sch",
        "direct-output": "fault-direct-output.kicad_sch",
        "series-return-control": "control-output-series-return-resistor.kicad_sch",
        "parallel-output-resistor": "fault-output-parallel-resistor.kicad_sch",
        "custom-direct-output": "fault-custom-direct-output.kicad_sch",
        "custom-series-return-control": "control-custom-output-series-return-resistor.kicad_sch",
    }
    source_hashes = {case: digest(fixture_root / name) for case, name in cases.items()}
    scratch = Path(tempfile.mkdtemp(prefix=f"led-rail-{project}-", dir=log.directory.resolve()))
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
        export_command = (
            f"for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{filename}"; done\n'
        )
        source_lines.append(export_command)
    script = "".join(source_lines)
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
        "HOME=/tmp/kicad-led-fixtures",
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
        script,
    )
    log.event(
        "led-rail-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "led-rail-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native LED fixture command failed: {command.stderr or command.error}")
    log.event(
        "led-rail-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    expected_findings: dict[str, set[str]] = {
        "direct-rails": {"D1: LED directly spans supply and return"},
        "series-control": set(),
        "parallel-resistor": {"D1: LED directly spans supply and return"},
        "direct-output": set(),
        "series-return-control": set(),
        "parallel-output-resistor": set(),
        "custom-direct-output": set(),
        "custom-series-return-control": set(),
    }
    expected_output_findings: dict[str, set[str]] = {
        "direct-rails": set(),
        "series-control": set(),
        "parallel-resistor": set(),
        "direct-output": {"D1: LED directly shares an output net and a rail"},
        "series-return-control": set(),
        "parallel-output-resistor": {"D1: LED directly shares an output net and a rail"},
        "custom-direct-output": set(),
        "custom-series-return-control": set(),
    }
    expected_mapped_output_findings: dict[str, set[str]] = {
        "custom-direct-output": {"D1: LED directly shares an output net and a rail"},
        "custom-series-return-control": set(),
    }
    custom_led_role_map = ComponentRoleMap(
        entries=(
            ComponentRoleBinding(
                part_id="training-led",
                symbol="Training:LED_5mm",
                footprint="Training:LED_0603",
                role="led",
                pins=(
                    ComponentRolePin(number="1", function="A", electrical_type="passive"),
                    ComponentRolePin(number="2", function="K", electrical_type="passive"),
                ),
                basis="Synthetic native fixture reviewed its exact custom LED symbol identity",
            ),
        )
    )
    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native LED fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if case == "parallel-output-resistor":
                native_nets = tuple(set(pins) for pins in observed.nets.values())
                if not any({"U1.1", "D1.1", "R1.1"} <= pins for pins in native_nets) or not any(
                    {"D1.2", "R1.2"} <= pins for pins in native_nets
                ):
                    raise ValueError(
                        "Native parallel-output-resistor fixture does not place R1 across "
                        "the LED's output and return nets"
                    )
            if case.startswith("custom-") and (
                observed.components.get("D1") is None
                or observed.components["D1"].part_id != "training-led"
                or observed.components["D1"].footprint != "Training:LED_0603"
                or observed.component_symbols.get("D1") != "Training:LED_5mm"
                or observed.component_pin_numbers.get("D1") != ("1", "2")
                or observed.pin_functions.get("D1.1") != "A"
                or observed.pin_functions.get("D1.2") != "K"
                or observed.pin_electrical_types.get("D1.1") != "passive"
                or observed.pin_electrical_types.get("D1.2") != "passive"
            ):
                raise ValueError(
                    "Native custom LED export changed its PART_ID, symbol, footprint, "
                    "or complete pin signature"
                )
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            bridges = leds_directly_between_positive_and_return_nets(observed)
            observed_bridges = {
                f"{item.reference}: LED directly spans supply and return" for item in bridges
            }
            if observed_bridges != expected_findings[case]:
                raise ValueError(
                    f"Native {case} LED topology differs from the fixture expectation: "
                    f"{sorted(observed_bridges)}"
                )
            output_driven = leds_directly_driven_without_visible_series_resistor(observed)
            observed_output_findings = {
                f"{item.reference}: LED directly shares an output net and a rail"
                for item in output_driven
            }
            if observed_output_findings != expected_output_findings[case]:
                raise ValueError(
                    f"Native {case} output-driven LED topology differs from the fixture "
                    f"expectation: {sorted(observed_output_findings)}"
                )
            policy = (
                DesignLintPolicy(component_role_map=custom_led_role_map)
                if case.startswith("custom-")
                else DesignLintPolicy()
            )
            mapped_output = leds_directly_driven_without_visible_series_resistor(
                observed, policy.component_role_map
            )
            mapped_output_findings = {
                f"{item.reference}: LED directly shares an output net and a rail"
                for item in mapped_output
            }
            expected_mapped = expected_mapped_output_findings.get(
                case, expected_output_findings[case]
            )
            if mapped_output_findings != expected_mapped:
                raise ValueError(
                    f"Native {case} project-role LED result differs from its fixture "
                    f"expectation: {sorted(mapped_output_findings)}"
                )
            project_id = f"synthetic-led-rail-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, policy)

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native LED exports differ after normalization to parsed netlist contracts"
        )
    for case in cases:
        findings = {
            item.subject
            for item in reports[(case, "first")].findings
            if item.rule_id == "component.led_directly_across_supply_and_return"
        }
        if findings != expected_findings[case]:
            raise ValueError(
                f"Native {case} lint result differs from its LED expectation: {sorted(findings)}"
            )
        output_findings = {
            item.subject
            for item in reports[(case, "first")].findings
            if item.rule_id == "component.led_directly_driven_from_output"
        }
        expected_report_output_findings = expected_mapped_output_findings.get(
            case, expected_output_findings[case]
        )
        if output_findings != expected_report_output_findings:
            raise ValueError(
                f"Native {case} lint result differs from its output-driven LED expectation: "
                f"{sorted(output_findings)}"
            )
        log.event(
            f"led-rail-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=reports[(case, "first")].status,
            led_rule_findings=";".join(sorted(findings)) or "none",
            led_output_rule_findings=";".join(sorted(output_findings)) or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(fixture_root / filename) != source_hashes[case] for case, filename in cases.items()
    ):
        raise ValueError("Synthetic LED fixture source changed during native export")


TWO_PIN_COMPONENT_FIXTURE_CASES: dict[str, tuple[str, str, set[str]]] = {
    "same-net-passive": (
        "two-pin-components/same-net.kicad_sch",
        "component.two_pin_passive_same_net",
        {"R1 (10k resistor) has both pins on one net"},
    ),
    "distinct-nets-passive": (
        "two-pin-components/distinct-nets.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-diode": (
        "two-pin-components/same-net-diode.kicad_sch",
        "component.two_pin_diode_same_net",
        {"D1 (1N4148 diode) has both pins on one net"},
    ),
    "distinct-nets-diode": (
        "two-pin-components/distinct-nets-diode.kicad_sch",
        "component.two_pin_diode_same_net",
        set(),
    ),
    "same-net-crystal": (
        "two-pin-crystals/same-net-crystal.kicad_sch",
        "component.two_pin_crystal_same_net",
        {"Y1 (16 MHz crystal) has both pins on one net"},
    ),
    "distinct-nets-crystal": (
        "two-pin-crystals/distinct-nets-crystal.kicad_sch",
        "component.two_pin_crystal_same_net",
        set(),
    ),
    "same-net-fuse": (
        "two-pin-fuses/same-net-fuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        {"F1 (1A fuse) has both pins on one net"},
    ),
    "distinct-nets-fuse": (
        "two-pin-fuses/distinct-nets-fuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        set(),
    ),
    "same-net-polyfuse": (
        "two-pin-fuses/same-net-polyfuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        {"F1 (1A polyfuse) has both pins on one net"},
    ),
    "distinct-nets-polyfuse": (
        "two-pin-fuses/distinct-nets-polyfuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        set(),
    ),
    "same-net-ferrite": (
        "two-pin-ferrites/same-net-ferrite.kicad_sch",
        "component.two_pin_ferrite_same_net",
        {"FB1 (600R@100MHz ferrite_bead) has both pins on one net"},
    ),
    "distinct-nets-ferrite": (
        "two-pin-ferrites/distinct-nets-ferrite.kicad_sch",
        "component.two_pin_ferrite_same_net",
        set(),
    ),
    "same-net-switch": (
        "two-pin-switches/same-net-spst.kicad_sch",
        "component.two_pin_switch_same_net",
        {"SW1 (Synthetic SPST switch) has both pins on one net"},
    ),
    "distinct-nets-switch": (
        "two-pin-switches/distinct-nets-spst.kicad_sch",
        "component.two_pin_switch_same_net",
        set(),
    ),
}


def two_pin_component_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify same-net component rules against repeated pinned native exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
    )
    from .hwrepo.two_pin_components import two_pin_components_on_same_net
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Two-pin component fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    cases = TWO_PIN_COMPONENT_FIXTURE_CASES
    source_hashes = {
        case: digest(fixture_root / filename) for case, (filename, _, _) in cases.items()
    }
    scratch = Path(
        tempfile.mkdtemp(prefix=f"two-pin-component-{project}-", dir=log.directory.resolve())
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
    for case, (filename, _, _) in cases.items():
        source_lines.append(f'printf "exporting_fixture=%s\\n" "{filename}"\n')
        source_lines.append(
            f"for run in first repeat; do kicad-cli sch export netlist "
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
        "HOME=/tmp/kicad-two-pin-component-fixtures",
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
        "two-pin-component-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "two-pin-component-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native two-pin component fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        "two-pin-component-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case, (_, rule_id, case_expected_subjects) in cases.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native two-pin component fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            candidates = two_pin_components_on_same_net(observed)
            candidate_kinds = {
                "component.two_pin_passive_same_net": {"resistor", "capacitor", "inductor"},
                "component.two_pin_diode_same_net": {"diode"},
                "component.two_pin_crystal_same_net": {"crystal"},
                "component.two_pin_fuse_same_net": {"fuse", "polyfuse"},
                "component.two_pin_ferrite_same_net": {"ferrite_bead"},
                "component.two_pin_switch_same_net": {"switch"},
            }[rule_id]
            matching_candidates = tuple(item for item in candidates if item.kind in candidate_kinds)
            expected_candidate_count = len(case_expected_subjects)
            if len(matching_candidates) != expected_candidate_count:
                raise ValueError(
                    f"Native {case} expected {expected_candidate_count} same-net component "
                    f"candidates, observed {len(matching_candidates)}"
                )
            project_id = f"synthetic-two-pin-component-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native two-pin component exports differ after normalization to parsed netlist contracts"
        )
    for case in cases:
        report = reports[(case, "first")]
        findings = {item.subject for item in report.findings if item.rule_id == cases[case][1]}
        if findings != cases[case][2]:
            raise ValueError(
                f"Native {case} lint result differs from expected findings: {sorted(findings)}"
            )
        expected_status = "REVIEW" if cases[case][2] else "PASS"
        if report.status != expected_status:
            raise ValueError(
                f"Native {case} expected lint status {expected_status}, observed {report.status}"
            )
        log.event(
            f"two-pin-component-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=report.status,
            component_rule=cases[case][1],
            component_findings=";".join(sorted(findings)) or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(fixture_root / filename) != source_hashes[case]
        for case, (filename, _, _) in cases.items()
    ):
        raise ValueError("Synthetic two-pin component fixture source changed during native export")


def component_peer_power_output_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify open peer power-output review against repeated pinned KiCad exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy, DesignLintReport
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Peer power-output fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/design_lint/component-peer-power-output-native"
    )
    cases = {
        "fault": ("fault.kicad_sch", ("U2.2",)),
        "control": ("control.kicad_sch", ()),
    }
    source_hashes = {case: digest(fixture_root / filename) for case, (filename, _) in cases.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"peer-power-output-{project}-", dir=log.directory.resolve())
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
    for case, (filename, _) in cases.items():
        source_lines.extend(
            (
                f'printf "exporting_fixture=%s\\n" "{filename}"\n',
                (
                    f"for run in first repeat; do kicad-cli sch export netlist "
                    f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
                    f'"/fixtures/{filename}"; done\n'
                ),
            )
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
        "HOME=/tmp/kicad-peer-power-output-fixtures",
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
        "component-peer-power-output-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "component-peer-power-output-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native peer power-output fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        "component-peer-power-output-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case, (_, expected_unassigned) in cases.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native peer power-output fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-peer-power-output-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())
            findings = tuple(
                item
                for item in reports[(case, run)].findings
                if item.rule_id == "component.peer_power_output_unconnected"
            )
            actual_unassigned = findings[0].evidence.get("unassigned_pins", ()) if findings else ()
            expected_finding_count = 1 if expected_unassigned else 0
            if actual_unassigned != expected_unassigned or len(findings) != expected_finding_count:
                raise ValueError(
                    f"Native {case} expected peer power-output pins {expected_unassigned}, "
                    f"observed {actual_unassigned}"
                )
            expected_status = "REVIEW" if expected_unassigned else "PASS"
            if reports[(case, run)].status != expected_status:
                raise ValueError(
                    f"Native {case} expected lint status {expected_status}, "
                    f"observed {reports[(case, run)].status}"
                )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native peer power-output exports differ after normalization to parsed contracts"
        )
    for case, (filename, expected_unassigned) in cases.items():
        report = reports[(case, "first")]
        findings = tuple(
            item
            for item in report.findings
            if item.rule_id == "component.peer_power_output_unconnected"
        )
        log.event(
            f"component-peer-power-output-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=report.status,
            unassigned_pins=",".join(expected_unassigned) or "none",
            finding_count=len(findings),
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(fixture_root / filename) != source_hashes[case]
        for case, (filename, _) in cases.items()
    ):
        raise ValueError("Synthetic peer power-output fixture source changed during native export")


def complementary_pair_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify USB SuperSpeed pin-function aliases with repeated native exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        NetlistContract,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Complementary-pair fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/complementary-pair-native"
    )
    cases = {"fault": "fault.kicad_sch", "control": "control.kicad_sch"}
    source_hashes = {case: digest(fixture_root / filename) for case, filename in cases.items()}
    expected_source_hashes = {
        "fault": "cc8832c4f8ab0b74996f3035ec5c9b85780c11e63bee9a33ea50d319dff2c755",
        "control": "4c0fcc56824a6004a1f63cfd0fc026f8e90438919eb936c492eeb96e9ecad601",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("USB SuperSpeed fixture sources differ from the reviewed hashes")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"complementary-pair-{project}-", dir=log.directory.resolve())
    )
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
        "HOME=/tmp/kicad-complementary-pair-fixtures",
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
        script,
    )
    log.event(
        "complementary-pair-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "complementary-pair-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native complementary-pair fixture command failed: {command.stderr or command.error}"
        )

    expected_functions = {
        "J1.1": "StdA_SSTX+",
        "J1.2": "StdA_SSTX-",
        "J1.3": "StdA_SSRX+",
        "J1.4": "StdA_SSRX-",
        "J1.5": "GND",
    }
    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    observed_by_case: dict[str, NetlistContract] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native complementary-pair export omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if observed.pin_functions != expected_functions:
                raise ValueError(
                    "KiCad native export did not preserve the expected Standard-A pin functions: "
                    f"{observed.pin_functions}"
                )
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-usb-superspeed-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())
            observed_by_case[case] = observed

    for case in cases:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native {case} exports differ after netlist normalization")
    for case, expected_findings in (("fault", 1), ("control", 0)):
        report = reports[(case, "first")]
        findings = tuple(
            item for item in report.findings if item.rule_id == "bus.complementary_pair_assignment"
        )
        if len(findings) != expected_findings:
            raise ValueError(
                f"Native {case} expected {expected_findings} complementary-pair findings, "
                f"observed {len(findings)}"
            )
        expected_status = "REVIEW" if expected_findings else "PASS"
        if report.status != expected_status:
            raise ValueError(
                f"Native {case} expected design-lint status {expected_status}, observed "
                f"{report.status}"
            )
        if case == "fault" and (
            findings[0].subject != "J1: USB SuperSpeed RX pair"
            or findings[0].evidence["negative_pins"] != ("J1.4",)
            or findings[0].evidence["negative_nets"]
        ):
            raise ValueError("Native open SSRX- pin did not localize to the expected pair finding")
        log.event(
            f"complementary-pair-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            pin_functions=";".join(
                f"{pin}={function}"
                for pin, function in sorted(observed_by_case[case].pin_functions.items())
            ),
            lint_status=report.status,
            pair_findings=";".join(item.subject for item in findings) or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "complementary-pair-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    if any(
        digest(fixture_root / filename) != source_hashes[case] for case, filename in cases.items()
    ):
        raise ValueError("USB SuperSpeed fixture source changed during native export")


def net_dc_reference_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Compare the connector/capacitor-only hint with pinned exports and native ERC."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy, DesignLintReport
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"DC-reference fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/net-dc-reference"
    )
    cases = {
        "fault": ("fault.kicad_sch", True),
        "control": ("control.kicad_sch", False),
        "dnp-control": ("dnp-control.kicad_sch", False),
    }
    source_hashes = {case: digest(fixture_root / filename) for case, (filename, _) in cases.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"net-dc-reference-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, (filename, _) in cases.items():
        shutil.copyfile(fixture_root / filename, inputs / filename)
        if digest(inputs / filename) != source_hashes[case]:
            raise ValueError(f"Synthetic {case} DC-reference fixture changed during native input")
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
        "for case in fault control dnp-control; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
        '      "/fixtures/${case}.kicad_sch"\n'
        "    kicad-cli sch erc --format json --severity-all "
        '      --output "/output/${case}.${run}.erc.json" '
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
        "HOME=/tmp/kicad-net-dc-reference-fixtures",
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
        script,
    )
    log.event(
        "net-dc-reference-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "net-dc-reference-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native DC-reference fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        "net-dc-reference-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    netlist_hashes: dict[tuple[str, str], str] = {}
    erc_hashes: dict[tuple[str, str], str] = {}
    reports: dict[str, DesignLintReport] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    for case, (_, expected_finding) in cases.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native DC-reference {case} export omitted a required report")
            raw_netlist_sha256 = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized_netlist = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            netlist_hashes[(case, run)] = hashlib.sha256(normalized_netlist).hexdigest()
            erc_report = read_kicad_erc_report(erc_path)
            if erc_report.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native {case} ERC version differs from KiCad {config.kicad_version}"
                )
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "error")
            )
            if erc_errors[(case, run)]:
                raise ValueError(
                    f"Native DC-reference {case} has unexpected ERC errors: "
                    f"{erc_errors[(case, run)]}"
                )
            erc_rows = [
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted(
                            ((detail.description, detail.x, detail.y) for detail in item.items),
                            key=lambda detail: json.dumps(
                                detail,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            ),
                        )
                    ),
                )
                for item in erc_report.violations
            ]
            erc_rows.sort(
                key=lambda violation: json.dumps(
                    violation,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc_report.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            erc_hashes[(case, run)] = hashlib.sha256(normalized_erc).hexdigest()
            report = evaluate(
                f"synthetic-net-dc-reference-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-net-dc-reference-{case}",
                    observed=observed,
                    netlist_sha256=raw_netlist_sha256,
                ),
                DesignLintPolicy(),
            )
            if case in {"fault", "dnp-control"}:
                net = tuple(sorted(observed.nets.get("ANALOG_IN", ())))
                if net != ("C1.1", "J1.1"):
                    raise ValueError(f"Native {case} net membership changed: {net}")
            if case == "dnp-control" and "C1" not in observed.dnp_components:
                raise ValueError("Native DNP control did not preserve C1's DNP state")
            rule_findings = tuple(
                item
                for item in report.findings
                if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
            )
            if bool(rule_findings) != expected_finding:
                raise ValueError(
                    f"Native DC-reference {case} expected finding={expected_finding}, "
                    f"observed {len(rule_findings)}"
                )
            expected_status = "REVIEW" if expected_finding else "PASS"
            if report.status != expected_status:
                raise ValueError(
                    f"Native DC-reference {case} expected {expected_status}, "
                    f"observed {report.status}"
                )
            reports[case] = report

    for case in cases:
        if netlist_hashes[(case, "first")] != netlist_hashes[(case, "repeat")]:
            raise ValueError(f"Native DC-reference {case} netlist export was not repeatable")
        if erc_hashes[(case, "first")] != erc_hashes[(case, "repeat")]:
            raise ValueError(f"Native DC-reference {case} ERC export was not repeatable")
        finding_text = (
            ";".join(
                item.subject
                for item in reports[case].findings
                if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
            )
            or "none"
        )
        log.event(
            f"net-dc-reference-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=netlist_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=netlist_hashes[(case, "repeat")],
            normalized_erc_sha256=erc_hashes[(case, "first")],
            repeat_normalized_erc_sha256=erc_hashes[(case, "repeat")],
            lint_status=reports[case].status,
            finding=finding_text,
            erc_error_types=";".join(erc_errors[(case, "first")]) or "none",
            repeatable="true",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    if any(
        digest(fixture_root / filename) != source_hashes[case]
        for case, (filename, _) in cases.items()
    ):
        raise ValueError("Synthetic DC-reference fixture source changed during native export")


def component_rating_fixtures_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify authored component voltage, power, and contact limits on native netlists."""
    import hashlib
    import os

    from .hwrepo.component_power_ratings import component_power_rating_checks
    from .hwrepo.component_voltage_ratings import component_voltage_rating_checks
    from .hwrepo.connector_contact_ratings import connector_contact_rating_checks
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ComponentPowerRatingAnalysis,
        ComponentPowerRatingRequirement,
        ComponentVoltageRatingAnalysis,
        ComponentVoltageRatingRequirement,
        ConnectorContactCurrentRequirement,
        ConnectorContactRatingAnalysis,
        ConnectorContactRatingRequirement,
        MosfetOperatingState,
        MosfetStressAnalysis,
        MosfetStressRequirement,
        MosfetVoltageInterval,
        NetlistContract,
    )
    from .hwrepo.mosfet_stress import mosfet_stress_checks
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Component and connector rating fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/component-voltage-ratings"
    )
    fixture = fixture_root / "rating-control.kicad_sch"
    fixture_sha256 = digest(fixture)
    power_fixture = fixture_root / "power-control.kicad_sch"
    power_fixture_sha256 = digest(power_fixture)
    contact_fixture = fixture_root / "contact-control.kicad_sch"
    contact_fixture_sha256 = digest(contact_fixture)
    mosfet_fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/mosfet-stress"
    )
    mosfet_fixture = mosfet_fixture_root / "mosfet.kicad_sch"
    mosfet_fixture_sha256 = digest(mosfet_fixture)
    scratch = Path(
        tempfile.mkdtemp(prefix=f"component-voltage-rating-{project}-", dir=log.directory.resolve())
    )
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    source = "".join(
        (
            'mkdir -p "$HOME"\n',
            'actual="$(kicad-cli version)"\n',
            'printf "kicad_version=%s\\n" "$actual"\n',
            f'test "$actual" = "{config.kicad_version}"\n',
            (
                "for run in first repeat; do kicad-cli sch export netlist "
                '--format kicadxml --output "/output/rating.${run}.netlist.xml" '
                '"/fixtures/rating-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch erc --format json --severity-all "
                '--output "/output/rating.${run}.erc.json" '
                '"/fixtures/rating-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch export netlist "
                '--format kicadxml --output "/output/power.${run}.netlist.xml" '
                '"/fixtures/power-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch erc --format json --severity-all "
                '--output "/output/power.${run}.erc.json" '
                '"/fixtures/power-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch export netlist "
                '--format kicadxml --output "/output/contact.${run}.netlist.xml" '
                '"/fixtures/contact-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch erc --format json --severity-all "
                '--output "/output/contact.${run}.erc.json" '
                '"/fixtures/contact-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch export netlist "
                '--format kicadxml --output "/output/mosfet.${run}.netlist.xml" '
                '"/mosfet-fixture/mosfet.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch erc --format json --severity-all "
                '--output "/output/mosfet.${run}.erc.json" '
                '"/mosfet-fixture/mosfet.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch export netlist "
                '--format kicadxml --output "/output/power.${run}.netlist.xml" '
                '"/fixtures/power-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch erc --format json --severity-all "
                '--output "/output/power.${run}.erc.json" '
                '"/fixtures/power-control.kicad_sch"; done\n'
            ),
        )
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
        "HOME=/tmp/kicad-component-voltage-rating-fixture",
        "-v",
        f"{fixture_root.resolve()}:/fixtures:ro",
        "-v",
        f"{mosfet_fixture_root.resolve()}:/mosfet-fixture:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        source,
    )
    log.event(
        "component-voltage-rating-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "component-voltage-rating-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native component voltage-rating fixture command failed: "
            f"{command.stderr or command.error}"
        )

    raw_hashes: dict[str, str] = {}
    normalized_hashes: dict[str, str] = {}
    normalized_erc_hashes: dict[str, str] = {}
    erc_types: dict[str, tuple[str, ...]] = {}
    erc_error_types: dict[str, tuple[str, ...]] = {}
    parsed: dict[str, NetlistContract] = {}
    for run in ("first", "repeat"):
        netlist_path = output / f"rating.{run}.netlist.xml"
        if not netlist_path.is_file():
            raise ValueError(f"Native component-rating export omitted {netlist_path.name}")
        raw_hashes[run] = digest(netlist_path)
        observed = read_netlist(netlist_path)
        normalized = json.dumps(
            observed.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
        parsed[run] = observed
        erc_path = output / f"rating.{run}.erc.json"
        if not erc_path.is_file():
            raise ValueError(f"Native component-rating export omitted {erc_path.name}")
        erc_report = read_kicad_erc_report(erc_path)
        if erc_report.kicad_version != config.kicad_version:
            raise ValueError(
                f"Native component-rating ERC version differs from KiCad {config.kicad_version}"
            )
        erc_types[run] = tuple(sorted(item.type for item in erc_report.violations))
        erc_error_types[run] = tuple(
            sorted(item.type for item in erc_report.violations if item.severity == "error")
        )
        if erc_error_types[run]:
            raise ValueError(
                f"Synthetic component-rating schematic has native ERC errors: "
                f"{erc_error_types[run]}"
            )
        normalized_erc = json.dumps(
            {
                "kicad_version": erc_report.kicad_version,
                "violations": sorted(
                    [
                        (
                            item.type,
                            item.severity,
                            item.description,
                            tuple(
                                sorted(
                                    [
                                        (detail.description, detail.x, detail.y)
                                        for detail in item.items
                                    ],
                                    key=lambda detail: json.dumps(
                                        detail,
                                        sort_keys=True,
                                        separators=(",", ":"),
                                        ensure_ascii=False,
                                    ),
                                )
                            ),
                        )
                        for item in erc_report.violations
                    ],
                    key=lambda item: json.dumps(
                        item,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ),
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_erc_hashes[run] = hashlib.sha256(normalized_erc).hexdigest()
    if normalized_hashes["first"] != normalized_hashes["repeat"]:
        raise ValueError("Native component-rating exports differ after netlist normalization")
    if normalized_erc_hashes["first"] != normalized_erc_hashes["repeat"]:
        raise ValueError("Native component-rating ERC reports differ after normalization")

    observed = parsed["first"]
    c1 = observed.components.get("C1")
    if (
        c1 is None
        or c1.footprint != "Synthetic:0603"
        or c1.part_id != "CAP-0603-16V"
        or observed.component_symbols.get("C1") != "Device:C"
        or set(observed.component_pin_numbers.get("C1", ())) != {"1", "2"}
    ):
        raise ValueError("Native C1 component identity or exact two-pin inventory differs")
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    if pin_nets.get("c1.1") != {"VLOAD"} or pin_nets.get("c1.2") != {"GND"}:
        raise ValueError("Native C1 pin-to-net assignments differ from the synthetic map")

    def check(maximum_expected_voltage_v: float) -> tuple[str, tuple[str, ...]]:
        requirement = ComponentVoltageRatingRequirement(
            id="load-capacitor",
            reference="C1",
            expected_symbol="Device:C",
            expected_footprint="Synthetic:0603",
            expected_part_id="CAP-0603-16V",
            pins=("C1.1", "C1.2"),
            nets=("VLOAD", "GND"),
            rated_working_voltage_v=24.0,
            maximum_expected_voltage_v=maximum_expected_voltage_v,
            maximum_utilization_fraction=0.8,
            rating_source="Synthetic capacitor datasheet Rev A, working-voltage table",
            rating_conditions="DC working voltage over the stated temperature range",
            stress_basis="Synthetic reviewed worst-case steady-state rail envelope",
        )
        spec = ComponentVoltageRatingAnalysis(
            basis="Synthetic exact-part rating comparison", requirements=(requirement,)
        )
        checks = component_voltage_rating_checks(spec, observed)
        margin = next(item for item in checks if item.id.endswith("/utilization"))
        if any(item.status != "PASS" for item in checks if not item.id.endswith("/utilization")):
            raise ValueError("Native component identity and pin-map checks did not pass")
        return margin.status, tuple(item.id for item in checks if item.status != "PASS")

    control_status, control_open = check(15.0)
    fault_status, fault_open = check(20.0)
    if control_status != "PASS" or control_open:
        raise ValueError("Native component voltage-rating control did not pass")
    if fault_status != "FAIL" or len(fault_open) != 1:
        raise ValueError("Native over-utilization fault was not detected")
    log.event(
        "component-voltage-rating-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        fixture_sha256=fixture_sha256,
        first_netlist_sha256=raw_hashes["first"],
        repeat_netlist_sha256=raw_hashes["repeat"],
        normalized_netlist_sha256=normalized_hashes["first"],
        repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
        normalized_erc_sha256=normalized_erc_hashes["first"],
        repeat_normalized_erc_sha256=normalized_erc_hashes["repeat"],
        native_erc_types=",".join(erc_types["first"]) or "none",
        native_erc_error_types=",".join(erc_error_types["first"]) or "none",
        repeatable="true",
        repeatability_basis="normalized_netlist_and_erc",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    for case, stress, status in (
        ("control", 15.0, control_status),
        ("over-limit-fault", 20.0, fault_status),
    ):
        log.event(
            f"component-voltage-rating-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            fixture_sha256=fixture_sha256,
            netlist_sha256=raw_hashes["first"],
            normalized_erc_sha256=normalized_erc_hashes["first"],
            native_erc_types=",".join(erc_types["first"]) or "none",
            native_erc_error_types=",".join(erc_error_types["first"]) or "none",
            maximum_expected_voltage_v=stress,
            utilization_status=status,
            repeatable="true",
        )
    if digest(fixture) != fixture_sha256:
        raise ValueError("Synthetic component voltage-rating fixture changed during native export")

    power_raw_hashes: dict[str, str] = {}
    power_normalized_hashes: dict[str, str] = {}
    power_erc_hashes: dict[str, str] = {}
    power_erc_types: dict[str, tuple[tuple[str, str], ...]] = {}
    power_parsed: dict[str, NetlistContract] = {}
    for run in ("first", "repeat"):
        netlist_path = output / f"power.{run}.netlist.xml"
        if not netlist_path.is_file():
            raise ValueError(f"Native component power-rating export omitted {netlist_path.name}")
        power_raw_hashes[run] = digest(netlist_path)
        observed_power = read_netlist(netlist_path)
        normalized_power = json.dumps(
            observed_power.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        power_normalized_hashes[run] = hashlib.sha256(normalized_power).hexdigest()
        power_parsed[run] = observed_power

        erc_path = output / f"power.{run}.erc.json"
        if not erc_path.is_file():
            raise ValueError(f"Native component power-rating export omitted {erc_path.name}")
        erc_report = read_kicad_erc_report(erc_path)
        if erc_report.kicad_version != config.kicad_version:
            raise ValueError(
                f"Native component power-rating ERC version differs from KiCad {config.kicad_version}"
            )
        power_erc_types[run] = tuple(
            sorted((item.type, item.severity) for item in erc_report.violations)
        )
        errors = tuple(item for item in power_erc_types[run] if item[1] == "error")
        if errors:
            raise ValueError(
                f"Synthetic component power-rating schematic has native ERC errors: {errors}"
            )
        power_erc_hashes[run] = hashlib.sha256(
            json.dumps(power_erc_types[run], separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
    if power_normalized_hashes["first"] != power_normalized_hashes["repeat"]:
        raise ValueError("Native component power-rating exports differ after netlist normalization")
    if power_erc_hashes["first"] != power_erc_hashes["repeat"]:
        raise ValueError("Native component power-rating ERC results differ after normalization")

    power_observed = power_parsed["first"]
    resistor = power_observed.components.get("R1")
    if (
        resistor is None
        or resistor.footprint != "Synthetic:R_0603"
        or resistor.part_id != "RES-SYNTHETIC-0603"
        or power_observed.component_symbols.get("R1") != "Device:R"
        or set(power_observed.component_pin_numbers.get("R1", ())) != {"1", "2"}
    ):
        raise ValueError("Native R1 component identity or exact two-pin inventory differs")
    power_pin_nets: dict[str, set[str]] = {}
    for net, pins in power_observed.nets.items():
        for pin in pins:
            power_pin_nets.setdefault(pin.casefold(), set()).add(net)
    if power_pin_nets.get("r1.1") != {"INPUT"} or power_pin_nets.get("r1.2") != {"OUTPUT"}:
        raise ValueError("Native R1 pin-to-net assignments differ from the synthetic map")

    def power_check(maximum_expected_power_w: float) -> tuple[str, tuple[str, ...]]:
        requirement = ComponentPowerRatingRequirement(
            id="sense-resistor",
            reference="R1",
            expected_symbol="Device:R",
            expected_footprint="Synthetic:R_0603",
            expected_part_id="RES-SYNTHETIC-0603",
            pins=("R1.1", "R1.2"),
            nets=("INPUT", "OUTPUT"),
            rated_power_w=0.5,
            derated_allowable_power_w=0.25,
            maximum_expected_power_w=maximum_expected_power_w,
            maximum_utilization_fraction=0.8,
            rating_source="Synthetic resistor specification, power table",
            rating_conditions="Synthetic declared board-temperature conditions",
            derating_basis="Synthetic reviewed derating curve at the fixture temperature",
            stress_basis="Synthetic reviewed worst-case dissipation calculation",
        )
        spec = ComponentPowerRatingAnalysis(
            basis="Synthetic exact-part power-rating comparison", requirements=(requirement,)
        )
        checks = component_power_rating_checks(spec, power_observed)
        margin = next(item for item in checks if item.id.endswith("/utilization"))
        if any(item.status != "PASS" for item in checks if not item.id.endswith("/utilization")):
            raise ValueError("Native component power identity and pin-map checks did not pass")
        return margin.status, tuple(item.id for item in checks if item.status != "PASS")

    power_control_status, power_control_open = power_check(0.1)
    power_fault_status, power_fault_open = power_check(0.21)
    if power_control_status != "PASS" or power_control_open:
        raise ValueError("Native component power-rating control did not pass")
    if power_fault_status != "FAIL" or len(power_fault_open) != 1:
        raise ValueError("Native over-utilization power fault was not detected")

    power_receipt = (scratch / "native.command.json").relative_to(root).as_posix()
    log.event(
        "component-power-rating-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        fixture_sha256=power_fixture_sha256,
        first_netlist_sha256=power_raw_hashes["first"],
        repeat_netlist_sha256=power_raw_hashes["repeat"],
        normalized_netlist_sha256=power_normalized_hashes["first"],
        repeat_normalized_netlist_sha256=power_normalized_hashes["repeat"],
        normalized_erc_sha256=power_erc_hashes["first"],
        repeat_normalized_erc_sha256=power_erc_hashes["repeat"],
        native_erc_types=";".join(
            f"{kind}:{severity}" for kind, severity in power_erc_types["first"]
        )
        or "none",
        native_erc_error_types="none",
        repeatable="true",
        repeatability_basis="normalized_netlist_and_erc_types",
        command_receipt=power_receipt,
    )
    for case, stress, status in (
        ("control", 0.1, power_control_status),
        ("over-limit-fault", 0.21, power_fault_status),
    ):
        log.event(
            f"component-power-rating-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            fixture_sha256=power_fixture_sha256,
            netlist_sha256=power_raw_hashes["first"],
            normalized_netlist_sha256=power_normalized_hashes["first"],
            normalized_erc_sha256=power_erc_hashes["first"],
            native_erc_types=";".join(
                f"{kind}:{severity}" for kind, severity in power_erc_types["first"]
            )
            or "none",
            native_erc_error_types="none",
            maximum_expected_power_w=stress,
            utilization_status=status,
            repeatable="true",
        )
    if digest(power_fixture) != power_fixture_sha256:
        raise ValueError("Synthetic component power-rating fixture changed during native export")

    contact_parsed: dict[str, NetlistContract] = {}
    contact_normalized_hashes: dict[str, str] = {}
    contact_erc_hashes: dict[str, str] = {}
    contact_erc_types: dict[str, tuple[tuple[str, str], ...]] = {}
    for run in ("first", "repeat"):
        netlist_path = output / f"contact.{run}.netlist.xml"
        erc_path = output / f"contact.{run}.erc.json"
        if not netlist_path.is_file() or not erc_path.is_file():
            raise ValueError(
                "Native connector contact-rating fixture omitted a repeated export or ERC"
            )
        observed_contact = read_netlist(netlist_path)
        normalized = json.dumps(
            observed_contact.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        contact_normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
        contact_parsed[run] = observed_contact
        erc_report = read_kicad_erc_report(erc_path)
        if erc_report.kicad_version != config.kicad_version:
            raise ValueError(
                "Native connector contact-rating ERC version differs from its pinned KiCad version"
            )
        contact_erc_types[run] = tuple(
            sorted((item.type, item.severity) for item in erc_report.violations)
        )
        errors = tuple(item for item in contact_erc_types[run] if item[1] == "error")
        if errors:
            raise ValueError(f"Synthetic contact-rating schematic has native ERC errors: {errors}")
        contact_erc_hashes[run] = hashlib.sha256(
            json.dumps(contact_erc_types[run], separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
    if contact_normalized_hashes["first"] != contact_normalized_hashes["repeat"]:
        raise ValueError("Native connector contact-rating exports differ after normalization")
    if contact_erc_hashes["first"] != contact_erc_hashes["repeat"]:
        raise ValueError("Native connector contact-rating ERC results differ after normalization")

    contact_observed = contact_parsed["first"]

    def contact_check(maximum_expected_current_a: float) -> tuple[str, tuple[str, ...]]:
        contact = ConnectorContactCurrentRequirement(
            id="contact-current",
            pin_number="1",
            expected_function="Pin_1",
            expected_net="CONTACT_CURRENT",
            rated_current_a=3.0,
            derated_allowable_current_a=2.0,
            maximum_expected_current_a=maximum_expected_current_a,
            maximum_utilization_fraction=0.8,
            rating_source="Synthetic connector specification, contact-current table",
            rating_conditions="Synthetic 20 C ambient, two loaded contacts, stated wire gauge",
            derating_basis="Synthetic project review for the stated test conditions",
            load_basis="Synthetic maximum DC load assigned to this individual contact",
        )
        requirement = ConnectorContactRatingRequirement(
            id="host-connector",
            reference="J1",
            expected_symbol="Connector_Generic:Conn_01x02",
            expected_footprint="Synthetic:Header_1x02",
            expected_part_id="SYNTHETIC-HEADER-2P-3A",
            native_pin_numbers=("1", "2"),
            contacts=(contact,),
        )
        spec = ConnectorContactRatingAnalysis(
            basis="Synthetic per-contact connector current comparison",
            requirements=(requirement,),
        )
        checks = connector_contact_rating_checks(spec, contact_observed)
        margin = next(item for item in checks if item.id.endswith("/utilization"))
        unexpected = tuple(
            item.id
            for item in checks
            if not item.id.endswith("/utilization") and item.status != "PASS"
        )
        if unexpected:
            raise ValueError(f"Native contact identity and pin map did not pass: {unexpected}")
        return margin.status, tuple(item.id for item in checks if item.status != "PASS")

    contact_control_status, contact_control_open = contact_check(1.6)
    contact_fault_status, contact_fault_open = contact_check(1.61)
    if contact_control_status != "PASS" or contact_control_open:
        raise ValueError("Native connector contact-rating equality control did not pass")
    if contact_fault_status != "FAIL" or len(contact_fault_open) != 1:
        raise ValueError("Native connector contact over-utilization fault was not detected")

    contact_receipt = (scratch / "native.command.json").relative_to(root).as_posix()
    log.event(
        "connector-contact-rating-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        fixture_sha256=contact_fixture_sha256,
        first_netlist_sha256=digest(output / "contact.first.netlist.xml"),
        repeat_netlist_sha256=digest(output / "contact.repeat.netlist.xml"),
        normalized_netlist_sha256=contact_normalized_hashes["first"],
        repeat_normalized_netlist_sha256=contact_normalized_hashes["repeat"],
        normalized_erc_sha256=contact_erc_hashes["first"],
        repeat_normalized_erc_sha256=contact_erc_hashes["repeat"],
        native_erc_types=";".join(
            f"{kind}:{severity}" for kind, severity in contact_erc_types["first"]
        )
        or "none",
        native_erc_error_types="none",
        repeatable="true",
        repeatability_basis="normalized_netlist_and_erc_types",
        command_receipt=contact_receipt,
    )
    for case, maximum_current_a, status in (
        ("control", 1.6, contact_control_status),
        ("over-limit-fault", 1.61, contact_fault_status),
    ):
        log.event(
            f"connector-contact-rating-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            fixture_sha256=contact_fixture_sha256,
            normalized_netlist_sha256=contact_normalized_hashes["first"],
            normalized_erc_sha256=contact_erc_hashes["first"],
            native_erc_error_types="none",
            maximum_expected_current_a=maximum_current_a,
            utilization_status=status,
            repeatable="true",
        )
    if digest(contact_fixture) != contact_fixture_sha256:
        raise ValueError("Synthetic connector contact-rating fixture changed during native export")

    mosfet_parsed: dict[str, NetlistContract] = {}
    mosfet_normalized_hashes: dict[str, str] = {}
    mosfet_erc_hashes: dict[str, str] = {}
    mosfet_erc_types: dict[str, tuple[tuple[str, str], ...]] = {}
    for run in ("first", "repeat"):
        netlist_path = output / f"mosfet.{run}.netlist.xml"
        erc_path = output / f"mosfet.{run}.erc.json"
        if not netlist_path.is_file() or not erc_path.is_file():
            raise ValueError("Native MOSFET stress fixture omitted a repeated export or ERC report")
        observed_mosfet = read_netlist(netlist_path)
        normalized = json.dumps(
            observed_mosfet.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        mosfet_normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
        mosfet_parsed[run] = observed_mosfet
        erc_report = read_kicad_erc_report(erc_path)
        if erc_report.kicad_version != config.kicad_version:
            raise ValueError("Native MOSFET ERC version differs from its pinned KiCad version")
        mosfet_erc_types[run] = tuple(
            sorted((item.type, item.severity) for item in erc_report.violations)
        )
        errors = tuple(item for item in mosfet_erc_types[run] if item[1] == "error")
        if errors:
            raise ValueError(f"Synthetic MOSFET schematic has native ERC errors: {errors}")
        mosfet_erc_hashes[run] = hashlib.sha256(
            json.dumps(mosfet_erc_types[run], separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
    if mosfet_normalized_hashes["first"] != mosfet_normalized_hashes["repeat"]:
        raise ValueError("Native MOSFET exports differ after netlist normalization")
    if mosfet_erc_hashes["first"] != mosfet_erc_hashes["repeat"]:
        raise ValueError("Native MOSFET ERC reports differ after normalization")

    mosfet_observed = mosfet_parsed["first"]
    mosfet_component = mosfet_observed.components.get("Q1")
    if (
        mosfet_component is None
        or mosfet_component.footprint != "Synthetic:TO-220"
        or mosfet_component.part_id != "SYN-NMOS-001"
        or mosfet_observed.component_symbols.get("Q1") != "Synthetic:Q_NMOS_GDS"
        or set(mosfet_observed.component_pin_numbers.get("Q1", ())) != {"1", "2", "3"}
        or {pin: mosfet_observed.pin_functions.get(pin) for pin in ("Q1.1", "Q1.2", "Q1.3")}
        != {"Q1.1": "D", "Q1.2": "G", "Q1.3": "S"}
    ):
        raise ValueError("Native MOSFET identity, pin functions, or exact inventory differs")
    mosfet_pin_nets: dict[str, set[str]] = {}
    for net, pins in mosfet_observed.nets.items():
        for pin in pins:
            mosfet_pin_nets.setdefault(pin.casefold(), set()).add(net)
    if any(
        mosfet_pin_nets.get(pin.casefold()) != {net}
        for pin, net in (("Q1.1", "D_NET"), ("Q1.2", "G_NET"), ("Q1.3", "S_NET"))
    ):
        raise ValueError("Native MOSFET terminal-to-net assignments differ from the synthetic map")

    def mosfet_check(drain_v: float, gate_v: float) -> tuple[str, tuple[str, ...]]:
        states = (
            MosfetOperatingState(
                id="off",
                net_potentials={
                    name: MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0)
                    for name in ("D_NET", "G_NET", "S_NET")
                },
            ),
            MosfetOperatingState(
                id="on",
                net_potentials={
                    "D_NET": MosfetVoltageInterval(minimum_v=drain_v, maximum_v=drain_v),
                    "G_NET": MosfetVoltageInterval(minimum_v=gate_v, maximum_v=gate_v),
                    "S_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
                },
            ),
        )
        requirement = MosfetStressRequirement(
            id="main-switch",
            reference="Q1",
            expected_symbol="Synthetic:Q_NMOS_GDS",
            expected_footprint="Synthetic:TO-220",
            expected_part_id="SYN-NMOS-001",
            drain_pin="Q1.1",
            drain_function="D",
            drain_net="D_NET",
            gate_pin="Q1.2",
            gate_function="G",
            gate_net="G_NET",
            source_pin="Q1.3",
            source_function="S",
            source_net="S_NET",
            rated_maximum_vds_v=60.0,
            rated_maximum_vgs_v=20.0,
            maximum_utilization_fraction=0.8,
            rating_source="Synthetic MOSFET specification, absolute maximum ratings table",
            rating_conditions="Synthetic declared operating conditions",
            stress_basis="Synthetic required steady-state off and on potential bounds",
        )
        spec = MosfetStressAnalysis(
            basis="Synthetic per-state MOSFET terminal stress comparison",
            required_states=("off", "on"),
            states=states,
            requirements=(requirement,),
        )
        checks = mosfet_stress_checks(spec, mosfet_observed)
        unexpected = tuple(
            item.id
            for item in checks
            if item.status != "PASS" and not (item.id.endswith("/vds") or item.id.endswith("/vgs"))
        )
        if unexpected:
            raise ValueError(
                f"Native MOSFET identity, terminal, or state checks failed: {unexpected}"
            )
        stress = tuple(
            item for item in checks if item.id.endswith("/vds") or item.id.endswith("/vgs")
        )
        if drain_v == 48.0 and gate_v == 16.0:
            if any(item.status != "PASS" for item in stress):
                raise ValueError("Native MOSFET equality-at-project-limit control failed")
            return "PASS", ()
        expected_failed = {
            "mosfet-stress/main-switch/state-on/vds",
            "mosfet-stress/main-switch/state-on/vgs",
        }
        failed = tuple(sorted(item.id for item in stress if item.status == "FAIL"))
        unexpected_statuses = tuple(
            item.id
            for item in stress
            if item.status != ("FAIL" if item.id in expected_failed else "PASS")
        )
        if set(failed) != expected_failed or unexpected_statuses:
            raise ValueError("Native MOSFET over-stress fault was not detected for both ratings")
        return "FAIL", failed

    mosfet_control_status, mosfet_control_open = mosfet_check(48.0, 16.0)
    mosfet_fault_status, mosfet_fault_open = mosfet_check(49.0, 17.0)
    if mosfet_control_status != "PASS" or mosfet_control_open:
        raise ValueError("Native MOSFET control at the project utilization limit did not pass")
    if mosfet_fault_status != "FAIL" or len(mosfet_fault_open) != 2:
        raise ValueError("Native MOSFET over-utilization fault was not detected")

    mosfet_receipt = (scratch / "native.command.json").relative_to(root).as_posix()
    log.event(
        "component-mosfet-stress-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        fixture_sha256=mosfet_fixture_sha256,
        first_netlist_sha256=digest(output / "mosfet.first.netlist.xml"),
        repeat_netlist_sha256=digest(output / "mosfet.repeat.netlist.xml"),
        normalized_netlist_sha256=mosfet_normalized_hashes["first"],
        repeat_normalized_netlist_sha256=mosfet_normalized_hashes["repeat"],
        normalized_erc_sha256=mosfet_erc_hashes["first"],
        repeat_normalized_erc_sha256=mosfet_erc_hashes["repeat"],
        native_erc_types=";".join(
            f"{kind}:{severity}" for kind, severity in mosfet_erc_types["first"]
        )
        or "none",
        native_erc_error_types="none",
        repeatable="true",
        repeatability_basis="normalized_netlist_and_erc_types",
        command_receipt=mosfet_receipt,
    )
    for case, drain_v, gate_v, status in (
        ("control", 48.0, 16.0, mosfet_control_status),
        ("over-limit-fault", 49.0, 17.0, mosfet_fault_status),
    ):
        log.event(
            f"component-mosfet-stress-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            fixture_sha256=mosfet_fixture_sha256,
            normalized_netlist_sha256=mosfet_normalized_hashes["first"],
            normalized_erc_sha256=mosfet_erc_hashes["first"],
            native_erc_error_types="none",
            drain_potential_v=drain_v,
            gate_potential_v=gate_v,
            utilization_status=status,
            repeatable="true",
        )
    if digest(mosfet_fixture) != mosfet_fixture_sha256:
        raise ValueError("Synthetic MOSFET stress fixture changed during native export")


def power_sequence_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Repeat exact-version exports and check an authored PG-to-enable dependency."""
    import hashlib
    import json
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        NetlistContract,
        PowerSequenceDependencyRequirement,
        PowerSequenceEndpointRequirement,
        PowerSequenceMap,
        PowerSequenceStageRequirement,
    )
    from .hwrepo.power_sequences import (
        PowerSequenceObservedCycle,
        power_sequence_graph_has_cycle,
        power_sequence_mismatches,
        power_sequence_observed_enable_cycles,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Power-sequence fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/power-sequence-native"
    )
    cases = {
        "control": "control.kicad_sch",
        "open-enable": "open-enable.kicad_sch",
        "output-enable-cycle": "output-enable-cycle.kicad_sch",
    }
    fixtures = {case: fixture_root / filename for case, filename in cases.items()}
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"power-sequence-{project}-", dir=log.directory.resolve())
    )
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    export_commands = "\n".join(
        f"for run in first repeat; do kicad-cli sch export netlist --format kicadxml "
        f'--output "/output/{case}.${{run}}.netlist.xml" '
        f'"/fixtures/{cases[case]}" || exit $?; done'
        for case in cases
    )
    source = "\n".join(
        (
            'mkdir -p "$HOME"',
            'actual="$(kicad-cli version)"',
            'printf "kicad_version=%s\\n" "$actual"',
            f'test "$actual" = "{config.kicad_version}"',
            export_commands,
        )
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
        "HOME=/tmp/kicad-power-sequence-fixture",
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
        source,
    )
    stage = "power-sequence-fixture/native-export"
    log.event(stage, "START", project=project, kicad_version=config.kicad_version, image=pinned)
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            stage,
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native power-sequence fixture command failed: {command.stderr or command.error}"
        )

    sequence_map = PowerSequenceMap(
        basis="Synthetic datasheet startup table: upstream PG must drive downstream EN",
        stages=(
            PowerSequenceStageRequirement(
                id="rail-a",
                output=PowerSequenceEndpointRequirement(
                    reference="U1",
                    pin="U1.2",
                    symbol="Synthetic:Regulator",
                    footprint="Synthetic:SOT23-5",
                    net="RAIL_A",
                    part_id="SYNTH-REG-A",
                ),
                power_good=PowerSequenceEndpointRequirement(
                    reference="U1",
                    pin="U1.3",
                    symbol="Synthetic:Regulator",
                    footprint="Synthetic:SOT23-5",
                    net="GOOD_A",
                    part_id="SYNTH-REG-A",
                ),
                enable=PowerSequenceEndpointRequirement(
                    reference="U1",
                    pin="U1.1",
                    symbol="Synthetic:Regulator",
                    footprint="Synthetic:SOT23-5",
                    net="CONTROL_ON",
                    part_id="SYNTH-REG-A",
                ),
                enable_control="always_on",
                basis="Synthetic upstream regulator source page 3",
            ),
            PowerSequenceStageRequirement(
                id="rail-b",
                output=PowerSequenceEndpointRequirement(
                    reference="U2",
                    pin="U2.2",
                    symbol="Synthetic:Regulator",
                    footprint="Synthetic:SOT23-5",
                    net="RAIL_B",
                    part_id="SYNTH-REG-B",
                ),
                enable=PowerSequenceEndpointRequirement(
                    reference="U2",
                    pin="U2.1",
                    symbol="Synthetic:Regulator",
                    footprint="Synthetic:SOT23-5",
                    net="GOOD_A",
                    part_id="SYNTH-REG-B",
                ),
                enable_control="netlist",
                basis="Synthetic downstream regulator source page 5",
            ),
        ),
        dependencies=(
            PowerSequenceDependencyRequirement(
                id="rail-a-pg-before-rail-b-enable",
                predecessor_stage="rail-a",
                successor_stage="rail-b",
                signal_net="GOOD_A",
                basis="Synthetic source requirement: rail A power-good gates rail B enable",
            ),
        ),
    )
    if power_sequence_graph_has_cycle(sequence_map):
        raise ValueError("Synthetic power-sequence control map unexpectedly contains a cycle")

    def cycle_endpoint(
        reference: str, pin: str, net: str, part_id: str
    ) -> PowerSequenceEndpointRequirement:
        return PowerSequenceEndpointRequirement(
            reference=reference,
            pin=f"{reference}.{pin}",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net=net,
            part_id=part_id,
        )

    cycle_sequence_map = PowerSequenceMap(
        basis="Synthetic source page 6, mapped stage endpoint table",
        stages=(
            PowerSequenceStageRequirement(
                id="rail-a",
                output=cycle_endpoint("U1", "2", "RAIL_A", "SYNTH-REG-A"),
                power_good=cycle_endpoint("U1", "3", "GOOD_A", "SYNTH-REG-A"),
                enable=cycle_endpoint("U1", "1", "RAIL_B", "SYNTH-REG-A"),
                enable_control="netlist",
                basis="Synthetic source identifies rail A stage endpoints",
            ),
            PowerSequenceStageRequirement(
                id="rail-b",
                output=cycle_endpoint("U2", "2", "RAIL_B", "SYNTH-REG-B"),
                power_good=cycle_endpoint("U2", "3", "GOOD_B", "SYNTH-REG-B"),
                enable=cycle_endpoint("U2", "1", "RAIL_A", "SYNTH-REG-B"),
                enable_control="netlist",
                basis="Synthetic source identifies rail B stage endpoints",
            ),
            PowerSequenceStageRequirement(
                id="rail-c",
                output=cycle_endpoint("U3", "2", "RAIL_C", "SYNTH-REG-C"),
                power_good=cycle_endpoint("U3", "3", "GOOD_C", "SYNTH-REG-C"),
                enable=cycle_endpoint("U3", "1", "GOOD_B", "SYNTH-REG-C"),
                enable_control="netlist",
                basis="Synthetic source identifies rail C stage endpoints",
            ),
        ),
        dependencies=(
            PowerSequenceDependencyRequirement(
                id="rail-b-before-rail-c",
                predecessor_stage="rail-b",
                successor_stage="rail-c",
                signal_net="GOOD_B",
                basis="Synthetic source requires rail B power-good to enable rail C",
            ),
        ),
    )
    if power_sequence_graph_has_cycle(cycle_sequence_map):
        raise ValueError("Synthetic output-to-enable map has a declared dependency cycle")
    sequence_maps = {
        "control": sequence_map,
        "open-enable": sequence_map,
        "output-enable-cycle": cycle_sequence_map,
    }

    parsed: dict[tuple[str, str], NetlistContract] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    normalized_hashes: dict[tuple[str, str], str] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native power-sequence export omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            parsed[(case, run)] = observed
            canonical = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(canonical).hexdigest()
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native {case} exports differ after canonical netlist normalization")

        if digest(fixtures[case]) != source_hashes[case]:
            raise ValueError(f"Synthetic {case} schematic changed during native export")

    expected_nets = {
        "control": {
            "U1.1": "CONTROL_ON",
            "U1.2": "RAIL_A",
            "U1.3": "GOOD_A",
            "U2.1": "GOOD_A",
            "U2.2": "RAIL_B",
            "U2.3": "GOOD_B",
        },
        "open-enable": {
            "U1.1": "CONTROL_ON",
            "U1.2": "RAIL_A",
            "U1.3": "GOOD_A",
            "U2.1": "FLOATING_ENABLE",
            "U2.2": "RAIL_B",
            "U2.3": "GOOD_B",
        },
        "output-enable-cycle": {
            "U1.1": "RAIL_B",
            "U1.2": "RAIL_A",
            "U1.3": "GOOD_A",
            "U2.1": "RAIL_A",
            "U2.2": "RAIL_B",
            "U2.3": "GOOD_B",
            "U3.1": "GOOD_B",
            "U3.2": "RAIL_C",
            "U3.3": "GOOD_C",
        },
    }
    expected_components = {
        "control": ("U1", "U2"),
        "open-enable": ("U1", "U2"),
        "output-enable-cycle": ("U1", "U2", "U3"),
    }
    reports: dict[str, DesignLintReport] = {}
    for case in cases:
        observed_cycles: tuple[PowerSequenceObservedCycle, ...] = ()
        observed_cycle_stages = "none"
        observed = parsed[(case, "first")]
        references = expected_components[case]
        for reference in references:
            if observed.component_symbols.get(reference) != "Synthetic:Regulator":
                raise ValueError(
                    f"Native {case} export lost {reference} synthetic regulator symbol identity"
                )
        for reference, suffix in zip(references, ("A", "B", "C"), strict=False):
            component = observed.components.get(reference)
            if (
                component is None
                or component.footprint != "Synthetic:SOT23-5"
                or component.part_id != f"SYNTH-REG-{suffix}"
                or set(observed.component_pin_numbers.get(reference, ())) != {"1", "2", "3"}
            ):
                raise ValueError(
                    f"Native {case} export changed {reference} identity or pin inventory"
                )
        for pin, net in expected_nets[case].items():
            assigned = tuple(
                sorted(candidate for candidate, pins in observed.nets.items() if pin in pins)
            )
            if assigned != (net,):
                raise ValueError(f"Native {case} export maps {pin} to {assigned!r}; expected {net}")
        case_sequence_map = sequence_maps[case]
        issues = power_sequence_mismatches(case_sequence_map, observed)
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=f"synthetic-power-sequence-{case}",
            observed=observed,
            netlist_sha256=raw_hashes[(case, "first")],
        )
        reports[case] = evaluate(
            f"synthetic-power-sequence-{case}",
            coach,
            DesignLintPolicy(power_sequence_map=case_sequence_map),
        )
        if case == "control" and (
            issues or reports[case].findings or reports[case].status != "PASS"
        ):
            raise ValueError("Native power-sequence control did not satisfy its authored map")
        if case == "open-enable":
            findings = tuple(
                finding
                for finding in reports[case].findings
                if finding.rule_id == "power.mapped_sequence_dependency_mismatch"
            )
            if (
                reports[case].status != "REVIEW"
                or len(findings) != 1
                or len(issues) != 1
                or not any(
                    "U2.1 is assigned to FLOATING_ENABLE" in issue for issue in issues[0].issues
                )
            ):
                raise ValueError("Native power-sequence open-enable fault was not localized")
        if case == "output-enable-cycle":
            observed_cycles = power_sequence_observed_enable_cycles(case_sequence_map, observed)
            cycle_findings = tuple(
                finding
                for finding in reports[case].findings
                if finding.rule_id == "power.mapped_sequence_dependency_mismatch"
            )
            if (
                power_sequence_graph_has_cycle(case_sequence_map)
                or issues
                or len(observed_cycles) != 1
                or observed_cycles[0].stage_ids != ("rail-a", "rail-b")
                or reports[case].status != "REVIEW"
                or len(cycle_findings) != 1
                or cycle_findings[0].evidence["observed_output_to_enable_cycle_stages"]
                != ("rail-a, rail-b",)
            ):
                raise ValueError("Native mapped output-to-enable cycle was not localized")
            observed_cycle_stages = ",".join(observed_cycles[0].stage_ids)
        log.event(
            f"power-sequence-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=reports[case].status,
            power_sequence_findings=",".join(finding.rule_id for finding in reports[case].findings)
            or "none",
            observed_enable_net=expected_nets[case]["U2.1"],
            observed_enable_cycle_stages=observed_cycle_stages,
            repeatable="true",
        )
    log.event(
        stage,
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        repeatable="true",
        repeatability_basis="canonical_native_netlist",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )


def ic_rail_capacitor_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Check synthetic IC power-rail faults and controls with native exports and ERC."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.led_heuristics import resolve_component_role_map
    from .hwrepo.models import (
        ComponentRoleBinding,
        ComponentRoleMap,
        ComponentRolePin,
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
    )
    from .hwrepo.power_decoupling import ic_power_rails_without_fitted_capacitors
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"IC rail-capacitor fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/cohort-power-pin-dc"
    )
    cases = {
        "positive-rail-no-cap": "no-cap.kicad_sch",
        "positive-rail-cap-control": "control.kicad_sch",
        "unrecognized-rail-control": "fault.kicad_sch",
        "source-backed-control": "source-backed-control.kicad_sch",
        "source-backed-no-cap": "source-backed-no-cap.kicad_sch",
        "source-backed-dnp-capacitor": "source-backed-dnp-capacitor.kicad_sch",
        "custom-capacitor-role-control": "custom-capacitor-role-control.kicad_sch",
        "custom-capacitor-role-wrong-return": "custom-capacitor-role-wrong-return.kicad_sch",
    }
    source_hashes = {case: digest(fixture_root / name) for case, name in cases.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"ic-rail-capacitor-{project}-", dir=log.directory.resolve())
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
        export_command = (
            f"for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{filename}"; done\n'
        )
        erc_command = (
            f"for run in first repeat; do kicad-cli sch erc --format json --severity-all "
            f'--output "/output/{case}.${{run}}.erc.json" '
            f'"/fixtures/{filename}"; done\n'
        )
        source_lines.extend((export_command, erc_command))
    script = "".join(source_lines)
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
        "HOME=/tmp/kicad-rail-cap-fixtures",
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
        script,
    )
    log.event(
        "ic-rail-cap-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "ic-rail-cap-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native IC rail-capacitor fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        "ic-rail-cap-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    expected_gaps: dict[str, set[tuple[str, tuple[str, ...], tuple[str, ...]]]] = {
        "positive-rail-no-cap": {("+3V3", ("U1.1",), ("U1",))},
        "positive-rail-cap-control": set(),
        "unrecognized-rail-control": set(),
        "source-backed-control": set(),
        "source-backed-no-cap": {("+3V3", ("U1.1",), ("U1",))},
        "source-backed-dnp-capacitor": {("+3V3", ("U1.1",), ("U1",))},
        "custom-capacitor-role-control": set(),
        "custom-capacitor-role-wrong-return": {("+3V3", ("U1.1",), ("U1",))},
    }
    expected_findings: dict[str, set[str]] = {
        "positive-rail-no-cap": {"+3V3: IC supply decoupling review"},
        "positive-rail-cap-control": set(),
        "unrecognized-rail-control": set(),
        "source-backed-control": set(),
        "source-backed-no-cap": {"+3V3: IC supply decoupling review"},
        "source-backed-dnp-capacitor": {"+3V3: IC supply decoupling review"},
        "custom-capacitor-role-control": set(),
        "custom-capacitor-role-wrong-return": {"+3V3: IC supply decoupling review"},
    }
    expected_source_path_findings: dict[str, set[str]] = {
        "positive-rail-no-cap": set(),
        "positive-rail-cap-control": set(),
        "unrecognized-rail-control": {"LOCAL_A: power-input source-path review"},
        "source-backed-control": set(),
        "source-backed-no-cap": set(),
        "source-backed-dnp-capacitor": set(),
        "custom-capacitor-role-control": set(),
        "custom-capacitor-role-wrong-return": set(),
    }
    expected_power_pin_not_driven = {
        "positive-rail-no-cap",
        "positive-rail-cap-control",
        "unrecognized-rail-control",
    }
    custom_capacitor_role_map = ComponentRoleMap(
        entries=(
            ComponentRoleBinding(
                part_id="synthetic-decoupling-capacitor",
                symbol="Vendor:CAP123",
                footprint="Synthetic:CAP123_0603",
                role="capacitor",
                pins=(
                    ComponentRolePin(number="1", function="1", electrical_type="passive"),
                    ComponentRolePin(number="2", function="2", electrical_type="passive"),
                ),
                basis="Synthetic native fixture uses this exact opaque two-pin capacitor identity",
            ),
        )
    )
    normalized_hashes: dict[tuple[str, str], str] = {}
    normalized_erc_hashes: dict[tuple[str, str], str] = {}
    erc_types: dict[tuple[str, str], tuple[str, ...]] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native IC rail-capacitor fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc_path = output / f"{case}.{run}.erc.json"
            if not erc_path.is_file():
                raise ValueError(f"Native IC power-rail fixture omitted {erc_path.name}")
            erc_report = read_kicad_erc_report(erc_path)
            if erc_report.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native {case} ERC report version differs from KiCad {config.kicad_version}"
                )
            violations = erc_report.violations
            erc_types[(case, run)] = tuple(sorted(item.type for item in violations))
            normalized_erc = json.dumps(
                {
                    "kicad_version": erc_report.kicad_version,
                    "violations": sorted(
                        [
                            (
                                item.type,
                                item.severity,
                                item.description,
                                tuple(
                                    sorted(
                                        [
                                            (detail.description, detail.x, detail.y)
                                            for detail in item.items
                                        ],
                                        key=lambda detail: json.dumps(
                                            detail,
                                            sort_keys=True,
                                            separators=(",", ":"),
                                            ensure_ascii=False,
                                        ),
                                    )
                                ),
                            )
                            for item in violations
                        ],
                        key=lambda item: json.dumps(
                            item,
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ),
                    ),
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[(case, run)] = hashlib.sha256(normalized_erc).hexdigest()
            has_undriven_power_pin = "power_pin_not_driven" in erc_types[(case, run)]
            if has_undriven_power_pin != (case in expected_power_pin_not_driven):
                raise ValueError(
                    f"Native {case} ERC power-source result differs from expectation: "
                    f"{erc_types[(case, run)]}"
                )
            erc_error_types = tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "error")
            )
            expected_error_types = (
                ("power_pin_not_driven",) if case in expected_power_pin_not_driven else ()
            )
            if erc_error_types != expected_error_types:
                raise ValueError(
                    f"Native {case} ERC error set differs from expectation: {erc_error_types}"
                )
            policy = (
                DesignLintPolicy(component_role_map=custom_capacitor_role_map)
                if case.startswith("custom-capacitor-role-")
                else DesignLintPolicy()
            )
            role_resolution = resolve_component_role_map(observed, policy.component_role_map)
            if role_resolution.issues:
                raise ValueError(
                    f"Native {case} project capacitor role map is stale: {role_resolution.issues}"
                )
            mapped_capacitor_references = tuple(
                reference
                for reference, binding in role_resolution.by_reference.items()
                if binding.role == "capacitor"
            )
            gaps = {
                (item.net, item.input_pins, item.component_references)
                for item in ic_power_rails_without_fitted_capacitors(
                    observed, mapped_capacitor_references=mapped_capacitor_references
                )
            }
            if gaps != expected_gaps[case]:
                raise ValueError(
                    f"Native {case} rail-capacitor topology differs from expectation: "
                    f"{sorted(gaps)}"
                )
            if case in {
                "source-backed-control",
                "source-backed-no-cap",
                "source-backed-dnp-capacitor",
                "custom-capacitor-role-control",
                "custom-capacitor-role-wrong-return",
            }:
                expected_source_net = (
                    {"U1.1", "U2.1"} if case == "source-backed-no-cap" else {"C1.1", "U1.1", "U2.1"}
                )
                if set(observed.nets.get("+3V3", ())) != expected_source_net:
                    raise ValueError(f"Native {case} does not match its authored +3V3 pin topology")
                if observed.pin_electrical_types.get("U2.1") != "power_out":
                    raise ValueError(f"Native {case} source pin is not power_out")
                if (case == "source-backed-dnp-capacitor") != ("C1" in observed.dnp_components):
                    raise ValueError(
                        f"Native {case} did not preserve the capacitor population state"
                    )
            if case.startswith("custom-capacitor-role-"):
                component = observed.components.get("C1")
                if (
                    component is None
                    or component.part_id != "synthetic-decoupling-capacitor"
                    or component.footprint != "Synthetic:CAP123_0603"
                    or observed.component_symbols.get("C1") != "Vendor:CAP123"
                    or observed.component_pin_numbers.get("C1") != ("1", "2")
                    or observed.pin_functions.get("C1.1") != "1"
                    or observed.pin_functions.get("C1.2") != "2"
                    or observed.pin_electrical_types.get("C1.1") != "passive"
                    or observed.pin_electrical_types.get("C1.2") != "passive"
                ):
                    raise ValueError(
                        f"Native {case} did not preserve the exact project capacitor-role identity"
                    )
                expected_capacitor_reference_net = (
                    "GND" if case == "custom-capacitor-role-control" else "CAP_REF"
                )
                net_by_pin = {
                    pin.casefold(): net for net, pins in observed.nets.items() for pin in pins
                }
                if (
                    net_by_pin.get("c1.1") != "+3V3"
                    or net_by_pin.get("c1.2") != expected_capacitor_reference_net
                ):
                    raise ValueError(f"Native {case} does not match its authored capacitor nets")
            project_id = f"synthetic-ic-rail-capacitor-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, policy)

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native IC rail-capacitor exports differ after normalization to parsed netlist contracts"
        )
    if any(
        normalized_erc_hashes[(case, "first")] != normalized_erc_hashes[(case, "repeat")]
        for case in cases
    ):
        raise ValueError("Native IC power-rail ERC reports differ after normalization")
    for case in cases:
        findings = {
            item.subject
            for item in reports[(case, "first")].findings
            if item.rule_id == "power.ic_rail_without_fitted_capacitor"
        }
        if findings != expected_findings[case]:
            raise ValueError(
                f"Native {case} lint result differs from the rail-capacitor expectation: "
                f"{sorted(findings)}"
            )
        source_path_findings = {
            item.subject
            for item in reports[(case, "first")].findings
            if item.rule_id == "power.input_without_supported_source_path"
        }
        if source_path_findings != expected_source_path_findings[case]:
            raise ValueError(
                f"Native {case} source-anchor/path result differs from expectation: "
                f"{sorted(source_path_findings)}"
            )
        if case == "unrecognized-rail-control":
            source_finding = next(
                item
                for item in reports[(case, "first")].findings
                if item.rule_id == "power.input_without_supported_source_path"
            )
            if source_finding.evidence.get("source_anchor_state") != ("not_recognized",):
                raise ValueError(
                    "Native custom-rail case lost its explicit source-anchor coverage evidence"
                )
        log.event(
            f"ic-rail-cap-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            normalized_erc_sha256=normalized_erc_hashes[(case, "first")],
            repeat_normalized_erc_sha256=normalized_erc_hashes[(case, "repeat")],
            native_erc_types=",".join(erc_types[(case, "first")]) or "none",
            native_erc_error_types=",".join(
                sorted(
                    item.type
                    for item in read_kicad_erc_report(output / f"{case}.first.erc.json").violations
                    if item.severity == "error"
                )
            )
            or "none",
            power_pin_not_driven=("true" if case in expected_power_pin_not_driven else "false"),
            lint_status=reports[(case, "first")].status,
            capacitor_findings=";".join(sorted(findings)) or "none",
            source_path_findings=";".join(sorted(source_path_findings)) or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_and_erc",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(fixture_root / filename) != source_hashes[case] for case, filename in cases.items()
    ):
        raise ValueError("Synthetic IC rail-capacitor fixture source changed during native export")


def native_control_input_demo_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Check unconnected controls in public demos bundled in pinned KiCad 10.0.5."""
    import hashlib

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.control_inputs import (
        connected_control_inputs_without_visible_rail_resistor,
        unconnected_control_inputs,
    )
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .validate import read_netlist

    root = root.resolve()
    expected_image = (
        "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
    )
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version != "10.0.5":
        raise ValueError(
            "Native control-input demo fixtures are pinned to the KiCad 10.0.5 demo corpus"
        )
    if config.image != expected_image:
        raise ValueError("Native control-input demos require the recorded KiCad 10.0.5 image")
    pinned = pinned_image(config.image)
    samples = {
        "cm5-minima": (
            "/usr/share/kicad/demos/cm5_minima",
            "CM5_MINIMA_3.kicad_sch",
            (),
        ),
        "jetson-agx-thor": (
            "/usr/share/kicad/demos/jetson-agx-thor-baseboard",
            "jetson-agx-thor-baseboard.kicad_sch",
            (("J14.23", "SDIO_~{RESET}", "reset", "input"),),
        ),
        "coldfire-xilinx": (
            "/usr/share/kicad/demos/kit-dev-coldfire-xilinx_5213",
            "kit-dev-coldfire-xilinx_5213.kicad_sch",
            (("VR201.4", "SHDN", "enable", "input"),),
        ),
        "vme-wren": (
            "/usr/share/kicad/demos/vme-wren",
            "vme-wren.kicad_sch",
            (
                ("IC19.3", "~{RESET}", "reset", "input"),
                ("IC21.3", "~{RESET}", "reset", "input"),
                ("IC30.33", "BOOT_B", "boot/strap", "input"),
                ("IC30.38", "BOOT_A", "boot/strap", "input"),
            ),
        ),
        "por-alias-fixture": (
            "/synthetic",
            "por-b.kicad_sch",
            (("U1.1", "POR_B", "reset", "input"),),
        ),
    }
    synthetic_fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/control-input-alias"
    )
    if not (synthetic_fixture_root / "por-b.kicad_sch").is_file():
        raise ValueError("Synthetic POR_B native control fixture is missing")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"control-input-demo-{project}-", dir=log.directory.resolve())
    )
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")

    source_lines = [
        'actual="$(kicad-cli version)"\n',
        'printf "kicad_version=%s\\n" "$actual"\n',
        f'test "$actual" = "{config.kicad_version}"\n',
    ]
    for sample, (directory, filename, _expected) in samples.items():
        source = f"{directory}/{filename}"
        source_lines.extend(
            (
                f'cd "{directory}"\n',
                f"find . -type f -name '*.kicad_sch' -print0 | sort -z | xargs -0 sha256sum > \"/output/{sample}.source-manifest.sha256\"\n",
                f'sha256sum "{source}" | cut -d \' \' -f 1 > "/output/{sample}.source.sha256"\n',
                f'kicad-cli sch export netlist --format kicadxml --output "/output/{sample}.first.netlist.xml" "{source}"\n',
                f'kicad-cli sch export netlist --format kicadxml --output "/output/{sample}.repeat.netlist.xml" "{source}"\n',
            )
        )
    script = 'mkdir -p "$HOME"\n' + "".join(source_lines)
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
        "HOME=/tmp/kicad-control-input-demos",
        "-v",
        f"{synthetic_fixture_root}:/synthetic:ro",
        "-v",
        f"{output}:/output:rw",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    log.event(
        "control-input-demo/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        samples=",".join(samples),
    )
    command = run_command(root, argv, timeout=900)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "control-input-demo/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native control demo export failed: {command.stderr or command.error}")
    log.event(
        "control-input-demo/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    for sample, (_directory, _filename, expected) in samples.items():
        candidates_by_run: dict[str, tuple[tuple[str, str, str, str], ...]] = {}
        bias_candidates_by_run: dict[
            str, tuple[tuple[str, tuple[tuple[str, str, str, str], ...], tuple[str, ...]], ...]
        ] = {}
        semantic_hashes: dict[str, str] = {}
        raw_hashes: dict[str, str] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{sample}.{run}.netlist.xml"
            manifest_path = output / f"{sample}.source-manifest.sha256"
            source_path = output / f"{sample}.source.sha256"
            if (
                not netlist_path.is_file()
                or not manifest_path.is_file()
                or not source_path.is_file()
            ):
                raise ValueError(f"Native {sample} demo omitted its source or netlist evidence")
            observed = read_netlist(netlist_path)
            if sample == "por-alias-fixture":
                if observed.pin_functions.get("U1.1") != "POR_B":
                    raise ValueError("Native POR_B fixture did not retain its exact pin function")
                if observed.pin_functions.get("U1.2") != "PORN":
                    raise ValueError("Native PORN negative control did not retain its pin function")
                if observed.pin_electrical_types.get("U1.1") != "input":
                    raise ValueError(
                        "Native POR_B fixture did not retain its input electrical type"
                    )
                if observed.pin_electrical_types.get("U1.2") != "input":
                    raise ValueError("Native PORN control did not retain its input electrical type")
                assigned = {pin.casefold() for pins in observed.nets.values() for pin in pins}
                if {"u1.1", "u1.2"} & assigned:
                    raise ValueError("Native POR alias fixture pins must remain unassigned")
            candidates = unconnected_control_inputs(observed)
            candidates_by_run[run] = tuple(
                (item.pin, item.function, item.family, item.electrical_type) for item in candidates
            )
            bias_candidates_by_run[run] = tuple(
                (
                    gap.net,
                    tuple(
                        (item.pin, item.function, item.family, item.electrical_type)
                        for item in gap.controls
                    ),
                    gap.output_capable_peers,
                )
                for gap in connected_control_inputs_without_visible_rail_resistor(observed)
            )
            raw_hashes[run] = digest(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            semantic_hashes[run] = hashlib.sha256(normalized).hexdigest()

        if candidates_by_run["first"] != expected or candidates_by_run["repeat"] != expected:
            raise ValueError(
                f"Native {sample} control findings changed: "
                f"first={candidates_by_run['first']}, repeat={candidates_by_run['repeat']}"
            )
        if bias_candidates_by_run["first"] != bias_candidates_by_run["repeat"]:
            raise ValueError(
                f"Native {sample} connected-control bias candidates changed between exports"
            )
        if semantic_hashes["first"] != semantic_hashes["repeat"]:
            raise ValueError(f"Native {sample} parsed netlist changed between repeated exports")

        manifest = output / f"{sample}.source-manifest.sha256"
        source_digest = output / f"{sample}.source.sha256"
        candidate_text = ";".join("|".join(item) for item in expected) or "none"
        bias_candidate_records = [
            {
                "net": net,
                "controls": [
                    {
                        "pin": pin,
                        "function": function,
                        "family": family,
                        "electrical_type": electrical_type,
                    }
                    for pin, function, family, electrical_type in controls
                ],
                "output_capable_peers": list(peers),
            }
            for net, controls, peers in bias_candidates_by_run["first"]
        ]
        bias_candidate_json = json.dumps(
            bias_candidate_records,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        bias_candidate_sha256 = hashlib.sha256(bias_candidate_json.encode("utf-8")).hexdigest()
        log.event(
            f"control-input-demo/{sample}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_digest.read_text(encoding="utf-8").strip(),
            source_manifest_sha256=digest(manifest),
            source_manifest_entries=str(len(manifest.read_text(encoding="utf-8").splitlines())),
            raw_netlist_sha256=raw_hashes["first"],
            repeat_raw_netlist_sha256=raw_hashes["repeat"],
            normalized_netlist_sha256=semantic_hashes["first"],
            repeat_normalized_netlist_sha256=semantic_hashes["repeat"],
            review_candidates=candidate_text,
            connected_bias_candidate_count=str(len(bias_candidate_records)),
            connected_bias_candidates_sha256=bias_candidate_sha256,
            connected_bias_candidates=bias_candidate_json,
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )


def pcb_return_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Exercise native return evidence on synthetic PCB path fixtures."""
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        PcbReturnBondRequirement,
        PcbReturnDomainRequirement,
        PcbReturnEndpointRequirement,
        PcbReturnPathsAnalysis,
    )
    from .hwrepo.pcb_return_paths import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
        pcb_return_path_checks,
    )

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"PCB return-path native fixtures do not cover KiCad {config.kicad_version}"
        )

    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    fixtures = (
        (
            "alternate-layer-via",
            "pcb-return-alternate-layer-via.kicad_pcb",
            "direct",
            True,
            None,
            None,
            None,
            None,
        ),
        (
            "alternate-layer-open",
            "pcb-return-alternate-layer-open.kicad_pcb",
            "direct",
            False,
            None,
            None,
            None,
            None,
        ),
        (
            "zone-connected",
            "pcb-return-zone-connected.kicad_pcb",
            "direct",
            True,
            1,
            (0, 0),
            None,
            None,
        ),
        (
            "zone-unanchored-island",
            "pcb-return-zone-unanchored-island.kicad_pcb",
            "direct",
            True,
            2,
            None,
            None,
            None,
        ),
        ("zone-split", "pcb-return-zone-split.kicad_pcb", "direct", False, 2, (0, 1), None, None),
        (
            "zone-through-hole-split",
            "pcb-return-zone-through-hole-split.kicad_pcb",
            "direct",
            False,
            2,
            (0, 1),
            None,
            None,
        ),
        (
            "net-tie-connected",
            "pcb-return-net-tie-connected.kicad_pcb",
            "bond",
            True,
            None,
            None,
            False,
            None,
        ),
        ("net-tie-dnp", "pcb-return-net-tie-dnp.kicad_pcb", "bond", False, None, None, True, None),
        (
            "isolation-open",
            "pcb-return-isolation-open.kicad_pcb",
            "isolation",
            True,
            None,
            None,
            None,
            True,
        ),
        (
            "isolation-bridged",
            "pcb-return-isolation-bridged.kicad_pcb",
            "isolation",
            True,
            None,
            None,
            False,
            False,
        ),
    )
    for (
        fixture_id,
        fixture_name,
        scenario,
        expected_connected,
        expected_islands,
        expected_island_indices,
        expected_tie_dnp,
        expected_isolated,
    ) in fixtures:
        scratch = Path(
            tempfile.mkdtemp(prefix=f"pcb-return-{project}-", dir=log.directory.resolve())
        )
        relative_project = scratch.relative_to(root) / f"{fixture_id}.kicad_pro"
        board = root / relative_project.with_suffix(".kicad_pcb")
        shutil.copyfile(fixture_root / fixture_name, board)
        fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
        receipt = scratch / "receipt"
        try:
            if scenario == "direct":
                topology = PcbReturnDomainRequirement(
                    id=fixture_id,
                    basis="Synthetic fixture asserts only its stated direct same-net path",
                    topology="direct",
                    endpoints=(
                        PcbReturnEndpointRequirement(
                            pad="J1.1", net="RETURN", footprint="Synthetic:TestPad"
                        ),
                        PcbReturnEndpointRequirement(
                            pad="J2.1", net="RETURN", footprint="Synthetic:TestPad"
                        ),
                    ),
                )
                domains = (topology,)
            elif scenario == "bond":
                topology = PcbReturnDomainRequirement(
                    id=fixture_id,
                    basis="Synthetic fixture asserts an exact fitted KiCad net-tie bond",
                    topology="bonded",
                    endpoints=(
                        PcbReturnEndpointRequirement(
                            pad="J1.1", net="RETURN_A", footprint="Synthetic:TestPad"
                        ),
                        PcbReturnEndpointRequirement(
                            pad="J2.1", net="RETURN_B", footprint="Synthetic:TestPad"
                        ),
                    ),
                    bonds=(
                        PcbReturnBondRequirement(
                            reference="NT1",
                            footprint="Synthetic:NetTie-2",
                            pad_groups=(("NT1.1", "NT1.2"),),
                        ),
                    ),
                )
                domains = (topology,)
            else:
                domains = (
                    PcbReturnDomainRequirement(
                        id="isolation-a",
                        basis="Synthetic fixture asserts two connected endpoints in return domain A",
                        topology="direct",
                        endpoints=(
                            PcbReturnEndpointRequirement(
                                pad="J1.1", net="RETURN_A", footprint="Synthetic:TestPad"
                            ),
                            PcbReturnEndpointRequirement(
                                pad="J3.1", net="RETURN_A", footprint="Synthetic:TestPad"
                            ),
                        ),
                    ),
                    PcbReturnDomainRequirement(
                        id="isolation-b",
                        basis="Synthetic fixture asserts two connected endpoints in return domain B",
                        topology="direct",
                        endpoints=(
                            PcbReturnEndpointRequirement(
                                pad="J2.1", net="RETURN_B", footprint="Synthetic:TestPad"
                            ),
                            PcbReturnEndpointRequirement(
                                pad="J4.1", net="RETURN_B", footprint="Synthetic:TestPad"
                            ),
                        ),
                    ),
                )
            requirement = PcbReturnPathsAnalysis(
                basis="Synthetic native PCB return-path fixture",
                domains=domains,
            )
            command, snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
            if command.returncode != 0 or command.error is not None:
                raise ValueError(
                    f"Native PCB fixture command failed: {command.stderr or command.error}"
                )
            if not native_pcb_command_matches(command, fixture_config):
                raise ValueError(
                    "Native PCB fixture did not use the pinned read-only probe command"
                )
            if snapshot is None:
                raise ValueError("Native PCB fixture returned no connectivity snapshot")

            checks = pcb_return_path_checks(
                requirement,
                snapshot,
                board_sha256=digest(board),
                kicad_version=config.kicad_version,
                image=config.image,
                probe_sha256=expected_probe_sha256(),
            )
            by_pad = {item.pad.casefold(): item for item in snapshot.pads}
            first = by_pad.get("j1.1")
            second = by_pad.get("j2.1")
            is_via_fixture = fixture_id.startswith("alternate-layer-")
            observed_connected = (
                first is not None
                and second is not None
                and "j2.1" in {pad.casefold() for pad in first.connected_pads}
                and "j1.1" in {pad.casefold() for pad in second.connected_pads}
            )
            connectivity_id = f"pcb-return-paths/{fixture_id}/connectivity"
            connectivity_check = next(
                (check for check in checks if check.id == connectivity_id), None
            )
            failures: list[str] = []
            via_identity_repeatable = False
            if is_via_fixture:
                observed_via = snapshot.vias[0] if len(snapshot.vias) == 1 else None
                if (
                    observed_via is None
                    or observed_via.net != "RETURN"
                    or (observed_via.x_nm, observed_via.y_nm) != (10_000_000, 5_000_000)
                    or (observed_via.start_layer, observed_via.end_layer) != ("F.Cu", "B.Cu")
                    or (observed_via.diameter_nm, observed_via.drill_nm) != (800_000, 300_000)
                    or observed_via.kind != "through"
                    or observed_via.multiplicity != 1
                ):
                    failures.append(
                        "Via fixture does not retain the exact stable geometry and layer transition"
                    )
                elif (
                    first is None
                    or second is None
                    or observed_via.id not in first.connected_vias
                    or ((observed_via.id in second.connected_vias) != expected_connected)
                ):
                    failures.append(
                        "Via fixture component membership differs from its connected/open topology"
                    )
                if observed_via is not None:
                    front_tracks = tuple(
                        item for item in snapshot.tracks if item.layer.casefold() == "f.cu"
                    )
                    back_tracks = tuple(
                        item for item in snapshot.tracks if item.layer.casefold() == "b.cu"
                    )
                    front_contact_ok = any(
                        item.geometry_kind == "segment"
                        and item.start_pads == ("J1.1",)
                        and item.end_vias == (observed_via.id,)
                        for item in front_tracks
                    )
                    back_contact_ok = any(
                        item.geometry_kind == "segment"
                        and item.start_vias == (observed_via.id,)
                        and item.end_pads == ("J2.1",)
                        for item in back_tracks
                    )
                    if not front_contact_ok or (back_contact_ok != expected_connected):
                        failures.append(
                            "Native track endpoint contacts differ from the fixture's pad/via path"
                        )
                if (
                    connectivity_check is None
                    or (
                        observed_via is not None
                        and observed_via.id not in connectivity_check.detail
                    )
                    or "F.Cu to B.Cu" not in connectivity_check.detail
                    or "no serial route inferred" not in connectivity_check.detail
                    or (
                        not expected_connected
                        and "J2.1: no component vias observed" not in connectivity_check.detail
                    )
                ):
                    failures.append(
                        "Via fixture return report omits its component membership or layer transition"
                    )
                if fixture_id == "alternate-layer-via":
                    repeated_command, repeated_snapshot = capture_native_pcb_connectivity(
                        root, fixture_config, scratch / "receipt-repeat"
                    )
                    if (
                        repeated_command.returncode != 0
                        or repeated_command.error is not None
                        or not native_pcb_command_matches(repeated_command, fixture_config)
                        or repeated_snapshot is None
                    ):
                        failures.append("Repeated native via probe did not produce valid evidence")
                    else:
                        first_membership = {
                            item.pad.casefold(): item.connected_vias for item in snapshot.pads
                        }
                        repeated_membership = {
                            item.pad.casefold(): item.connected_vias
                            for item in repeated_snapshot.pads
                        }
                        via_identity_repeatable = (
                            snapshot.vias == repeated_snapshot.vias
                            and first_membership == repeated_membership
                        )
                        if not via_identity_repeatable:
                            failures.append(
                                "Via geometry identity or component membership changed across identical native loads"
                            )
            expected_statuses: dict[str, str] = {}
            if scenario == "isolation":
                expected_statuses.update(
                    {
                        "pcb-return-paths/isolation-a/connectivity": "PASS",
                        "pcb-return-paths/isolation-b/connectivity": "PASS",
                        "pcb-return-paths/isolation/isolation-a/isolation-b": (
                            "PASS" if expected_isolated else "FAIL"
                        ),
                    }
                )
            else:
                connectivity_id = f"pcb-return-paths/{fixture_id}/connectivity"
                expected_connectivity_status = "PASS" if expected_connected else "FAIL"
                expected_statuses[connectivity_id] = expected_connectivity_status
            if scenario == "bond" and expected_tie_dnp is not None:
                expected_statuses[f"pcb-return-paths/{fixture_id}/bond/NT1"] = (
                    "FAIL" if expected_tie_dnp else "PASS"
                )
            failures.extend(
                [
                    f"{check.id}: {check.detail}"
                    for check in checks
                    if check.status != expected_statuses.get(check.id, "PASS")
                ]
            )
            if scenario == "direct" and observed_connected != expected_connected:
                failures.append(
                    "Native copper pad membership does not match the fixture's declared topology"
                )
            if expected_tie_dnp is not None:
                observed_ties = {item.reference.casefold(): item for item in snapshot.net_ties}
                tie = observed_ties.get("nt1")
                if (
                    tie is None
                    or tie.footprint != "Synthetic:NetTie-2"
                    or tie.dnp != expected_tie_dnp
                    or tie.pad_groups != (("NT1.1", "NT1.2"),)
                ):
                    failures.append(
                        "Native net-tie inventory differs from the fixture's exact reference, footprint, DNP state, or pad group"
                    )
                if first is None or second is None:
                    failures.append("Net-tie fixture is missing a reviewed connector pad")
                elif (
                    "nt1.1" not in {pad.casefold() for pad in first.connected_pads}
                    or "nt1.2" not in {pad.casefold() for pad in second.connected_pads}
                    or "j2.1" in {pad.casefold() for pad in first.connected_pads}
                    or "j1.1" in {pad.casefold() for pad in second.connected_pads}
                ):
                    failures.append(
                        "Native net-tie fixture does not retain its two separate endpoint copper groups"
                    )
                if scenario == "bond":
                    connectivity_check = next(
                        (check for check in checks if check.id.endswith("/connectivity")), None
                    )
                    if connectivity_check is None or (
                        (connectivity_check.status == "PASS") != (not expected_tie_dnp)
                    ):
                        failures.append(
                            "Bonded return result does not match the native fitted/DNP net-tie state"
                        )
            if scenario == "isolation":
                by_pad = {item.pad.casefold(): item for item in snapshot.pads}
                isolation_pads = {
                    name: by_pad.get(f"{name}.1".casefold()) for name in ("J1", "J2", "J3", "J4")
                }
                group_a = (
                    isolation_pads["J1"] is not None
                    and isolation_pads["J3"] is not None
                    and "j3.1" in {pad.casefold() for pad in isolation_pads["J1"].connected_pads}
                    and "j1.1" in {pad.casefold() for pad in isolation_pads["J3"].connected_pads}
                )
                group_b = (
                    isolation_pads["J2"] is not None
                    and isolation_pads["J4"] is not None
                    and "j4.1" in {pad.casefold() for pad in isolation_pads["J2"].connected_pads}
                    and "j2.1" in {pad.casefold() for pad in isolation_pads["J4"].connected_pads}
                )
                crosses_groups = any(
                    pad is not None
                    and any(
                        other.casefold() in {member.casefold() for member in pad.connected_pads}
                        for other in opposite
                    )
                    for pad, opposite in (
                        (isolation_pads["J1"], ("J2.1", "J4.1")),
                        (isolation_pads["J3"], ("J2.1", "J4.1")),
                        (isolation_pads["J2"], ("J1.1", "J3.1")),
                        (isolation_pads["J4"], ("J1.1", "J3.1")),
                    )
                )
                if not group_a or not group_b or crosses_groups:
                    failures.append(
                        "Native isolation fixture does not retain two complete, separate same-net copper groups"
                    )
                isolation_check = next(
                    (
                        check
                        for check in checks
                        if check.id == "pcb-return-paths/isolation/isolation-a/isolation-b"
                    ),
                    None,
                )
                if isolation_check is None or (
                    (isolation_check.status == "PASS") != bool(expected_isolated)
                ):
                    failures.append(
                        "Native isolation result differs from the fixture's declared separation state"
                    )
            if expected_islands is not None:
                if len(snapshot.zones) != 1:
                    failures.append(
                        f"Expected one native zone observation, found {len(snapshot.zones)}"
                    )
                elif snapshot.zones[0].filled_island_count != expected_islands:
                    failures.append(
                        "Native filled-island count differs from the fixture: "
                        f"expected {expected_islands}, found {snapshot.zones[0].filled_island_count}"
                    )
                elif fixture_id == "zone-unanchored-island":
                    zone = snapshot.zones[0]
                    first_indexes: set[int] = set()
                    second_indexes: set[int] = set()
                    if first is not None:
                        first_indexes = {
                            island.island_index
                            for island in first.connected_islands
                            if (island.uuid.casefold(), island.layer.casefold())
                            == (zone.uuid.casefold(), zone.layer.casefold())
                        }
                    if second is not None:
                        second_indexes = {
                            island.island_index
                            for island in second.connected_islands
                            if (island.uuid.casefold(), island.layer.casefold())
                            == (zone.uuid.casefold(), zone.layer.casefold())
                        }
                    if (
                        len(zone.unanchored_pad_island_indexes) != 1
                        or len(first_indexes) != 1
                        or first_indexes != second_indexes
                        or first_indexes & set(zone.unanchored_pad_island_indexes)
                    ):
                        failures.append(
                            "Native zone fixture must retain one separate island without a pad anchor"
                        )
                elif snapshot.zones[0].unanchored_pad_island_indexes:
                    failures.append(
                        "Native zone fixture unexpectedly has an island without a pad anchor"
                    )
                if first is None or second is None:
                    failures.append("Zone fixture is missing a reviewed connector pad")
                elif (
                    len(first.connected_zones) != 1
                    or len(second.connected_zones) != 1
                    or first.connected_zones != second.connected_zones
                ):
                    failures.append(
                        "Zone fixture pads do not retain their shared native zone identity"
                    )
                if expected_island_indices is not None:
                    observed_indices = (
                        tuple(item.island_index for item in first.connected_islands)
                        if first is not None
                        else (),
                        tuple(item.island_index for item in second.connected_islands)
                        if second is not None
                        else (),
                    )
                    expected_indices = (
                        (expected_island_indices[0],),
                        (expected_island_indices[1],),
                    )
                    if observed_indices != expected_indices:
                        failures.append(
                            "Native pad-to-island mapping differs from the fixture: "
                            f"expected {expected_indices}, found {observed_indices}"
                        )
                if connectivity_check is None or (
                    snapshot.zones
                    and (
                        snapshot.zones[0].uuid not in connectivity_check.detail
                        or f"filled islands={expected_islands}" not in connectivity_check.detail
                        or (
                            fixture_id == "zone-unanchored-island"
                            and snapshot.zones
                            and (
                                "unanchored to pad indexes="
                                f"{list(snapshot.zones[0].unanchored_pad_island_indexes)}"
                            )
                            not in connectivity_check.detail
                        )
                        or (
                            expected_island_indices is not None
                            and any(
                                f"connected island indexes=[{index}]"
                                not in connectivity_check.detail
                                for index in expected_island_indices
                            )
                        )
                    )
                ):
                    failures.append(
                        "Native return-path finding omits the zone identity or island-count evidence"
                    )
                if (
                    not expected_connected
                    and first is not None
                    and second is not None
                    and set(first.connected_pads) & set(second.connected_pads)
                ):
                    failures.append(
                        "Split-plane fixture pads unexpectedly share native copper connectivity"
                    )
            if failures:
                raise ValueError("Native PCB return fixture failed: " + "; ".join(failures))
        except Exception as exc:
            log.event(
                f"pcb-return-fixture/{fixture_id}",
                "FAIL",
                project=project,
                kicad_version=config.kicad_version,
                error=str(exc),
            )
            raise
        if expected_islands is None:
            event_fields: dict[str, str | float] = {
                "project": project,
                "kicad_version": config.kicad_version,
                "expected_connectivity": "connected" if expected_connected else "open",
                "receipt": receipt.relative_to(root).as_posix(),
            }
            if expected_isolated is not None:
                event_fields["expected_isolation"] = "separate" if expected_isolated else "bridged"
            if fixture_id == "alternate-layer-via":
                event_fields["via_identity_repeatable"] = (
                    "true" if via_identity_repeatable else "false"
                )
            log.event(
                f"pcb-return-fixture/{fixture_id}",
                "PASS",
                **event_fields,
            )
        else:
            log.event(
                f"pcb-return-fixture/{fixture_id}",
                "PASS",
                project=project,
                kicad_version=config.kicad_version,
                expected_connectivity="connected" if expected_connected else "open",
                filled_island_count=expected_islands,
                receipt=receipt.relative_to(root).as_posix(),
            )


def pcb_access_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Exercise native pad exposure and probe-envelope evidence on a synthetic PCB."""
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        PcbAccessAnalysis,
        PcbAccessProbeObservation,
        RequiredTestAccess,
        TestAccessAnalysis,
        TestAccessEndpointRequirement,
        TestAccessProbeEnvelope,
    )
    from .hwrepo.pcb_return_paths import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
    )
    from .hwrepo.test_access import (
        pcb_access_probe_request_set,
        pcb_probe_envelope_checks,
    )

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"PCB probe-envelope native fixtures do not cover KiCad {config.kicad_version}"
        )

    def endpoint(
        reference: str,
        net: str,
        *,
        approach_side: Literal["front", "back", "either"],
        tip_diameter_mm: float,
        clearance_mm: float,
    ) -> TestAccessEndpointRequirement:
        return TestAccessEndpointRequirement(
            kind="test_point",
            reference=reference,
            symbol="Synthetic:AccessTarget",
            footprint="Synthetic:AccessTarget",
            pin=f"{reference}.1",
            electrical_type="passive",
            approach_side=approach_side,
            probe_envelope=TestAccessProbeEnvelope(
                tip_diameter_mm=tip_diameter_mm,
                clearance_mm=clearance_mm,
            ),
        )

    spec = TestAccessAnalysis(
        basis="Synthetic native PCB probe-envelope regression fixture",
        pcb_accessibility=PcbAccessAnalysis(
            basis="Synthetic native API fixture checks pad surface geometry only"
        ),
        decisions=(
            RequiredTestAccess(
                mode="required",
                id="front-back-boundary",
                basis="Synthetic either-side envelope uses one passing surface",
                net="TARGET_ACCESS",
                endpoints=(
                    endpoint(
                        "J1",
                        "TARGET_ACCESS",
                        approach_side="either",
                        tip_diameter_mm=0.8,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="unconnected-obstacle",
                basis="Synthetic no-net pad remains an observed obstacle",
                net="TARGET_NO_NET_NEIGHBOR",
                endpoints=(
                    endpoint(
                        "J7",
                        "TARGET_NO_NET_NEIGHBOR",
                        approach_side="front",
                        tip_diameter_mm=0.6,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="front-only-clearance-fault",
                basis="Synthetic one-sided access cannot pass using an unavailable side",
                net="TARGET_FRONT_ONLY",
                endpoints=(
                    endpoint(
                        "J9",
                        "TARGET_FRONT_ONLY",
                        approach_side="either",
                        tip_diameter_mm=0.8,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="undersize-aperture-fault",
                basis="Synthetic circular aperture is smaller than the declared probe tip envelope",
                net="TARGET_APERTURE_SMALL",
                endpoints=(
                    endpoint(
                        "J11",
                        "TARGET_APERTURE_SMALL",
                        approach_side="front",
                        tip_diameter_mm=0.6,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="aperture-fit-boundary-control",
                basis="Synthetic aperture exactly matches the declared tip-plus-clearance diameter",
                net="TARGET_APERTURE_BOUNDARY",
                endpoints=(
                    endpoint(
                        "J12",
                        "TARGET_APERTURE_BOUNDARY",
                        approach_side="front",
                        tip_diameter_mm=0.6,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="rectangular-aperture-unsupported",
                basis="Synthetic rectangular target stays outside the circular fit predicate",
                net="TARGET_APERTURE_RECT",
                endpoints=(
                    endpoint(
                        "J13",
                        "TARGET_APERTURE_RECT",
                        approach_side="front",
                        tip_diameter_mm=0.6,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="drilled-aperture-unsupported",
                basis="Synthetic drilled target stays outside the circular fit predicate",
                net="TARGET_APERTURE_DRILLED",
                endpoints=(
                    endpoint(
                        "J14",
                        "TARGET_APERTURE_DRILLED",
                        approach_side="front",
                        tip_diameter_mm=0.6,
                        clearance_mm=0.1,
                    ),
                ),
            ),
        ),
    )
    requests = pcb_access_probe_request_set(spec)
    if requests is None:
        raise ValueError("Synthetic PCB access fixture produced no native probe requests")

    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(tempfile.mkdtemp(prefix=f"pcb-access-{project}-", dir=log.directory.resolve()))
    relative_project = scratch.relative_to(root) / "probe-envelope.kicad_pro"
    board = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(fixture_root / "pcb-access-probe-envelope.kicad_pcb", board)
    source_hash = digest(board)
    fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
    expected_statuses = {
        "test-access/pcb-probe-envelope/front-back-boundary": "PASS",
        "test-access/pcb-probe-envelope/unconnected-obstacle": "PASS",
        "test-access/pcb-probe-envelope/front-only-clearance-fault": "FAIL",
        "test-access/pcb-probe-envelope/undersize-aperture-fault": "FAIL",
        "test-access/pcb-probe-envelope/aperture-fit-boundary-control": "PASS",
        "test-access/pcb-probe-envelope/rectangular-aperture-unsupported": "FAIL",
        "test-access/pcb-probe-envelope/drilled-aperture-unsupported": "FAIL",
    }
    expected_observations = {
        ("j1.1", "front"): ("J4.1", "FOREIGN_FRONT", 400_000, True, "circle", 1_200_000),
        ("j1.1", "back"): ("J5.1", "FOREIGN_BACK", 800_000, True, "circle", 1_200_000),
        ("j7.1", "front"): ("J8.1", None, 400_000, True, "circle", 800_000),
        ("j9.1", "front"): (
            "J10.1",
            "FOREIGN_FRONT_ONLY",
            400_000,
            True,
            "circle",
            300_000,
        ),
        ("j9.1", "back"): (None, None, None, False, None, None),
        ("j11.1", "front"): (
            "J12.1",
            "TARGET_APERTURE_BOUNDARY",
            9_500_001,
            True,
            "circle",
            400_000,
        ),
        ("j12.1", "front"): (
            "J13.1",
            "TARGET_APERTURE_RECT",
            9_500_000,
            True,
            "circle",
            800_000,
        ),
        ("j13.1", "front"): (
            "J12.1",
            "TARGET_APERTURE_BOUNDARY",
            9_500_001,
            True,
            "unsupported",
            None,
        ),
        ("j14.1", "front"): (
            "J13.1",
            "TARGET_APERTURE_RECT",
            9_500_000,
            True,
            "unsupported",
            None,
        ),
    }
    try:
        retained_observations: tuple[PcbAccessProbeObservation, ...] | None = None
        for repeat in ("first", "repeat"):
            receipt = scratch / f"receipt-{repeat}"
            command, snapshot = capture_native_pcb_connectivity(
                root, fixture_config, receipt, requests
            )
            if command.returncode != 0 or command.error is not None:
                raise ValueError(
                    f"Native PCB access fixture command failed: {command.stderr or command.error}"
                )
            if not native_pcb_command_matches(command, fixture_config, access_probes=True):
                raise ValueError(
                    "Native access fixture did not use the pinned read-only probe command"
                )
            if snapshot is None:
                raise ValueError("Native PCB access fixture returned no connectivity snapshot")
            request_path = receipt / "access-probe-requests.json"
            if (
                snapshot.board_sha256 != source_hash
                or snapshot.kicad_version != config.kicad_version
                or snapshot.image != config.image
                or snapshot.probe_sha256 != expected_probe_sha256()
                or snapshot.access_probe_requests_sha256 != digest(request_path)
                or not snapshot.zones_refilled
            ):
                raise ValueError("Native access fixture evidence is not bound to its exact inputs")

            observations = {
                (item.endpoint.casefold(), item.side): item
                for item in snapshot.access_probe_observations
            }
            if len(observations) != len(snapshot.access_probe_observations):
                raise ValueError("Native access fixture returned duplicate endpoint surfaces")
            if set(observations) != set(expected_observations):
                raise ValueError(
                    "Native access fixture surfaces differ from the synthetic request inventory"
                )
            for key, expected in expected_observations.items():
                item = observations[key]
                observed = (
                    item.obstacle,
                    item.obstacle_net,
                    item.distance_nm,
                    item.target_exposed,
                    item.target_aperture_shape,
                    item.target_aperture_diameter_nm,
                )
                if observed != expected:
                    raise ValueError(
                        f"Native probe geometry for {key[0]} {key[1]} differs from its fixture: "
                        f"expected {expected}, found {observed}"
                    )

            checks = {item.id: item.status for item in pcb_probe_envelope_checks(spec, snapshot)}
            if checks != expected_statuses:
                raise ValueError(
                    "Probe-envelope fault/control results differ from the synthetic expectations: "
                    f"expected {expected_statuses}, found {checks}"
                )
            if retained_observations is None:
                retained_observations = snapshot.access_probe_observations
            elif retained_observations != snapshot.access_probe_observations:
                raise ValueError(
                    "Repeated native probe geometry changed for identical board inputs"
                )

        log.event(
            "pcb-access-fixture/probe-envelope",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            checks="3 PASS, 4 expected FAIL",
            repeatable="true",
            receipt=(scratch.relative_to(root) / "receipt-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-access-fixture/probe-envelope",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            error=str(exc),
        )
        raise


def pcb_decoupling_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Check native pad geometry and source-mapped PCB controls on synthetic copper."""
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        PcbDecouplingCapacitor,
        PcbDecouplingMap,
        PcbDecouplingRequirement,
        PcbProtectionPathMap,
        PcbProtectionPathRequirement,
        PcbTrackWidthMap,
        PcbTrackWidthRequirement,
    )
    from .hwrepo.pcb_decoupling import pcb_decoupling_entries
    from .hwrepo.pcb_protection_path import pcb_protection_path_entries
    from .hwrepo.pcb_return_paths import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
    )
    from .hwrepo.pcb_track_width import pcb_track_width_entries

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"PCB decoupling native fixtures do not cover KiCad {config.kicad_version}"
        )
    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(
        tempfile.mkdtemp(prefix=f"pcb-decoupling-{project}-", dir=log.directory.resolve())
    )
    relative_project = scratch.relative_to(root) / "decoupling.kicad_pro"
    board = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(fixture_root / "pcb-decoupling-placement.kicad_pcb", board)
    source_hash = digest(board)
    fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
    protection_project = relative_project.with_name("protection.kicad_pro")
    protection_board = root / protection_project.with_suffix(".kicad_pcb")
    shutil.copyfile(fixture_root / "pcb-protection-entry-path.kicad_pcb", protection_board)
    protection_source_hash = digest(protection_board)
    protection_fixture_config = config.model_copy(update={"project": protection_project.as_posix()})
    capacitor_candidates = (
        PcbDecouplingCapacitor(
            reference="C1",
            footprint="Synthetic:Cap_0603",
            supply_pad="C1.1",
            return_pad="C1.2",
        ),
        PcbDecouplingCapacitor(
            reference="C2",
            footprint="Synthetic:Cap_0603",
            supply_pad="C2.1",
            return_pad="C2.2",
        ),
    )
    requirement = PcbDecouplingRequirement(
        id="synthetic-vdd",
        basis="Native fault/control fixture; 1000 um is an exact test boundary, not a design recommendation",
        ic_reference="U1",
        ic_footprint="Synthetic:IC_QFN",
        supply_pad="U1.1",
        return_pad="U1.2",
        supply_net="VDD",
        return_net="GND",
        capacitors=capacitor_candidates,
        selection="any",
        max_distance_um=1000,
        max_return_via_distance_um=1000,
    )
    placement_map = PcbDecouplingMap(
        basis="Synthetic native PCB geometry and connectivity regression",
        requirements=(requirement,),
    )
    protection_requirement = PcbProtectionPathRequirement(
        id="synthetic-data-protection",
        connector_reference="J1",
        connector_footprint="Synthetic:Conn1",
        connector_signal_pad="J1.1",
        protection_reference="D1",
        protection_footprint="Synthetic:TVS",
        protection_signal_pad="D1.1",
        protection_reference_pad="D1.2",
        signal_net="DATA",
        reference_net="GND",
        max_entry_distance_um=650,
        minimum_reference_vias=1,
        reference_via_radius_um=2000,
    )
    protection_map = PcbProtectionPathMap(
        basis="Synthetic native connector-to-protector pad and connected-via regression",
        requirements=(protection_requirement,),
    )
    width_boundary_map = PcbTrackWidthMap(
        basis="Synthetic exact-width boundary control",
        requirements=(
            PcbTrackWidthRequirement(
                id="vdd-boundary",
                basis="Synthetic 250 um boundary fixture",
                net="VDD",
                minimum_width_um=250,
            ),
        ),
    )
    width_fault_map = PcbTrackWidthMap(
        basis="Synthetic below-width fault control",
        requirements=(
            PcbTrackWidthRequirement(
                id="vdd-fault",
                basis="Synthetic 251 um threshold against a 250 um track",
                net="VDD",
                minimum_width_um=251,
            ),
        ),
    )
    try:
        retained_snapshot = None
        retained_protection_snapshot = None
        for repeat in ("first", "repeat"):
            receipt = scratch / f"receipt-{repeat}"
            command, snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
            if command.returncode != 0 or command.error is not None:
                raise ValueError(
                    f"Native PCB decoupling fixture command failed: {command.stderr or command.error}"
                )
            if not native_pcb_command_matches(command, fixture_config):
                raise ValueError(
                    "Native decoupling fixture did not use the pinned read-only probe command"
                )
            if snapshot is None:
                raise ValueError("Native PCB decoupling fixture returned no connectivity snapshot")
            if (
                snapshot.schema_version != "10"
                or snapshot.board_sha256 != source_hash
                or snapshot.kicad_version != config.kicad_version
                or snapshot.image != config.image
                or snapshot.probe_sha256 != expected_probe_sha256()
                or not snapshot.zones_refilled
                or snapshot.copper_layers[0].casefold() != "f.cu"
                or snapshot.copper_layers[-1].casefold() != "b.cu"
            ):
                raise ValueError(
                    "Native PCB fixture evidence is not bound to its exact source and copper stack"
                )
            protection_receipt = scratch / f"protection-{repeat}"
            protection_command, protection_snapshot = capture_native_pcb_connectivity(
                root, protection_fixture_config, protection_receipt
            )
            if protection_command.returncode != 0 or protection_command.error is not None:
                raise ValueError(
                    "Native PCB protection-path fixture command failed: "
                    f"{protection_command.stderr or protection_command.error}"
                )
            if not native_pcb_command_matches(protection_command, protection_fixture_config):
                raise ValueError(
                    "Native protection-path fixture did not use the pinned read-only probe"
                )
            if (
                protection_snapshot is None
                or protection_snapshot.schema_version != "10"
                or protection_snapshot.board_sha256 != protection_source_hash
                or protection_snapshot.kicad_version != config.kicad_version
                or protection_snapshot.image != config.image
                or protection_snapshot.probe_sha256 != expected_probe_sha256()
                or not protection_snapshot.zones_refilled
            ):
                raise ValueError(
                    "Native PCB protection-path evidence is not bound to its exact source and tool"
                )
            protection_entries = pcb_protection_path_entries(protection_map, protection_snapshot)
            if (
                len(protection_entries) != 1
                or protection_entries[0].status != "COMPLETE"
                or not protection_entries[0].native_signal_path_connected
                or protection_entries[0].connector_to_protection_distance_nm != 650_000
                or protection_entries[0].connected_reference_via_count != 1
                or protection_entries[0].reference_vias_within_radius != 1
            ):
                raise ValueError(
                    f"Native protection path fault/control result changed: {protection_entries}"
                )
            distance_fault = pcb_protection_path_entries(
                protection_map.model_copy(
                    update={
                        "requirements": (
                            protection_requirement.model_copy(
                                update={"max_entry_distance_um": 649}
                            ),
                        )
                    }
                ),
                protection_snapshot,
            )
            via_count_fault = pcb_protection_path_entries(
                protection_map.model_copy(
                    update={
                        "requirements": (
                            protection_requirement.model_copy(update={"minimum_reference_vias": 2}),
                        )
                    }
                ),
                protection_snapshot,
            )
            if (
                distance_fault[0].status != "INCOMPLETE"
                or via_count_fault[0].status != "INCOMPLETE"
            ):
                raise ValueError(
                    "Native protection path distance/via fault controls were not detected"
                )
            protection_fixture_text = protection_board.read_text(encoding="utf-8")
            reference_via = (
                '  (via (at 10.65 11) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 2)\n'
                '    (uuid "00000000-0000-0000-0000-000000000003"))\n'
            )
            if protection_fixture_text.count(reference_via) != 1:
                raise ValueError(
                    "Native protection fixture no longer has its unique reference-via item"
                )
            open_reference_via_project = relative_project.with_name(
                "protection-nearby-open-via.kicad_pro"
            )
            open_reference_via_board = root / open_reference_via_project.with_suffix(".kicad_pcb")
            open_reference_via_board.write_text(
                protection_fixture_text.replace(
                    reference_via,
                    reference_via.replace("(at 10.65 11)", "(at 10.65 12.5)"),
                    1,
                ),
                encoding="utf-8",
            )
            open_reference_via_hash = digest(open_reference_via_board)
            open_reference_via_config = config.model_copy(
                update={"project": open_reference_via_project.as_posix()}
            )
            retained_open_reference_via_snapshot = None
            for open_via_repeat in ("first", "repeat"):
                open_reference_via_receipt = (
                    scratch / f"protection-nearby-open-via-{repeat}-{open_via_repeat}"
                )
                open_reference_via_command, open_reference_via_snapshot = (
                    capture_native_pcb_connectivity(
                        root, open_reference_via_config, open_reference_via_receipt
                    )
                )
                if (
                    open_reference_via_command.returncode != 0
                    or open_reference_via_command.error is not None
                ):
                    raise ValueError(
                        "Native nearby-open-via fixture command failed: "
                        f"{open_reference_via_command.stderr or open_reference_via_command.error}"
                    )
                if not native_pcb_command_matches(
                    open_reference_via_command, open_reference_via_config
                ):
                    raise ValueError(
                        "Native nearby-open-via fixture did not use the pinned read-only probe"
                    )
                if (
                    open_reference_via_snapshot is None
                    or open_reference_via_snapshot.schema_version != "10"
                    or open_reference_via_snapshot.board_sha256 != open_reference_via_hash
                    or open_reference_via_snapshot.kicad_version != config.kicad_version
                    or open_reference_via_snapshot.image != config.image
                    or open_reference_via_snapshot.probe_sha256 != expected_probe_sha256()
                    or not open_reference_via_snapshot.zones_refilled
                ):
                    raise ValueError(
                        "Native nearby-open-via evidence is not bound to its exact source and tool"
                    )
                open_via_entries = pcb_protection_path_entries(
                    protection_map, open_reference_via_snapshot
                )
                open_vias_at_fault_coordinate = tuple(
                    item
                    for item in open_reference_via_snapshot.vias
                    if item.net == "GND" and item.x_nm == 10_650_000 and item.y_nm == 12_500_000
                )
                open_via_reference_pad = next(
                    (
                        item
                        for item in open_reference_via_snapshot.pads
                        if item.pad.casefold() == "d1.2"
                    ),
                    None,
                )
                if (
                    len(open_via_entries) != 1
                    or open_via_entries[0].status != "INCOMPLETE"
                    or not open_via_entries[0].native_signal_path_connected
                    or open_via_entries[0].connected_reference_via_count != 0
                    or open_via_entries[0].reference_vias_within_radius != 0
                    or len(open_vias_at_fault_coordinate) != 1
                    or open_via_reference_pad is None
                    or open_via_reference_pad.connected_vias
                    or min(
                        (x - open_vias_at_fault_coordinate[0].x_nm) ** 2
                        + (y - open_vias_at_fault_coordinate[0].y_nm) ** 2
                        for x, y in open_via_reference_pad.positions_nm
                    )
                    != 1_500_000**2
                ):
                    raise ValueError(
                        "Native nearby but disconnected reference via was not rejected: "
                        f"entries={open_via_entries}, vias={open_vias_at_fault_coordinate}, "
                        f"pad={open_via_reference_pad}"
                    )
                if retained_open_reference_via_snapshot is None:
                    retained_open_reference_via_snapshot = open_reference_via_snapshot
                elif retained_open_reference_via_snapshot != open_reference_via_snapshot:
                    raise ValueError(
                        "Repeated native nearby-open-via evidence changed for identical input"
                    )
            if retained_protection_snapshot is None:
                retained_protection_snapshot = protection_snapshot
            elif retained_protection_snapshot != protection_snapshot:
                raise ValueError(
                    "Repeated native protection-path evidence changed for identical board inputs"
                )
            pads = {item.pad.casefold(): item for item in snapshot.pads}
            vias = {item.id: item for item in snapshot.vias}
            c1_return = pads["c1.2"]
            if len(c1_return.connected_vias) != 1:
                raise ValueError(
                    "Native decoupling fixture must connect C1 return to exactly one via"
                )
            connected_return_via = vias[c1_return.connected_vias[0]]
            via_distance_squared = min(
                (x - connected_return_via.x_nm) ** 2 + (y - connected_return_via.y_nm) ** 2
                for x, y in c1_return.positions_nm
            )
            if via_distance_squared != 1_000_000**2:
                raise ValueError(
                    "Native C1 return-to-connected-via distance changed: "
                    f"squared distance {via_distance_squared} nm^2"
                )
            expected_distances = {"c1.1": 1_000_000, "c2.1": 15_000_000}
            for reference, expected_distance in expected_distances.items():
                first = pads["u1.1"].positions_nm
                second = pads[reference].positions_nm
                measured_squared = min(
                    (x1 - x2) ** 2 + (y1 - y2) ** 2 for x1, y1 in first for x2, y2 in second
                )
                if measured_squared != expected_distance**2:
                    raise ValueError(
                        f"Native pad-center distance to {reference} changed: "
                        f"squared distance {measured_squared} nm^2"
                    )
            rotated = pads["c3.1"].positions_nm[0]
            if rotated[0] != 40_000_000 or abs(rotated[1] - 20_000_000) != 1_000_000:
                raise ValueError(f"Rotated footprint pad position is incorrect: {rotated}")
            entries = pcb_decoupling_entries(placement_map, snapshot)
            if (
                len(entries) != 1
                or entries[0].status != "COMPLETE"
                or entries[0].selected_capacitors != ("C1",)
                or tuple(item.distance_nm for item in entries[0].candidates)
                != (1_000_000, 15_000_000)
                or entries[0].max_return_via_distance_um != 1000
                or entries[0].candidates[0].return_via_distance_nm != 1_000_000
                or entries[0].candidates[0].connected_return_via_count != 1
            ):
                raise ValueError(f"Native placement fault/control result changed: {entries}")
            all_requirement = requirement.model_copy(update={"selection": "all"})
            all_entries = pcb_decoupling_entries(
                PcbDecouplingMap(
                    basis=placement_map.basis,
                    requirements=(all_requirement,),
                ),
                snapshot,
            )
            if all_entries[0].status != "INCOMPLETE":
                raise ValueError(
                    "Native all-candidate control did not detect the distant capacitor"
                )
            track_inventory = {item.net: item for item in snapshot.tracks}
            if set(track_inventory) != {"VDD", "GND", "DATA"} or any(
                item.width_nm != 250_000 or item.layer != "F.Cu"
                for item in track_inventory.values()
            ):
                raise ValueError(
                    "Native track inventory differs from the synthetic 250 um VDD/GND/DATA fixture"
                )
            width_boundary = pcb_track_width_entries(width_boundary_map, snapshot)
            width_fault = pcb_track_width_entries(width_fault_map, snapshot)
            if (
                len(width_boundary) != 1
                or width_boundary[0].status != "COMPLETE"
                or len(width_boundary[0].tracks) != 1
                or width_boundary[0].tracks[0].below_minimum
                or len(width_fault) != 1
                or width_fault[0].status != "COMPLETE"
                or len(width_fault[0].tracks) != 1
                or not width_fault[0].tracks[0].below_minimum
            ):
                raise ValueError(
                    "Native track-width fault/boundary controls differ from the synthetic maps"
                )
            if retained_snapshot is None:
                retained_snapshot = snapshot
            elif retained_snapshot != snapshot:
                raise ValueError("Repeated native pad centers changed for identical board inputs")
        fixture_text = (fixture_root / "pcb-decoupling-placement.kicad_pcb").read_text(
            encoding="utf-8"
        )
        if fixture_text.count("(at 12 11)") != 1:
            raise ValueError("Native return-via fixture no longer has its unique test coordinate")
        signal_segment = (
            '  (segment (start 10 10) (end 10.65 10) (width 0.25) (layer "F.Cu") (net 1)\n'
            '    (uuid "00000000-0000-0000-0000-000000000001"))\n'
        )
        if protection_fixture_text.count(signal_segment) != 1:
            raise ValueError("Native protection fixture no longer has its unique signal segment")
        disconnected_signal_board = root / relative_project.with_name(
            "protection-disconnected.kicad_pcb"
        )
        disconnected_signal_board.write_text(
            protection_fixture_text.replace(signal_segment, "", 1), encoding="utf-8"
        )
        disconnected_signal_hash = digest(disconnected_signal_board)
        disconnected_signal_project = relative_project.with_name(
            "protection-disconnected.kicad_pro"
        )
        disconnected_signal_config = config.model_copy(
            update={"project": disconnected_signal_project.as_posix()}
        )
        receipt = scratch / "disconnected-protection-signal"
        command, disconnected_snapshot = capture_native_pcb_connectivity(
            root, disconnected_signal_config, receipt
        )
        if command.returncode != 0 or command.error is not None:
            raise ValueError(
                "Native PCB protection-path fault fixture command failed: "
                f"{command.stderr or command.error}"
            )
        if not native_pcb_command_matches(command, disconnected_signal_config):
            raise ValueError(
                "Native protection-path fault fixture did not use the pinned read-only probe"
            )
        if (
            disconnected_snapshot is None
            or disconnected_snapshot.board_sha256 != disconnected_signal_hash
            or disconnected_snapshot.schema_version != "10"
            or disconnected_snapshot.kicad_version != config.kicad_version
            or disconnected_snapshot.image != config.image
            or disconnected_snapshot.probe_sha256 != expected_probe_sha256()
            or not disconnected_snapshot.zones_refilled
        ):
            raise ValueError(
                "Native protection-path fault evidence is not bound to its exact source and tool"
            )
        disconnected_entries = pcb_protection_path_entries(protection_map, disconnected_snapshot)
        if (
            len(disconnected_entries) != 1
            or disconnected_entries[0].status != "INCOMPLETE"
            or disconnected_entries[0].native_signal_path_connected
        ):
            raise ValueError(
                f"Native disconnected connector-to-protector fault was not detected: "
                f"{disconnected_entries}"
            )
        board.write_text(fixture_text.replace("(at 12 11)", "(at 13 11)", 1), encoding="utf-8")
        return_via_fault_hash = digest(board)
        retained_fault_snapshot = None
        for repeat in ("first", "repeat"):
            receipt = scratch / f"return-via-fault-{repeat}"
            command, fault_snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
            if command.returncode != 0 or command.error is not None:
                raise ValueError(
                    f"Native PCB return-via fault fixture command failed: "
                    f"{command.stderr or command.error}"
                )
            if not native_pcb_command_matches(command, fixture_config):
                raise ValueError(
                    "Native return-via fault fixture did not use the pinned read-only probe command"
                )
            if fault_snapshot is None or fault_snapshot.board_sha256 != return_via_fault_hash:
                raise ValueError("Native return-via fault evidence is not bound to its source")
            fault_entries = pcb_decoupling_entries(placement_map, fault_snapshot)
            if (
                len(fault_entries) != 1
                or fault_entries[0].status != "INCOMPLETE"
                or fault_entries[0].selected_capacitors
                or fault_entries[0].candidates[0].return_via_distance_nm != 2_000_000
            ):
                raise ValueError(
                    f"Native distant-return-via fault was not detected: {fault_entries}"
                )
            if retained_fault_snapshot is None:
                retained_fault_snapshot = fault_snapshot
            elif retained_fault_snapshot != fault_snapshot:
                raise ValueError("Repeated native return-via evidence changed for identical input")
        log.event(
            "pcb-decoupling-fixture/placement",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            near_distance_nm=1_000_000,
            distant_distance_nm=15_000_000,
            connected_return_via_distance_nm=1_000_000,
            distant_return_via_fault_distance_nm=2_000_000,
            return_via_fault_sha256=return_via_fault_hash,
            rotated_pad="40.000,19.000 or 40.000,21.000 mm",
            repeatable="true",
            receipt=(scratch.relative_to(root) / "receipt-first").as_posix(),
        )
        log.event(
            "pcb-protection-path-fixture/entry",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=protection_source_hash,
            connector_to_protector_distance_nm=650_000,
            connected_reference_vias=1,
            distance_fault_limit_um=649,
            via_count_fault_minimum=2,
            disconnected_signal_fault_sha256=disconnected_signal_hash,
            disconnected_nearby_reference_via_fault_sha256=open_reference_via_hash,
            nearby_reference_via_pad_distance_nm=1_500_000,
            nearby_reference_via_radius_um=2000,
            connected_vias_for_nearby_open_fault=0,
            repeatable="true",
            receipt=(scratch.relative_to(root) / "protection-first").as_posix(),
        )
        log.event(
            "pcb-track-width-fixture/screen",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            measured_width_nm=250_000,
            boundary_minimum_um=250,
            fault_minimum_um=251,
            repeatable="true",
            receipt=(scratch.relative_to(root) / "receipt-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-decoupling-fixture/placement",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            error=str(exc),
        )
        log.event(
            "pcb-protection-path-fixture/entry",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=protection_source_hash,
            error=str(exc),
        )
        log.event(
            "pcb-track-width-fixture/screen",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            error=str(exc),
        )
        raise


def pcb_switching_loop_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Check native switching-loop geometry and mapped trace-chain evidence."""
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        PcbReferencePlaneMap,
        PcbReferencePlaneRequirement,
        PcbSwitchingLoopEdge,
        PcbSwitchingLoopMap,
        PcbSwitchingLoopPad,
        PcbSwitchingLoopRequirement,
    )
    from .hwrepo.pcb_reference_planes import pcb_reference_plane_entries
    from .hwrepo.pcb_return_paths import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
    )
    from .hwrepo.pcb_switching_loops import pcb_switching_loop_entries

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Switching-loop native fixtures do not cover KiCad {config.kicad_version}"
        )
    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(
        tempfile.mkdtemp(prefix=f"pcb-switching-loop-{project}-", dir=log.directory.resolve())
    )
    cases = (
        ("front-plane", "pcb-switching-loop.kicad_pcb", "F.Cu", "CONNECTED", True),
        ("arc-trace", "pcb-switching-loop.kicad_pcb", "F.Cu", "CONNECTED", False),
        (
            "inner-plane",
            "pcb-switching-loop-inner-plane.kicad_pcb",
            "In1.Cu",
            "CONNECTED",
            False,
        ),
        (
            "split-inner-plane",
            "pcb-switching-loop-split-plane.kicad_pcb",
            "In1.Cu",
            "SPLIT",
            False,
        ),
    )

    def mapped_pad(reference: str, footprint: str, net: str) -> PcbSwitchingLoopPad:
        return PcbSwitchingLoopPad(pad=reference, footprint=footprint, net=net)

    for case_name, fixture_name, plane_layer, expected_plane, test_area_limit in cases:
        case_root = scratch / case_name
        case_root.mkdir()
        relative_project = (case_root.relative_to(root) / "switching-loop.kicad_pro").as_posix()
        board = root / Path(relative_project).with_suffix(".kicad_pcb")
        shutil.copyfile(fixture_root / fixture_name, board)
        if case_name in {"front-plane", "arc-trace"}:
            source = board.read_text(encoding="utf-8")
            original = (
                '  (segment (start 10 10) (end 25 10) (width 0.25) (layer "F.Cu") (net 1)\n'
                '    (uuid "00000000-0000-0000-0000-000000000001"))'
            )
            replacement = (
                "  (arc (start 10 10) (mid 17.5 5) (end 25 10) (width 0.25) "
                '(layer "F.Cu") (net 1)\n'
                '    (uuid "00000000-0000-0000-0000-000000000001"))'
                if case_name == "arc-trace"
                else (
                    '  (segment (start 10 10) (end 17.5 10) (width 0.25) (layer "F.Cu") (net 1)\n'
                    '    (uuid "00000000-0000-0000-0000-000000000001"))\n'
                    '  (segment (start 17.5 10) (end 25 10) (width 0.25) (layer "F.Cu") (net 1)\n'
                    '    (uuid "00000000-0000-0000-0000-000000000002"))'
                )
            )
            if source.count(original) != 1:
                raise ValueError("Synthetic route geometry source segment was not unique")
            board.write_text(source.replace(original, replacement), encoding="utf-8")
        source_hash = digest(board)
        fixture_config = config.model_copy(update={"project": relative_project})
        requirement = PcbSwitchingLoopRequirement(
            id=f"synthetic-{case_name}",
            basis="Synthetic native fixture; pad-center area is a geometry measurement only",
            loop_pads=(
                mapped_pad("U1.1", "Synthetic:IC_QFN", "VDD"),
                mapped_pad("C1.1", "Synthetic:Cap_0603", "VDD"),
                mapped_pad("C1.2", "Synthetic:Cap_0603", "GND"),
                mapped_pad("U1.2", "Synthetic:IC_QFN", "GND"),
            ),
            return_net="GND",
            return_plane_layer=plane_layer,
            return_plane_pads=(
                mapped_pad("U1.2", "Synthetic:IC_QFN", "GND"),
                mapped_pad("C1.2", "Synthetic:Cap_0603", "GND"),
            ),
            maximum_area_um2=1_000_000,
        )
        valid_map = PcbSwitchingLoopMap(
            basis=f"Synthetic native {case_name} return-plane regression",
            requirements=(requirement,),
        )
        trace_map = None
        if case_name in {"front-plane", "arc-trace"}:
            trace_map = PcbSwitchingLoopMap(
                basis="Synthetic native trace geometry resolver regression",
                requirements=(
                    PcbSwitchingLoopRequirement(
                        id="synthetic-native-route-chain",
                        basis="Synthetic mapped pads with native trace geometry",
                        loop_pads=(
                            mapped_pad("U1.1", "Synthetic:IC_QFN", "VDD"),
                            mapped_pad("C2.1", "Synthetic:Cap_0603", "VDD"),
                            mapped_pad("C2.2", "Synthetic:Cap_0603", "GND"),
                            mapped_pad("U1.2", "Synthetic:IC_QFN", "GND"),
                        ),
                        return_net="GND",
                        return_plane_layer="F.Cu",
                        return_plane_pads=(
                            mapped_pad("C2.2", "Synthetic:Cap_0603", "GND"),
                            mapped_pad("U1.2", "Synthetic:IC_QFN", "GND"),
                        ),
                        route_edges=(
                            PcbSwitchingLoopEdge(
                                from_pad="U1.1",
                                to_pad="C2.1",
                                kind="trace",
                                net="VDD",
                                layers=("F.Cu",),
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="C2.1",
                                to_pad="C2.2",
                                kind="component",
                                component_reference="C2",
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="C2.2",
                                to_pad="U1.2",
                                kind="plane",
                                net="GND",
                                plane_layer="F.Cu",
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="U1.2",
                                to_pad="U1.1",
                                kind="component",
                                component_reference="U1",
                            ),
                        ),
                    ),
                ),
            )
        over_limit = PcbSwitchingLoopMap(
            basis="Synthetic one-square-micrometre-under boundary fault",
            requirements=(requirement.model_copy(update={"maximum_area_um2": 999_999}),),
        )
        try:
            retained_snapshot = None
            retained_reference_measurement: tuple[str, str, str, int, int, bool] | None = None
            native_hole_ring_count = 0
            native_clearance_hole_bounds_nm = "NOT_TESTED"
            for repeat in ("first", "repeat"):
                receipt = case_root / f"receipt-{repeat}"
                command, snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
                if command.returncode != 0 or command.error is not None:
                    raise ValueError(
                        f"Native switching-loop fixture command failed: {command.stderr or command.error}"
                    )
                if not native_pcb_command_matches(command, fixture_config):
                    raise ValueError(
                        "Native switching-loop fixture did not use the pinned read-only probe command"
                    )
                if snapshot is None:
                    raise ValueError(
                        "Native switching-loop fixture returned no connectivity snapshot"
                    )
                stack = {layer.casefold() for layer in snapshot.copper_layers}
                if (
                    snapshot.schema_version != "10"
                    or snapshot.board_sha256 != source_hash
                    or snapshot.kicad_version != config.kicad_version
                    or snapshot.image != config.image
                    or snapshot.probe_sha256 != expected_probe_sha256()
                    or not snapshot.zones_refilled
                    or not snapshot.copper_layers
                    or snapshot.copper_layers[0].casefold() != "f.cu"
                    or snapshot.copper_layers[-1].casefold() != "b.cu"
                    or plane_layer.casefold() not in stack
                ):
                    raise ValueError(
                        "Native switching-loop evidence is not bound to its exact source and copper stack"
                    )
                if case_name == "inner-plane":
                    matching_zones = tuple(
                        item
                        for item in snapshot.zones
                        if item.layer.casefold() == plane_layer.casefold()
                        and item.net is not None
                        and item.net.casefold() == "gnd"
                    )
                    if len(matching_zones) != 1 or len(matching_zones[0].filled_islands) != 1:
                        raise ValueError(
                            "Native inner-plane fixture does not expose its one expected GND island"
                        )
                    outline = matching_zones[0].filled_islands[0].outline_nm
                    bounds = (
                        min(point[0] for point in outline),
                        min(point[1] for point in outline),
                        max(point[0] for point in outline),
                        max(point[1] for point in outline),
                    )
                    if bounds != (8_000_000, 8_000_000, 14_000_000, 14_000_000):
                        raise ValueError(
                            "Native inner-plane contour bounds differ from the synthetic 6 mm square"
                        )
                    test_pad = next(
                        (item for item in snapshot.pads if item.pad.casefold() == "tp1.1"),
                        None,
                    )
                    if (
                        test_pad is None
                        or test_pad.positions_nm != ((13_000_000, 13_000_000),)
                        or test_pad.net is None
                        or test_pad.net.casefold() != "vdd"
                        or test_pad.connected_islands
                        or test_pad.connected_zones
                    ):
                        raise ValueError(
                            "Native hole-control pad differs from the synthetic isolated VDD pad"
                        )
                    hole_rings = tuple(
                        hole for item in matching_zones[0].filled_islands for hole in item.holes_nm
                    )
                    native_hole_ring_count = len(hole_rings)
                    clearance_hole_bounds = tuple(
                        (
                            min(point[0] for point in hole),
                            min(point[1] for point in hole),
                            max(point[0] for point in hole),
                            max(point[1] for point in hole),
                        )
                        for hole in hole_rings
                    )
                    expected_clearance_hole = (
                        12_399_500,
                        12_399_500,
                        13_600_500,
                        13_600_500,
                    )
                    if clearance_hole_bounds.count(expected_clearance_hole) != 1:
                        raise ValueError(
                            "Native inner-plane contour did not retain the exact VDD pad clearance ring"
                        )
                    native_clearance_hole_bounds_nm = ",".join(
                        str(value) for value in expected_clearance_hole
                    )
                pads = {item.pad.casefold(): item for item in snapshot.pads}
                expected_centers = {
                    "u1.1": ((10_000_000, 10_000_000),),
                    "c1.1": ((11_000_000, 10_000_000),),
                    "c1.2": ((11_000_000, 11_000_000),),
                    "u1.2": ((10_000_000, 11_000_000),),
                }
                if any(
                    pads[name].positions_nm != centers for name, centers in expected_centers.items()
                ):
                    raise ValueError(
                        "Native switching-loop pad centers differ from the fixture geometry"
                    )
                tracks = tuple(sorted(snapshot.tracks, key=lambda item: item.start_nm))
                if case_name == "front-plane":
                    if (
                        len(tracks) != 2
                        or tracks[0].geometry_kind != "segment"
                        or tracks[0].start_pads != ("U1.1",)
                        or tracks[0].end_pads
                        or tracks[0].start_vias
                        or tracks[0].end_vias
                        or tracks[0].start_tracks
                        or tracks[0].end_tracks != (tracks[1].uuid,)
                        or tracks[1].geometry_kind != "segment"
                        or tracks[1].start_pads
                        or tracks[1].end_pads != ("C2.1",)
                        or tracks[1].start_vias
                        or tracks[1].end_vias
                        or tracks[1].start_tracks != (tracks[0].uuid,)
                        or tracks[1].end_tracks
                    ):
                        raise ValueError(
                            "Native track endpoint and same-layer adjacency evidence "
                            "differs from the synthetic connected chain"
                        )
                elif case_name == "arc-trace":
                    if (
                        len(tracks) != 1
                        or tracks[0].geometry_kind != "arc"
                        or tracks[0].start_pads != ("U1.1",)
                        or tracks[0].end_pads != ("C2.1",)
                        or tracks[0].start_vias
                        or tracks[0].end_vias
                        or tracks[0].start_tracks
                        or tracks[0].end_tracks
                    ):
                        raise ValueError(
                            "Native arc endpoint evidence differs from the synthetic board"
                        )
                elif len(tracks) != 1 or (
                    tracks[0].geometry_kind != "segment"
                    or tracks[0].start_pads != ("U1.1",)
                    or tracks[0].end_pads != ("C2.1",)
                    or tracks[0].start_vias
                    or tracks[0].end_vias
                    or tracks[0].start_tracks
                    or tracks[0].end_tracks
                ):
                    raise ValueError(
                        "Native track endpoint contact evidence differs from the synthetic board"
                    )
                if case_name == "inner-plane":
                    reference_requirement = PcbReferencePlaneRequirement(
                        id="synthetic-vdd-reference",
                        basis="Synthetic native signal-to-adjacent-plane coverage",
                        signal_net="VDD",
                        signal_layers=("F.Cu",),
                        reference_net="GND",
                        minimum_track_length_um=1_000,
                        minimum_referenced_fraction=0.3,
                    )
                    reference_map = PcbReferencePlaneMap(
                        basis="Synthetic inner-plane native geometry check",
                        requirements=(reference_requirement,),
                    )
                    measured = pcb_reference_plane_entries(reference_map, snapshot)
                    if (
                        len(measured) != 1
                        or measured[0].status != "COMPLETE"
                        or len(measured[0].tracks) != 1
                    ):
                        raise ValueError(
                            f"Native reference-plane measurement is incomplete: {measured}"
                        )
                    measurement = measured[0].tracks[0]
                    expected_measurement = (
                        measurement.track_uuid,
                        measurement.signal_layer,
                        measurement.reference_layer,
                        measurement.covered_fraction_numerator,
                        measurement.covered_fraction_denominator,
                        measurement.below_minimum,
                    )
                    if expected_measurement[1:] != ("F.Cu", "In1.Cu", 4, 15, True):
                        raise ValueError(
                            "Native inner-plane centerline coverage differs from the 4/15 "
                            f"synthetic fault: {expected_measurement}"
                        )
                    control_map = reference_map.model_copy(
                        update={
                            "requirements": (
                                reference_requirement.model_copy(
                                    update={"minimum_referenced_fraction": 0.25}
                                ),
                            )
                        }
                    )
                    control = pcb_reference_plane_entries(control_map, snapshot)
                    if control[0].tracks[0].below_minimum:
                        raise ValueError(
                            "Native inner-plane 4/15 coverage did not pass its 0.25 control"
                        )
                    if retained_reference_measurement is None:
                        retained_reference_measurement = expected_measurement
                    elif retained_reference_measurement != expected_measurement:
                        raise ValueError(
                            "Repeated native reference-plane measurement changed for identical inputs"
                        )
                valid = pcb_switching_loop_entries(valid_map, snapshot)
                if (
                    len(valid) != 1
                    or valid[0].loop_area_twice_nm2 != 2_000_000_000_000
                    or valid[0].area_exceeds_limit is not False
                    or valid[0].return_plane_status != expected_plane
                    or valid[0].return_plane_layer != plane_layer
                ):
                    raise ValueError(f"Native switching-loop result changed: {valid}")
                expected_status = "COMPLETE" if expected_plane == "CONNECTED" else "INCOMPLETE"
                if valid[0].status != expected_status:
                    raise ValueError(
                        f"Native switching-loop coverage differs from {expected_status}: {valid[0]}"
                    )
                if expected_plane == "CONNECTED" and not valid[0].return_zone_uuid:
                    raise ValueError("Connected native return-plane result has no zone identity")
                if expected_plane == "SPLIT" and valid[0].return_zone_uuid is not None:
                    raise ValueError("Split native return-plane result unexpectedly names one zone")
                if test_area_limit:
                    fault = pcb_switching_loop_entries(over_limit, snapshot)
                    if (
                        len(fault) != 1
                        or fault[0].status != "INCOMPLETE"
                        or fault[0].area_exceeds_limit is not True
                    ):
                        raise ValueError(f"Native loop-area threshold fault changed: {fault}")
                resolved_trace_length_nm: int | str | None = None
                measured_plane_area_twice_nm2: int | None = None
                if trace_map is not None:
                    trace_entries = pcb_switching_loop_entries(trace_map, snapshot)
                    if len(trace_entries) != 1:
                        raise ValueError("Native route-chain map did not return one coverage entry")
                    trace_entry = trace_entries[0]
                    if case_name == "arc-trace":
                        if (
                            trace_entry.route_status != "INCOMPLETE"
                            or trace_entry.route_edges[0].status != "INCOMPLETE"
                            or trace_entry.route_edges[0].track_uuids
                            != tuple(item.uuid for item in tracks)
                            or trace_entry.route_edges[0].length_nm is not None
                            or trace_entry.route_edges[0].issue is None
                            or "unsupported arc geometry" not in trace_entry.route_edges[0].issue
                        ):
                            raise ValueError(
                                "Native arc trace was not conservatively reported as unsupported: "
                                f"{trace_entry}"
                            )
                        resolved_trace_length_nm = "UNSUPPORTED_ARC"
                    elif (
                        trace_entry.route_status != "INCOMPLETE"
                        or trace_entry.route_edges[0].status != "RESOLVED"
                        or trace_entry.route_edges[0].track_uuids
                        != tuple(item.uuid for item in tracks)
                        or trace_entry.route_edges[0].vertices_nm
                        != (
                            (10_000_000, 10_000_000),
                            (17_500_000, 10_000_000),
                            (25_000_000, 10_000_000),
                        )
                        or trace_entry.route_edges[0].length_nm != 15_000_000
                        or not any(
                            "component geometry is not measured" in item
                            for item in trace_entry.issues
                        )
                    ):
                        raise ValueError(
                            f"Native trace route resolution differs from the synthetic map: {trace_entry}"
                        )
                    else:
                        resolved_trace_length_nm = trace_entry.route_edges[0].length_nm
                    plane_edge = trace_entry.route_edges[2]
                    if (
                        plane_edge.status != "DECLARED"
                        or plane_edge.plane_zone_uuid is None
                        or plane_edge.plane_island_index is None
                        or plane_edge.plane_island_area_twice_nm2 is None
                        or plane_edge.plane_island_area_twice_nm2 <= 0
                    ):
                        raise ValueError(
                            "Native plane route edge lacks exact filled-island contour evidence"
                        )
                    measured_plane_area_twice_nm2 = plane_edge.plane_island_area_twice_nm2
                if retained_snapshot is None:
                    retained_snapshot = snapshot
                elif retained_snapshot != snapshot:
                    raise ValueError(
                        "Repeated native switching-loop evidence changed for identical inputs"
                    )
            log.event(
                f"pcb-switching-loop-fixture/{case_name}",
                "PASS",
                project=project,
                kicad_version=config.kicad_version,
                fixture_sha256=source_hash,
                measured_area_twice_nm2=2_000_000_000_000,
                resolved_trace_length_nm=(
                    "NOT_TESTED" if resolved_trace_length_nm is None else resolved_trace_length_nm
                ),
                plane_contour_area_twice_nm2=(
                    "NOT_TESTED"
                    if measured_plane_area_twice_nm2 is None
                    else measured_plane_area_twice_nm2
                ),
                native_hole_ring_count=native_hole_ring_count,
                clearance_hole_bounds_nm=native_clearance_hole_bounds_nm,
                return_plane_layer=plane_layer,
                return_plane_status=expected_plane,
                exact_area_boundary="PASS" if test_area_limit else "NOT_TESTED",
                lower_area_fault="PASS" if test_area_limit else "NOT_TESTED",
                repeatable="true",
                receipt=(case_root.relative_to(root) / "receipt-first").as_posix(),
            )
            if case_name == "inner-plane":
                if retained_reference_measurement is None:
                    raise ValueError("Native reference-plane measurement was not retained")
                log.event(
                    "pcb-reference-plane-fixture/inner-plane",
                    "PASS",
                    project=project,
                    kicad_version=config.kicad_version,
                    fixture_sha256=source_hash,
                    signal_layer=retained_reference_measurement[1],
                    reference_layer=retained_reference_measurement[2],
                    covered_fraction=(
                        f"{retained_reference_measurement[3]}/{retained_reference_measurement[4]}"
                    ),
                    fault_threshold=0.3,
                    control_threshold=0.25,
                    below_fault_threshold=str(retained_reference_measurement[5]).lower(),
                    repeatable="true",
                    receipt=(case_root.relative_to(root) / "receipt-first").as_posix(),
                )
        except Exception as exc:
            log.event(
                f"pcb-switching-loop-fixture/{case_name}",
                "FAIL",
                project=project,
                kicad_version=config.kicad_version,
                fixture_sha256=source_hash,
                error=str(exc),
            )
            raise


def pcb_reference_plane_via_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify native via antipad contours and mapped reference-plane context."""
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import PcbReferencePlaneMap, PcbReferencePlaneRequirement
    from .hwrepo.pcb_reference_planes import pcb_reference_plane_entries
    from .hwrepo.pcb_return_paths import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
    )

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Reference-plane via fixtures do not cover KiCad {config.kicad_version}")
    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(
        tempfile.mkdtemp(prefix=f"pcb-reference-via-{project}-", dir=log.directory.resolve())
    )
    relative_project = scratch.relative_to(root) / "via-antipad.kicad_pro"
    board = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(fixture_root / "pcb-reference-via-antipad.kicad_pcb", board)
    source_hash = digest(board)
    fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
    fault_requirement = PcbReferencePlaneRequirement(
        id="synthetic-data-via-antipad",
        basis="Synthetic native via clearance; 0.75 is only a fixture threshold",
        signal_net="DATA",
        signal_layers=("F.Cu",),
        reference_net="GND",
        minimum_track_length_um=1_000,
        minimum_referenced_fraction=0.75,
    )
    fault_map = PcbReferencePlaneMap(
        basis="Synthetic native via-antipad fault control",
        requirements=(fault_requirement,),
    )
    control_map = fault_map.model_copy(
        update={
            "requirements": (
                fault_requirement.model_copy(update={"minimum_referenced_fraction": 0.5}),
            )
        }
    )
    try:
        retained_snapshot = None
        retained_measurement: tuple[str, int, int, bool, tuple[str, ...]] | None = None
        for repeat in ("first", "repeat"):
            receipt = scratch / f"receipt-{repeat}"
            command, snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
            if command.returncode != 0 or command.error is not None:
                raise ValueError(
                    f"Native PCB reference-via fixture command failed: {command.stderr or command.error}"
                )
            if not native_pcb_command_matches(command, fixture_config):
                raise ValueError(
                    "Native reference-via fixture did not use the pinned read-only probe command"
                )
            if snapshot is None:
                raise ValueError("Native PCB reference-via fixture returned no snapshot")
            if (
                snapshot.schema_version != "10"
                or snapshot.board_sha256 != source_hash
                or snapshot.kicad_version != config.kicad_version
                or snapshot.image != config.image
                or snapshot.probe_sha256 != expected_probe_sha256()
                or not snapshot.zones_refilled
                or snapshot.copper_layers[0].casefold() != "f.cu"
                or snapshot.copper_layers[-1].casefold() != "b.cu"
            ):
                raise ValueError(
                    "Native reference-via evidence is not bound to its source, tool, and copper stack"
                )
            data_tracks = tuple(
                track
                for track in snapshot.tracks
                if track.net is not None
                and track.net.casefold() == "data"
                and track.layer.casefold() == "f.cu"
            )
            data_vias = tuple(
                via for via in snapshot.vias if via.net is not None and via.net.casefold() == "data"
            )
            if len(data_tracks) != 1 or len(data_vias) != 1:
                raise ValueError(
                    "Native reference-via fixture must expose exactly one DATA segment and via"
                )
            track = data_tracks[0]
            via = data_vias[0]
            if (
                via.x_nm != 10_000_000
                or via.y_nm != 13_000_000
                or via.start_layer.casefold() != "f.cu"
                or via.end_layer.casefold() != "b.cu"
                or (via.x_nm, via.y_nm) not in {track.start_nm, track.end_nm}
                or via.id not in {*track.start_vias, *track.end_vias}
            ):
                raise ValueError(
                    "Native DATA track endpoint does not match the synthetic through-via"
                )
            reference_zones = tuple(
                zone
                for zone in snapshot.zones
                if zone.layer.casefold() == "in1.cu"
                and zone.net is not None
                and zone.net.casefold() == "gnd"
            )
            if len(reference_zones) != 1 or not any(
                island.holes_nm for island in reference_zones[0].filled_islands
            ):
                raise ValueError("Native GND reference zone did not retain a filled clearance hole")
            measured = pcb_reference_plane_entries(fault_map, snapshot)
            if (
                len(measured) != 1
                or measured[0].status != "COMPLETE"
                or len(measured[0].tracks) != 1
            ):
                raise ValueError(f"Native reference-via coverage is incomplete: {measured}")
            measurement = measured[0].tracks[0]
            if (
                measurement.track_uuid.casefold() != track.uuid.casefold()
                or not measurement.below_minimum
                or measurement.endpoint_via_ids != (via.id,)
                or measurement.endpoint_via_ids_with_center_in_reference_holes != (via.id,)
            ):
                raise ValueError(
                    "Native via center was not annotated as an uncovered reference-hole candidate"
                )
            control = pcb_reference_plane_entries(control_map, snapshot)
            if len(control) != 1 or control[0].tracks[0].below_minimum:
                raise ValueError("Native via-hole measurement did not pass its 0.5 control")
            measurement_value = (
                measurement.track_uuid,
                measurement.covered_fraction_numerator,
                measurement.covered_fraction_denominator,
                measurement.below_minimum,
                measurement.endpoint_via_ids_with_center_in_reference_holes,
            )
            if retained_snapshot is None:
                retained_snapshot = snapshot
                retained_measurement = measurement_value
            elif retained_snapshot != snapshot or retained_measurement != measurement_value:
                raise ValueError(
                    "Repeated native via-hole geometry changed for identical source and tool inputs"
                )
        if retained_measurement is None:
            raise ValueError("Native reference-via measurement was not retained")
        log.event(
            "pcb-reference-plane-fixture/via-antipad",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            covered_fraction=(f"{retained_measurement[1]}/{retained_measurement[2]}"),
            fault_threshold=0.75,
            control_threshold=0.5,
            endpoint_via_hole_candidate=retained_measurement[4][0],
            intervals_remain_uncovered="true",
            repeatable="true",
            receipt=(scratch.relative_to(root) / "receipt-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-reference-plane-fixture/via-antipad",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            error=str(exc),
        )
        raise


def pcb_reference_plane_narrow_void_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Ensure exact native centerline geometry catches a void between coarse samples."""
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        PcbConnectivitySnapshot,
        PcbReferencePlaneMap,
        PcbReferencePlaneRequirement,
    )
    from .hwrepo.pcb_reference_planes import pcb_reference_plane_entries
    from .hwrepo.pcb_return_paths import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
    )

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Reference-plane narrow-void fixtures do not cover KiCad {config.kicad_version}"
        )
    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"pcb-reference-narrow-void-{project}-", dir=log.directory.resolve()
        )
    )
    requirement = PcbReferencePlaneRequirement(
        id="synthetic-data-narrow-reference-void",
        basis="Synthetic 0.2 mm mid-route void; 0.65 is only a fixture threshold",
        signal_net="DATA",
        signal_layers=("F.Cu",),
        reference_net="GND",
        minimum_track_length_um=1_000,
        minimum_referenced_fraction=0.65,
    )
    reference_map = PcbReferencePlaneMap(
        basis="Synthetic native narrow-void fault/control",
        requirements=(requirement,),
    )
    retained: dict[
        str, tuple[PcbConnectivitySnapshot, tuple[str, int, int, bool, tuple[str, ...]]]
    ] = {}
    source_hashes: dict[str, str] = {}
    try:
        for case in ("control", "fault"):
            relative_project = scratch.relative_to(root) / f"narrow-void-{case}.kicad_pro"
            board = root / relative_project.with_suffix(".kicad_pcb")
            shutil.copyfile(fixture_root / f"pcb-reference-narrow-void-{case}.kicad_pcb", board)
            source_hash = digest(board)
            source_hashes[case] = source_hash
            fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
            retained_snapshot: PcbConnectivitySnapshot | None = None
            retained_measurement: tuple[str, int, int, bool, tuple[str, ...]] | None = None
            for repeat in ("first", "repeat"):
                receipt = scratch / f"{case}-receipt-{repeat}"
                command, snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
                if command.returncode != 0 or command.error is not None:
                    raise ValueError(
                        f"Native reference-plane {case} command failed: "
                        f"{command.stderr or command.error}"
                    )
                if not native_pcb_command_matches(command, fixture_config):
                    raise ValueError(
                        f"Native reference-plane {case} did not use the pinned read-only probe"
                    )
                if snapshot is None:
                    raise ValueError(f"Native reference-plane {case} returned no snapshot")
                if (
                    snapshot.schema_version != "10"
                    or snapshot.board_sha256 != source_hash
                    or snapshot.kicad_version != config.kicad_version
                    or snapshot.image != config.image
                    or snapshot.probe_sha256 != expected_probe_sha256()
                    or not snapshot.zones_refilled
                    or snapshot.copper_layers != ("F.Cu", "B.Cu")
                ):
                    raise ValueError(
                        f"Native reference-plane {case} evidence is not bound to source, tool, and two-layer stack"
                    )
                data_tracks = tuple(
                    track
                    for track in snapshot.tracks
                    if track.net is not None
                    and track.net.casefold() == "data"
                    and track.layer.casefold() == "f.cu"
                )
                data_vias = tuple(
                    via
                    for via in snapshot.vias
                    if via.net is not None and via.net.casefold() == "data"
                )
                if len(data_tracks) != 1 or len(data_vias) != 1:
                    raise ValueError(
                        f"Native reference-plane {case} must expose one DATA segment and via"
                    )
                track = data_tracks[0]
                via = data_vias[0]
                if (
                    (track.start_nm, track.end_nm)
                    != ((10_000_000, 13_000_000), (12_000_000, 13_000_000))
                    or via.x_nm != 10_000_000
                    or via.y_nm != 13_000_000
                    or (via.id not in {*track.start_vias, *track.end_vias})
                ):
                    raise ValueError(
                        f"Native reference-plane {case} lost its exact synthetic route"
                    )
                reference_zones = tuple(
                    zone
                    for zone in snapshot.zones
                    if zone.layer.casefold() == "b.cu"
                    and zone.net is not None
                    and zone.net.casefold() == "gnd"
                )
                if len(reference_zones) != 1 or not any(
                    island.holes_nm for island in reference_zones[0].filled_islands
                ):
                    raise ValueError(
                        f"Native reference-plane {case} did not retain the endpoint via clearance"
                    )
                entries = pcb_reference_plane_entries(reference_map, snapshot)
                if (
                    len(entries) != 1
                    or entries[0].status != "COMPLETE"
                    or len(entries[0].tracks) != 1
                ):
                    raise ValueError(
                        f"Native reference-plane {case} coverage is incomplete: {entries}"
                    )
                measurement = entries[0].tracks[0]
                expected_below = case == "fault"
                if (
                    measurement.track_uuid.casefold() != track.uuid.casefold()
                    or measurement.below_minimum != expected_below
                    or measurement.endpoint_via_ids != (via.id,)
                    or measurement.endpoint_via_ids_with_center_in_reference_holes != (via.id,)
                ):
                    raise ValueError(
                        f"Native reference-plane {case} did not match its threshold control"
                    )
                measurement_value = (
                    measurement.track_uuid,
                    measurement.covered_fraction_numerator,
                    measurement.covered_fraction_denominator,
                    measurement.below_minimum,
                    measurement.endpoint_via_ids_with_center_in_reference_holes,
                )
                if retained_snapshot is None:
                    retained_snapshot = snapshot
                    retained_measurement = measurement_value
                elif retained_snapshot != snapshot or retained_measurement != measurement_value:
                    raise ValueError(
                        f"Repeated native reference-plane {case} geometry changed for identical inputs"
                    )
            if retained_measurement is None:
                raise ValueError(f"Native reference-plane {case} evidence was not retained")
            retained[case] = (retained_snapshot, retained_measurement)

        control_snapshot, control_measurement = retained["control"]
        fault_snapshot, fault_measurement = retained["fault"]
        if control_snapshot.kicad_version != fault_snapshot.kicad_version:
            raise ValueError("Native reference-plane fault/control versions differ")
        log.event(
            "pcb-reference-plane-fixture/narrow-void",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            control_fixture_sha256=source_hashes["control"],
            fault_fixture_sha256=source_hashes["fault"],
            control_coverage=(f"{control_measurement[1]}/{control_measurement[2]}"),
            fault_coverage=(f"{fault_measurement[1]}/{fault_measurement[2]}"),
            minimum_fraction=requirement.minimum_referenced_fraction,
            control_below_threshold="false",
            fault_below_threshold="true",
            endpoint_via_hole_context="retained",
            repeatable="true",
            control_receipt=(scratch.relative_to(root) / "control-receipt-first").as_posix(),
            fault_receipt=(scratch.relative_to(root) / "fault-receipt-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-reference-plane-fixture/narrow-void",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            control_fixture_sha256=source_hashes.get("control", ""),
            fault_fixture_sha256=source_hashes.get("fault", ""),
            error=str(exc),
        )
        raise


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
        component_rating_fixtures_lane(root, project=project, image=image, log=log)
        power_sequence_fixture_lane(root, project=project, image=image, log=log)
        ic_rail_capacitor_fixture_lane(root, project=project, image=image, log=log)
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


def release_fixture(root: Path, target: Path) -> None:
    """Restore the public examples in a disposable default-layout repository.

    Live catalogs, design roots and adopter configuration are deliberately absent:
    release rehearsal exercises the retained public template fixtures, even after
    adoption has replaced the live catalog or moved private designs elsewhere.
    """
    root = root.resolve()
    if target.exists():
        raise ValueError(f"Release rehearsal output already exists: {target}")
    directories = ("docs", "templates", "examples", ".github")
    files = (
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        "CHANGELOG.md",
        ".gitignore",
        ".gitattributes",
        "pyproject.toml",
        "requirements-tooling.txt",
        "catalog/documentation-policy.json",
    )
    references = (
        "examples/catalog/projects.json",
        "examples/catalog/products.json",
        "examples/catalog/parts.json",
        "examples/catalog/interfaces.json",
        "examples/catalog/libraries.json",
        "examples/catalog/toolchains.json",
        "examples/catalog/team-policy.json",
        "examples/catalog/release-policies.json",
        "examples/projects/arduino-uno-status-led/project.json",
    )
    missing = [name for name in (*directories, *files, *references) if not (root / name).exists()]
    if missing:
        raise ValueError(
            "Release rehearsal requires retained public template fixtures; restore these "
            f"paths from the matching template version: {', '.join(missing)}"
        )

    def ignore_local(directory: str, names: list[str]) -> set[str]:
        ignored = {
            name
            for name in names
            if name == ".git"
            or ephemeral(name)
            or generated_artifact((Path(directory) / name).relative_to(root).as_posix())
        }
        for name in set(names) - ignored:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f"Public release fixture must not follow a symlink: {path}")
        return ignored

    # Validate before creating output, including links in directory ancestors.
    for name in (*directories, *files):
        source = root / name
        if any((root / part).is_symlink() for part in (Path(name), *Path(name).parents)):
            raise ValueError(f"Public release fixture must not follow a symlink: {source}")
        if source.is_dir():
            for directory, children, filenames in os.walk(source):
                ignored = ignore_local(directory, children + filenames)
                children[:] = [name for name in children if name not in ignored]

    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    for directory in directories:
        shutil.copytree(root / directory, target / directory, ignore=ignore_local)
    for name in files:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, destination)
    for directory in ("catalog", "projects", "products", "libraries", "generated", "schemas"):
        (target / directory).mkdir(exist_ok=True)
        readme = root / directory / "README.md"
        if not (root / directory).is_symlink() and readme.is_file() and not readme.is_symlink():
            shutil.copy2(readme, target / directory / "README.md")
    shutil.copytree(
        root / "examples/catalog", target / "catalog", dirs_exist_ok=True, ignore=ignore_local
    )
    shutil.copy2(
        Path(__file__).resolve().parent / "fixtures/scaffold-license.txt", target / "LICENSE"
    )


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
