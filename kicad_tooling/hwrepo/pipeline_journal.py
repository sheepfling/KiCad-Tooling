"""Live, partial evidence for portable policy runs.

The final portable report remains authoritative. This journal makes a timed-out or
crashed run diagnosable without claiming that unfinished checks passed.
"""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .models import CommandEvidence

_Result = TypeVar("_Result")


class PipelineJournal:
    def __init__(self, output: Path | None, scope: str, projects: tuple[str, ...],
                 workers: int) -> None:
        self.output = output
        self.started = time.monotonic()
        self._metadata: dict[str, str | int | float | tuple[str, ...]] = {
            "schema_version": "1", "scope": scope, "projects": projects,
            "project_test_workers": workers, "status": "RUNNING",
            "started_utc": datetime.now(UTC).isoformat(),
        }
        if output is not None:
            output.mkdir(parents=True, exist_ok=False)
            self._write_metadata()
        self._event("pipeline", "START")

    def _write_metadata(self) -> None:
        if self.output is not None:
            (self.output / "run.json").write_text(
                json.dumps(self._metadata, indent=2) + "\n", encoding="utf-8"
            )

    def _event(self, name: str, status: str, elapsed: float | None = None,
               error: str | None = None) -> None:
        event: dict[str, str | float] = {
            "time_utc": datetime.now(UTC).isoformat(), "stage": name, "status": status,
        }
        if elapsed is not None:
            event["elapsed_seconds"] = round(elapsed, 3)
        if error is not None:
            event["error"] = error
        if self.output is not None:
            with (self.output / "events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, sort_keys=True) + "\n")
        suffix = f" ({elapsed:.1f}s)" if elapsed is not None else ""
        print(f"ci: {name} {status.lower()}{suffix}", file=sys.stderr, flush=True)

    def stage(self, name: str, action: Callable[[], _Result]) -> _Result:
        started = time.monotonic()
        self._event(name, "START")
        try:
            result = action()
        except BaseException as exc:
            self._event(name, "ERROR", time.monotonic() - started,
                        f"{type(exc).__name__}: {exc}")
            raise
        if self.output is not None and isinstance(result, BaseModel):
            (self.output / f"{name}.json").write_text(
                result.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
        state = (
            "PASS" if result.returncode == 0 and result.error is None else "FAIL"
        ) if isinstance(result, CommandEvidence) else getattr(result, "status", "DONE")
        self._event(name, str(state), time.monotonic() - started)
        return result

    def finish(self, status: str) -> None:
        elapsed = time.monotonic() - self.started
        self._event("pipeline", status, elapsed)
        self._metadata["status"] = status
        self._metadata["elapsed_seconds"] = round(elapsed, 3)
        self._write_metadata()
