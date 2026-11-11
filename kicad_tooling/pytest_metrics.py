"""Extract and report concise pytest outcome and duration metrics."""

from __future__ import annotations

import re
from typing import TypedDict


class PytestDuration(TypedDict):
    seconds: float
    phase: str
    nodeid: str


class PytestMetrics(TypedDict):
    summary_available: bool
    summary_line: str | None
    pytest_elapsed_seconds: float | None
    counts: dict[str, int]
    duration_section_available: bool
    slowest: list[PytestDuration]


_OUTCOMES = (
    "passed",
    "failed",
    "errors",
    "error",
    "skipped",
    "deselected",
    "xfailed",
    "xpassed",
    "rerun",
    "warnings",
    "warning",
)
_OUTCOME_NAMES = "|".join(_OUTCOMES)
_SUMMARY_LINE = re.compile(
    rf"(?:\d+\s+(?:{_OUTCOME_NAMES})\b(?:\s*,\s*)?)+\s+in\s+"
    r"(?P<elapsed>\d+(?:\.\d+)?)s(?:\s+\([^)]*\))?\s*$"
)
_NO_TESTS_LINE = re.compile(r"no tests ran in (?P<elapsed>\d+(?:\.\d+)?)s\s*$")
_COUNT = re.compile(rf"(?P<count>\d+)\s+(?P<outcome>{_OUTCOME_NAMES})\b")
_DURATION_HEADING = re.compile(r"slowest\s+\d+\s+durations?", re.IGNORECASE)
_DURATION = re.compile(
    r"^\s*(?P<seconds>\d+(?:\.\d+)?)s\s+(?P<phase>[a-zA-Z_-]+)\s+(?P<nodeid>\S.*?)\s*$"
)


def pytest_metrics(output: str, *, slowest_limit: int = 10) -> PytestMetrics:
    """Parse pytest's quiet summary and duration section without requiring a plugin."""
    if slowest_limit < 0:
        raise ValueError("slowest_limit must not be negative")

    lines = output.splitlines()
    summary_line: str | None = None
    elapsed_seconds: float | None = None
    counts: dict[str, int] = {}
    for line in reversed(lines):
        candidate = line.strip()
        summary = _SUMMARY_LINE.search(candidate)
        no_tests = _NO_TESTS_LINE.search(candidate)
        if no_tests is not None:
            summary_line = candidate
            elapsed_seconds = float(no_tests.group("elapsed"))
            break
        if summary is None:
            continue
        summary_line = candidate
        elapsed_seconds = float(summary.group("elapsed"))
        for match in _COUNT.finditer(candidate):
            outcome = _canonical_outcome(match.group("outcome"))
            counts[outcome] = counts.get(outcome, 0) + int(match.group("count"))
        break

    heading_index = next(
        (index for index, line in enumerate(lines) if _DURATION_HEADING.search(line)), None
    )
    slowest: list[PytestDuration] = []
    if heading_index is not None and slowest_limit:
        for line in lines[heading_index + 1 :]:
            if line.startswith("="):
                break
            match = _DURATION.match(line)
            if match is None:
                continue
            slowest.append(
                {
                    "seconds": float(match.group("seconds")),
                    "phase": match.group("phase"),
                    "nodeid": match.group("nodeid"),
                }
            )
            if len(slowest) >= slowest_limit:
                break

    return {
        "summary_available": summary_line is not None,
        "summary_line": summary_line,
        "pytest_elapsed_seconds": elapsed_seconds,
        "counts": counts,
        "duration_section_available": heading_index is not None,
        "slowest": slowest,
    }


def report_pytest_metrics(output: str) -> PytestMetrics:
    """Print pytest metrics and return the compact, JSON-compatible event payload."""
    metrics = pytest_metrics(output)
    if not metrics["summary_available"]:
        print("tooling-ci: unit pytest metrics unavailable (summary not recognized)", flush=True)
        return metrics

    counts = metrics["counts"]
    labels = [f"{count} {name}" for name, count in counts.items()]
    result = ", ".join(labels) if labels else "no tests reported"
    elapsed = metrics["pytest_elapsed_seconds"]
    if elapsed is None:
        raise AssertionError("recognized pytest summary is missing its elapsed time")
    print(f"tooling-ci: unit pytest {result}; pytest elapsed {elapsed:.2f}s", flush=True)

    slowest = metrics["slowest"]
    if not slowest:
        label = "unavailable" if not metrics["duration_section_available"] else "none reported"
        print(f"tooling-ci: unit slowest tests {label}", flush=True)
        return metrics
    for sample in slowest:
        print(
            "tooling-ci: unit slowest "
            f"{sample['seconds']:.2f}s {sample['phase']} {sample['nodeid']}",
            flush=True,
        )
    return metrics


def _canonical_outcome(outcome: str) -> str:
    if outcome == "error":
        return "errors"
    if outcome == "warning":
        return "warnings"
    return outcome
