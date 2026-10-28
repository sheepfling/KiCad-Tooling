"""Exercise installed CLI and MCP onboarding against disposable project checkouts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from kicad_tooling.hwrepo.evidence import digest as file_digest
from kicad_tooling.hwrepo.repository import ephemeral
from kicad_tooling.playtest_mcp import PLAYTEST_REPORT_ADAPTER, PlaytestReport, run_mcp_playtest

ROOT = Path(__file__).resolve().parents[1]
OMIT = frozenset(
    {
        ".git",
        "build",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".DS_Store",
    }
)


def source_files(root: Path) -> dict[str, str]:
    """Hash ordinary authored inputs; never follow links or consume local build state."""
    result: dict[str, str] = {}
    for directory, children, files in os.walk(root, followlinks=False):
        base = Path(directory)
        children[:] = sorted(
            name
            for name in children
            if name not in OMIT and not ephemeral((base / name).relative_to(root).as_posix())
        )
        for name in (*children, *sorted(files)):
            if (
                name in OMIT
                or name.endswith((".pyc", ".pyo"))
                or ephemeral((base / name).relative_to(root).as_posix())
            ):
                continue
            path = base / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError(f"Playtest source must use ordinary files/directories: {path}")
            if stat.S_ISREG(mode):
                result[path.relative_to(root).as_posix()] = file_digest(path)
    return result


class Playtest:
    def __init__(self, template: Path, output: Path, native: bool) -> None:
        self.template, self.output, self.native = template, output, native
        self.environment = os.environ.copy()
        self.environment.pop("PYTHONPATH", None)
        self.environment["PYTHONDONTWRITEBYTECODE"] = "1"
        self.records: list[dict[str, JsonValue]] = []
        self.complete = False
        self.started = datetime.now(UTC).isoformat()
        self.caller = output / "caller"
        self.caller.mkdir()
        self.hooks = self.caller / "empty-hooks"
        self.hooks.mkdir()

    def save(self, name: str, document: object) -> None:
        (self.output / name).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    def record(self, name: str, passed: bool, **details: JsonValue) -> None:
        status = "PASS" if passed else "FAIL"
        item: dict[str, JsonValue] = {"stage": name, "status": status, **details}
        self.records.append(item)
        with (self.output / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item) + "\n")
        print(f"playtest: {name} {status.lower()}", flush=True)
        self.summary()

    def summary(self) -> None:
        passed = bool(self.records) and all(row["status"] == "PASS" for row in self.records)
        self.save(
            "summary.json",
            {
                "status": ("PASS" if passed else "FAIL") if self.complete else "IN_PROGRESS",
                "completed": self.complete,
                "started_utc": self.started,
                "build_authorized": False,
                "native_requested": self.native,
                "template_source": str(self.template),
                "run_directory": str(self.output),
                "stages": self.records,
                "scope": "Disposable onboarding and tool execution; no design approval or supplier calls.",
            },
        )

    def run(
        self,
        name: str,
        command: tuple[str, ...],
        *,
        expected_exit: int = 0,
        expected_status: str | None = None,
        timeout: int = 300,
    ) -> PlaytestReport:
        print(f"playtest: {name} started", flush=True)
        started = time.monotonic()
        result = subprocess.run(
            command,
            cwd=self.caller,
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        (self.output / f"{name}.stdout.log").write_text(result.stdout, encoding="utf-8")
        (self.output / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
        report: PlaytestReport = {}
        parse_error = None
        if expected_status is not None:
            try:
                report = PLAYTEST_REPORT_ADAPTER.validate_python(
                    json.loads(result.stdout), strict=True
                )
            except (ValueError, TypeError) as exc:
                parse_error = str(exc)
                report = {}
        passed = (
            result.returncode == expected_exit
            and parse_error is None
            and (expected_status is None or report.get("status") == expected_status)
            and report.get("build_authorized") is not True
        )
        self.record(
            name,
            passed,
            command=cast(JsonValue, list(command)),
            returncode=result.returncode,
            expected_returncode=expected_exit,
            observed_status=report.get("status"),
            expected_status=expected_status,
            parse_error=parse_error,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
        return report

    def cli(
        self,
        name: str,
        root: Path,
        *arguments: str,
        expected_exit: int = 0,
        expected_status: str = "PASS",
        timeout: int = 300,
    ) -> PlaytestReport:
        return self.run(
            name,
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling",
                *arguments,
                "--root",
                str(root),
                "--format",
                "json",
            ),
            expected_exit=expected_exit,
            expected_status=expected_status,
            timeout=timeout,
        )

    def git(self, root: Path, label: str) -> None:
        for name, arguments in (
            ("init", ("init", str(root))),
            ("index", ("-C", str(root), "add", "--all")),
            (
                "commit",
                (
                    "-C",
                    str(root),
                    "-c",
                    "user.name=Tooling playtest",
                    "-c",
                    "user.email=playtest@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "-c",
                    f"core.hooksPath={self.hooks}",
                    "commit",
                    "-m",
                    "Disposable fixture",
                ),
            ),
        ):
            self.run(f"{label}-git-{name}", ("git", *arguments))

    def execute(self) -> None:
        original = source_files(self.template)
        reference = self.output / "reference"

        def omit_local(directory: str, names: Iterable[str]) -> set[str]:
            base = Path(directory)
            return {
                name
                for name in names
                if name in OMIT
                or name.endswith((".pyc", ".pyo"))
                or ephemeral((base / name).relative_to(self.template).as_posix())
            }

        shutil.copytree(self.template, reference, symlinks=True, ignore=omit_local)
        self.record("copy-authored-bytes", original == source_files(reference), files=len(original))
        if any(path.is_file() for path in (reference / "tools").rglob("*")):
            raise ValueError("The project still embeds tools/; use the extracted template checkout")
        self.save("source-sha256.json", original)
        self.run(
            "installed-origin",
            (
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import kicad_tooling; print(kicad_tooling.__file__)",
            ),
        )
        self.git(reference, "reference")
        inventory = self.cli("inventory", reference, "template", "list")
        controllers = [item for item in inventory.get("projects", []) if item["id"] == "controller"]
        if len(controllers) != 1:
            raise ValueError("Playtest needs the declared controller reference fixture")
        controller = controllers[0]
        toolchain_id = controller["toolchain_id"]
        source = reference / controller["project"]
        original_native = source_files(source.parent)
        self.cli("surface", reference, "surface", "--require-live-mcp")
        self.cli("portable-controller", reference, "verify", "--project", "controller")
        if self.native:
            self.cli(
                "native-controller",
                reference,
                "verify",
                "--project",
                "controller",
                "--depth",
                "native",
                "--runner",
                "container",
                timeout=1200,
            )
        adopted = self.output / "adopted"
        self.cli(
            "bootstrap",
            reference,
            "template",
            "bootstrap",
            "--destination",
            str(adopted),
            "--project-id",
            "playtest-hardware",
        )
        if not adopted.is_dir():
            raise ValueError("Bootstrap did not create the disposable destination")
        self.git(adopted, "adopted")
        adoption = self.cli(
            "adopt", adopted, "template", "adopt", "--project-id", "playtest-hardware", timeout=600
        )
        if adoption.get("status") != "PASS":
            # Keep the detailed project gate beside the adoption summary. Independent
            # onboarding steps can still run when initialization itself succeeded.
            self.cli("adopt-detailed-gate", adopted, "ci", timeout=600)
            if adoption.get("initialization") != "PASS":
                raise ValueError("Adoption initialization failed; inspect adopt.stdout.log")
        self.cli("adopted-inventory", adopted, "template", "list")
        self.cli(
            "cli-new-project",
            adopted,
            "template",
            "new-project",
            "--project-id",
            "cli-first",
            "--kind",
            "pcb",
            "--toolchain",
            toolchain_id,
        )
        diagnosis = self.cli(
            "cli-diagnose-first",
            adopted,
            "template",
            "diagnose",
            "--project-id",
            "cli-first",
            expected_exit=1,
            expected_status="NEEDS_WORK",
        )
        self.record(
            "cli-actionable-diagnosis",
            bool(diagnosis.get("findings"))
            and any(
                item.get("severity") == "BLOCKING" and item.get("action")
                for item in diagnosis.get("findings", [])
            ),
        )
        arguments = (
            "template",
            "import-project",
            "--source",
            str(source),
            "--project-id",
            "imported-controller",
            "--toolchain",
            toolchain_id,
        )
        preview = self.cli("import-preview", adopted, *arguments, "--dry-run")
        self.record(
            "import-preview-readonly", not (adopted / "projects/imported-controller").exists()
        )
        imported = self.cli("import-apply", adopted, *arguments)
        directory = adopted / imported.get("directory", "projects/imported-controller")
        copied = imported.get("copied_sha256", {})
        self.record(
            "import-byte-identity",
            bool(copied)
            and copied == preview.get("copied_sha256")
            and all(
                file_digest(directory / "kicad" / name) == digest for name, digest in copied.items()
            )
            and original_native == source_files(source.parent),
        )
        contract = json.loads((directory / "tests/contract.json").read_text(encoding="utf-8"))
        validation = contract["validation"]
        self.record(
            "import-independent-requirements",
            imported.get("review_required") is True
            and validation.get("components") == {}
            and validation.get("nets") == {},
            review_state="UNREVIEWED",
            electrical_coverage=False,
            build_authorized=False,
        )
        self.cli(
            "import-diagnosis",
            adopted,
            "template",
            "diagnose",
            "--project-id",
            "imported-controller",
            expected_exit=1,
            expected_status="NEEDS_WORK",
        )
        if self.native:
            observed = self.cli(
                "import-contract-capture",
                adopted,
                "contract-coach",
                "--project-id",
                "imported-controller",
                "--capture",
                "--runner",
                "container",
                expected_status="READY_FOR_REVIEW",
                timeout=600,
            )
            self.record(
                "capture-preserves-review-boundary",
                observed.get("review_state") == "UNREVIEWED"
                and observed.get("electrical_coverage") is False
                and observed.get("build_authorized") is False
                and contract == json.loads((directory / "tests/contract.json").read_text()),
            )
        asyncio.run(run_mcp_playtest(self, reference, toolchain_id))
        self.record(
            "original-native-source-preserved",
            original_native == source_files(self.template / Path(controller["project"]).parent),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template-root",
        "--template",
        type=Path,
        required=True,
        help="External template checkout with the controller reference project",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="New receipt directory below the tooling or template checkout's build/",
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="Run approved digest-pinned KiCad containers and UNREVIEWED contract capture",
    )
    args = parser.parse_args()
    template = args.template_root.resolve(strict=True)
    requested = args.output or ROOT / "build/playtests" / datetime.now(UTC).strftime(
        "run-%Y%m%dT%H%M%S%fZ"
    )
    output = requested.absolute()
    if output.resolve() != output or not any(
        output.is_relative_to(base / "build") and output != base / "build"
        for base in (ROOT, template)
    ):
        parser.error("Output must be an unlinked new directory below a checkout's build/")
    output.mkdir(parents=True, exist_ok=False)
    playtest = Playtest(template, output, args.native)
    try:
        playtest.execute()
    except Exception as exc:  # noqa: BLE001 - retain transport/runner failures in the receipt
        playtest.record("playtest-error", False, error=f"{type(exc).__name__}: {exc}")
    playtest.complete = True
    playtest.summary()
    print(f"playtest: receipt {output}", flush=True)
    return 0 if all(row["status"] == "PASS" for row in playtest.records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
