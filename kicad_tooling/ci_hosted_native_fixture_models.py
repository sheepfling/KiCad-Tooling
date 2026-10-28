"""Shared typed evidence records for repeatable native fixture exports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Literal, TypeAlias, TypeVar

from .hwrepo.models import NetlistContract

NativeRun: TypeAlias = Literal["first", "repeat"]
FaultControlFixtureCase: TypeAlias = Literal["control", "fault"]
_Record = TypeVar("_Record")


@dataclass(frozen=True, slots=True)
class NativeRunPair(Generic[_Record]):
    """The two explicitly named exports used for repeatability evidence."""

    first: _Record
    repeat: _Record

    def for_run(self, run: NativeRun) -> _Record:
        if run == "first":
            return self.first
        if run == "repeat":
            return self.repeat
        raise ValueError(f"Unknown native run: {run}")


@dataclass(frozen=True, slots=True)
class FaultControlPair(Generic[_Record]):
    """An explicit control/fault pair with finite case lookup."""

    control: _Record
    fault: _Record

    def for_case(self, case: FaultControlFixtureCase) -> _Record:
        if case == "control":
            return self.control
        if case == "fault":
            return self.fault
        raise ValueError(f"Unknown control/fault fixture case: {case}")


@dataclass(frozen=True, slots=True)
class FixtureSourceEvidence:
    """Original source file and its reviewed content digest."""

    path: Path
    sha256: str

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise ValueError("Native fixture source path must be absolute")
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValueError("Native fixture source digest must be a lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class NativeNetlistRunEvidence:
    """One native netlist export and both raw and normalized digests."""

    contract: NetlistContract
    netlist_sha256: str
    normalized_sha256: str

    def __post_init__(self) -> None:
        for label, value in (
            ("native netlist", self.netlist_sha256),
            ("normalized netlist", self.normalized_sha256),
        ):
            if re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(f"{label} digest must be a lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class NativeNetlistFixtureEvidence:
    """A source-bound netlist fixture with repeatable native run evidence."""

    source: FixtureSourceEvidence
    netlists: NativeRunPair[NativeNetlistRunEvidence]
