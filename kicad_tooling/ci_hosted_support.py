"""Shared event logging and child-process errors for hosted verification lanes."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from .hwrepo.contracts import KiCadErcReport


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


def normalized_erc_report_bytes(report: KiCadErcReport) -> bytes:
    """Serialize typed ERC evidence in stable order, excluding raw JSON ordering."""
    violations: list[
        tuple[
            str,
            str,
            str | None,
            tuple[tuple[str | None, int | float | None, int | float | None], ...],
        ]
    ] = []
    for item in report.violations:
        details = tuple(
            sorted(
                ((detail.description, detail.x, detail.y) for detail in item.items),
                key=lambda detail: json.dumps(
                    detail,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
            )
        )
        violations.append((item.type, item.severity, item.description, details))
    violations.sort(
        key=lambda violation: json.dumps(
            violation,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
    return json.dumps(
        {"kicad_version": report.kicad_version, "violations": violations},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
