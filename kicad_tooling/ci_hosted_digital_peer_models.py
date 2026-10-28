"""Typed source and native-run evidence for digital-peer fixtures."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Protocol, TypeAlias

from .ci_hosted_native_fixture_models import (
    FixtureSourceEvidence as DigitalPeerFixtureSource,
)
from .ci_hosted_native_fixture_models import (
    NativeNetlistRunEvidence,
    NativeRunPair,
)
from .hwrepo.models import NetlistContract, ProjectConfig

DigitalPeerFixtureCase: TypeAlias = Literal[
    "multi-device",
    "combo-device",
    "peer-control",
    "peer-fault",
    "peer-translator-control",
    "serial-control",
    "serial-fault",
    "serial-reference-fault",
    "serial-connector-control",
    "serial-connector-fault",
    "serial-optical-isolation-control",
    "serial-label-control",
    "serial-label-fault",
    "component-peer-control",
    "component-peer-fault",
]
FIXTURE_CASES: tuple[DigitalPeerFixtureCase, ...] = (
    "multi-device",
    "combo-device",
    "peer-control",
    "peer-fault",
    "peer-translator-control",
    "serial-control",
    "serial-fault",
    "serial-reference-fault",
    "serial-connector-control",
    "serial-connector-fault",
    "serial-optical-isolation-control",
    "serial-label-control",
    "serial-label-fault",
    "component-peer-control",
    "component-peer-fault",
)
SPI_PEER_FIXTURE_CASES: tuple[DigitalPeerFixtureCase, ...] = (
    "peer-control",
    "peer-fault",
    "peer-translator-control",
)
SERIAL_PEER_FIXTURE_CASES: tuple[DigitalPeerFixtureCase, ...] = (
    "serial-control",
    "serial-fault",
    "serial-reference-fault",
)
SERIAL_CONNECTOR_REFERENCE_CASES: tuple[DigitalPeerFixtureCase, ...] = (
    "serial-connector-control",
    "serial-connector-fault",
    "serial-optical-isolation-control",
)
SERIAL_CONNECTOR_REVIEW_CASES: tuple[DigitalPeerFixtureCase, ...] = (
    "serial-connector-control",
    "serial-connector-fault",
)
SERIAL_LABEL_REFERENCE_CASES: tuple[DigitalPeerFixtureCase, ...] = (
    "serial-label-control",
    "serial-label-fault",
)
COMPONENT_PEER_FIXTURE_CASES: tuple[DigitalPeerFixtureCase, ...] = (
    "component-peer-control",
    "component-peer-fault",
)


@dataclass(frozen=True, slots=True)
class NativeErcRunEvidence:
    """Normalized ERC output for one native run."""

    kicad_version: str
    normalized_sha256: str
    warning_types: tuple[str, ...]
    error_types: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.kicad_version:
            raise ValueError("ERC evidence must identify its KiCad version")
        if re.fullmatch(r"[0-9a-f]{64}", self.normalized_sha256) is None:
            raise ValueError("Normalized ERC digest must be a lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class DigitalPeerFixtureEvidence:
    """Complete repeatable native evidence for one source fixture."""

    case: DigitalPeerFixtureCase
    source: DigitalPeerFixtureSource
    netlists: NativeRunPair[NativeNetlistRunEvidence]
    component_erc: NativeRunPair[NativeErcRunEvidence] | None = None

    def require_component_erc(self) -> NativeRunPair[NativeErcRunEvidence]:
        """Return ERC runs for a component-peer fixture or fail explicitly."""
        if self.component_erc is None:
            raise ValueError(f"Fixture {self.case} has no component-peer ERC evidence")
        return self.component_erc


class DigitalPeerLog(Protocol):
    directory: Path

    def event(self, stage: str, status: str, **details: str | float) -> None: ...


@dataclass(frozen=True, slots=True)
class DigitalPeerFixtureContext:
    """Pinned native fixture run plus its validated, named evidence records."""

    root: Path
    project: str
    config: ProjectConfig
    pinned: str
    log: DigitalPeerLog
    scratch: Path
    fixture_root: Path
    fixtures: Mapping[DigitalPeerFixtureCase, DigitalPeerFixtureEvidence]

    def __post_init__(self) -> None:
        fixture_records = dict(self.fixtures)
        if set(fixture_records) != set(FIXTURE_CASES):
            missing = sorted(set(FIXTURE_CASES) - set(fixture_records))
            extra = sorted(set(fixture_records) - set(FIXTURE_CASES))
            raise ValueError(f"Digital-peer fixture cases differ: missing={missing}, extra={extra}")
        for case, evidence in fixture_records.items():
            if evidence.case != case:
                raise ValueError(f"Digital-peer fixture key {case} does not match its evidence")
            has_erc = evidence.component_erc is not None
            if has_erc != (case in COMPONENT_PEER_FIXTURE_CASES):
                raise ValueError(f"Digital-peer fixture {case} has an invalid ERC evidence shape")
            if evidence.component_erc is not None and any(
                run.kicad_version != self.config.kicad_version
                for run in (evidence.component_erc.first, evidence.component_erc.repeat)
            ):
                raise ValueError(
                    f"Digital-peer fixture {case} ERC version differs from its toolchain"
                )
        object.__setattr__(self, "fixtures", MappingProxyType(fixture_records))

    def fixture(self, case: DigitalPeerFixtureCase) -> DigitalPeerFixtureEvidence:
        """Return the evidence record for one declared fixture case."""
        try:
            return self.fixtures[case]
        except KeyError as error:
            raise ValueError(f"Unknown digital-peer fixture case: {case}") from error

    @property
    def observed(self) -> NetlistContract:
        """Compatibility view of the primary SPI participant netlist."""
        return self.fixture("multi-device").netlists.first.contract
