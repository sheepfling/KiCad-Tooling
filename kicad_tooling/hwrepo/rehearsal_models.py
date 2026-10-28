"""Typed JSON contracts used by the prepared-corpus rehearsal driver."""

from __future__ import annotations

from typing import NotRequired

from pydantic import JsonValue, TypeAdapter
from typing_extensions import TypedDict


class CorpusFixture(TypedDict):
    """One queue entry ready for a disposable project rehearsal."""

    id: str
    ready: bool
    group_id: str
    relative_path: str
    repository: str


class CorpusGroup(TypedDict):
    """Source snapshot and integrity receipt shared by queue entries."""

    id: str
    inventory_path: str
    inventory_sha256: str
    source_kind: str
    directory: str
    revision: str


class CorpusInventoryItem(TypedDict):
    """One exact inventoried file or preserved symlink."""

    path: str
    kind: NotRequired[str]
    target: NotRequired[str]
    sha256: NotRequired[str]


class CorpusInventory(TypedDict):
    """File inventory decoded from a prepared source snapshot."""

    files: list[CorpusInventoryItem]
    inventory_complete: NotRequired[bool]


class CorpusQueue(TypedDict):
    """Prepared fixture selection plus its source groups."""

    fixtures: list[CorpusFixture]
    groups: list[CorpusGroup]
    counts: NotRequired[JsonValue]


class ToolReport(TypedDict):
    """Common required status plus command-specific JSON report fields."""

    status: NotRequired[str]
    run_directory: NotRequired[str]
    findings: NotRequired[JsonValue]
    copied_sha256: NotRequired[dict[str, str]]
    directory: NotRequired[str]


class RehearsalStageReceipt(TypedDict):
    """One captured subprocess attempt without duplicating its full report."""

    stage: str
    command: list[str]
    returncode: int
    status: str | None
    parse_error: str | None
    elapsed_seconds: float
    run_directory: str | None
    findings: JsonValue


class RehearsalStage(RehearsalStageReceipt):
    """One in-memory subprocess attempt paired with its structured report."""

    report: ToolReport


class RehearsalResult(TypedDict):
    """One fixture's collected stages and integrity outcome."""

    fixture: CorpusFixture
    source_revision: str
    build_authorized: bool
    stages: list[RehearsalStage]
    status: str
    copied_bytes_match: NotRequired[bool]
    error: NotRequired[str]


class RehearsalSummary(TypedDict):
    """Top-level durable summary written after the selected runs finish."""

    status: str
    completed: int
    selected: int
    build_authorized: bool
    results: list[RehearsalResult]
    not_exercised: list[str]


CORPUS_QUEUE_ADAPTER = TypeAdapter(CorpusQueue)
CORPUS_INVENTORY_ADAPTER = TypeAdapter(CorpusInventory)
TOOL_REPORT_ADAPTER = TypeAdapter(ToolReport)
