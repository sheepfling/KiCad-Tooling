"""Compare retained verification stages without inferring missing work passed."""

from __future__ import annotations

from typing import get_args

from .verification_history_evidence import SavedSnapshot
from .verification_history_models import HistoryStageChange, StageState

_STAGES = (
    "verification",
    "portable",
    "doctor",
    "native",
    "design_lint",
    "electrical",
    "diagnosis",
)


def _state(snapshot: SavedSnapshot, stage: str) -> StageState:
    report = snapshot.verification
    if report is not None:
        value = report if stage == "verification" else getattr(report, stage)
        if value is None:
            return "NOT_RUN"
        status = value.status
        if status not in get_args(StageState):
            raise ValueError(f"Unexpected verification stage status: {status}")
        return status
    evidence = next((item for item in snapshot.evidence if item.kind == "verification"), None)
    if evidence is None or evidence.integrity == "NOT_SELECTED":
        return "NOT_RUN"
    if evidence.integrity == "MISSING":
        return "MISSING"
    if evidence.integrity == "STALE":
        return "STALE"
    return "UNAVAILABLE"


def stage_changes(before: SavedSnapshot, after: SavedSnapshot) -> tuple[HistoryStageChange, ...]:
    """A missing or changed summary never becomes a recorded NOT_RUN stage."""
    result: list[HistoryStageChange] = []
    for name in _STAGES:
        previous, current = _state(before, name), _state(after, name)
        result.append(
            HistoryStageChange(
                name=name,
                change="UNCHANGED" if previous == current else "CHANGED",
                before=previous,
                after=current,
            )
        )
    return tuple(result)
