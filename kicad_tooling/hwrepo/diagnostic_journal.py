"""Ignored, per-run evidence for the human-facing diagnostic command."""
from __future__ import annotations

import json
import platform
import re
import sys
import tempfile
import time
import traceback
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class DiagnosticJournal:
    """Record stage progress and raw typed results without copying design sources."""

    def __init__(
        self, root: Path, project_id: str, output: Path | None = None,
        label: str = "diagnose",
    ) -> None:
        root = root.resolve()
        if output is None:
            parent = root / "build/diagnostics"
            parent.mkdir(parents=True, exist_ok=True)
            safe_id = re.sub(r"[^a-zA-Z0-9-]", "-", project_id)[:40] or "project"
            directory = Path(tempfile.mkdtemp(prefix=f"{safe_id}-", dir=parent))
        else:
            directory = output.resolve()
            if directory.is_relative_to(root) and not directory.is_relative_to(root / "build"):
                raise ValueError("In-repository diagnostic output must be under ignored build/")
            directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self._label = label
        self._started = time.monotonic()
        self._metadata: dict[str, str | float] = {
            "schema_version": "1",
            "project_id": project_id,
            "root": str(root),
            "started_utc": datetime.now(UTC).isoformat(),
            "python": platform.python_version(),
            "executable": sys.executable,
            "platform": platform.platform(),
            "status": "RUNNING",
        }
        self._write_metadata()
        self.event("run", "START", f"diagnostic receipt: {directory}")

    def _write_metadata(self) -> None:
        (self.directory / "run.json").write_text(
            json.dumps(self._metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def event(self, stage: str, status: str, detail: str) -> None:
        timestamp = datetime.now(UTC).isoformat()
        with (self.directory / "events.log").open("a", encoding="utf-8") as stream:
            stream.write(f"{timestamp} [{stage}] {status}: {detail}\n")

    @contextmanager
    def stage(self, name: str) -> Generator[None, None, None]:
        started = time.monotonic()
        self.event(name, "START", "running")
        print(f"{self._label}: {name}...", file=sys.stderr, flush=True)
        try:
            yield
        except BaseException as exc:
            self.event(name, "ERROR", f"{type(exc).__name__}: {exc}")
            raise
        else:
            elapsed = time.monotonic() - started
            self.event(name, "DONE", f"{elapsed:.2f}s")
            print(f"{self._label}: {name} done ({elapsed:.1f}s)", file=sys.stderr, flush=True)

    def save_model(self, name: str, model: BaseModel) -> None:
        (self.directory / f"{name}.json").write_text(
            model.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        self.event(name, "SAVED", f"{name}.json")

    def finish(self, result: BaseModel, human_text: str, status: str) -> None:
        self.finish_named("diagnosis", result, human_text, status)

    def finish_named(self, name: str, result: BaseModel, human_text: str, status: str) -> None:
        """Close a diagnostic or verification run with a retained typed report."""
        self.save_model(name, result)
        (self.directory / f"{name}.txt").write_text(human_text + "\n", encoding="utf-8")
        self._metadata["status"] = status
        self._metadata["elapsed_seconds"] = round(time.monotonic() - self._started, 3)
        self._write_metadata()
        self.event("run", "DONE", f"{status}; {name}.txt and {name}.json saved")

    def fail(self, exc: BaseException) -> None:
        (self.directory / "error.txt").write_text(
            "".join(traceback.format_exception(exc)), encoding="utf-8"
        )
        self._metadata["status"] = "ERROR"
        self._metadata["elapsed_seconds"] = round(time.monotonic() - self._started, 3)
        self._write_metadata()
        self.event("run", "ERROR", f"{type(exc).__name__}: {exc}; see error.txt")
