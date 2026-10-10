"""Resolve source-bound STM32 pin-map coverage and merge its source hashes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from .contracts import repo_path
from .evidence import digest
from .models import (
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
    Stm32PinMapCoverageReport,
    Stm32PinMapMismatch,
)
from .stm32_pin_map import (
    CubeMxDocument,
    parse_cubemx_ioc,
    stm32_pin_map_mismatches,
    stm32_pin_map_sha256,
    unmapped_stm32_devices,
)


def resolve_stm32_pin_map_coverage(
    coach: ContractCoachReport,
    policy: DesignLintPolicy,
    coverage: Stm32PinMapCoverageReport | None,
) -> tuple[Stm32PinMapCoverageReport, dict[str, str]]:
    """Apply the authored STM32 lint mode and bind IOC source hashes."""
    override = next(
        (item for item in policy.rules if item.rule_id == "mcu.stm32_cubemx_pin_map"),
        None,
    )
    mode = "review" if override is None else override.mode
    if coverage is None:
        if mode == "off":
            coverage = Stm32PinMapCoverageReport(
                status="DISABLED",
                mode="off",
                map_sha256=(
                    stm32_pin_map_sha256(policy.stm32_pin_maps) if policy.stm32_pin_maps else None
                ),
            )
        elif policy.stm32_pin_maps:
            coverage = Stm32PinMapCoverageReport(
                status="BLOCKED",
                mode=mode,
                map_sha256=stm32_pin_map_sha256(policy.stm32_pin_maps),
                issue="Source-bound CubeMX IOC contents were not supplied for the configured pin map",
            )
        elif coach.observed is not None and coach.netlist_sha256 is not None:
            unmapped = unmapped_stm32_devices(
                coach.observed, (), netlist_sha256=coach.netlist_sha256
            )
            coverage = Stm32PinMapCoverageReport(
                status="INCOMPLETE" if unmapped else "NOT_REQUESTED",
                mode=mode if unmapped else None,
                netlist_sha256=coach.netlist_sha256 if unmapped else None,
                unmapped_devices=unmapped,
            )
        else:
            coverage = Stm32PinMapCoverageReport()

    source_hashes = dict(coach.source_hashes)
    for source_path, source_sha256 in coverage.ioc_source_hashes.items():
        previous_sha256 = source_hashes.get(source_path)
        if previous_sha256 is not None and previous_sha256 != source_sha256:
            raise ValueError(f"Conflicting source hashes for CubeMX input {source_path}")
        source_hashes[source_path] = source_sha256
    return coverage, source_hashes


def scan_stm32_pin_maps(
    root: Path,
    policy: DesignLintPolicy,
    observed: NetlistContract,
    netlist_sha256: str | None,
) -> Stm32PinMapCoverageReport:
    """Read and hash project-local CubeMX files before comparing authored pin maps."""
    root = root.resolve()
    override = next(
        (item for item in policy.rules if item.rule_id == "mcu.stm32_cubemx_pin_map"),
        None,
    )
    mode: Literal["review", "block", "off"] = "review" if override is None else override.mode
    map_sha256 = stm32_pin_map_sha256(policy.stm32_pin_maps) if policy.stm32_pin_maps else None
    if mode == "off":
        return Stm32PinMapCoverageReport(
            status="DISABLED",
            mode=mode,
            map_sha256=map_sha256,
        )
    if netlist_sha256 is None:
        if policy.stm32_pin_maps:
            return Stm32PinMapCoverageReport(
                status="BLOCKED",
                mode=mode,
                map_sha256=map_sha256,
                issue="Source-bound native netlist hash is unavailable for STM32 pin-map review",
            )
        return Stm32PinMapCoverageReport()
    if not policy.stm32_pin_maps:
        unmapped = unmapped_stm32_devices(observed, (), netlist_sha256=netlist_sha256)
        return Stm32PinMapCoverageReport(
            status="INCOMPLETE" if unmapped else "NOT_REQUESTED",
            mode=mode if unmapped else None,
            netlist_sha256=netlist_sha256 if unmapped else None,
            unmapped_devices=unmapped,
        )

    source_hashes: dict[str, str] = {}
    documents: dict[str, CubeMxDocument] = {}
    mismatches: list[Stm32PinMapMismatch] = []
    try:
        for pin_map in policy.stm32_pin_maps:
            source_path = repo_path(root, pin_map.ioc_path)
            relative_path = source_path.relative_to(root).as_posix()
            before = digest(source_path)
            content = source_path.read_bytes()
            source_sha256 = hashlib.sha256(content).hexdigest()
            if before != source_sha256 or digest(source_path) != source_sha256:
                raise ValueError(f"CubeMX IOC changed while being read: {relative_path}")
            source_hashes[relative_path] = source_sha256
            document = documents.get(relative_path)
            if document is None:
                document = parse_cubemx_ioc(content)
                documents[relative_path] = document
            if document.issues:
                raise ValueError(
                    f"CubeMX IOC has unsupported or ambiguous pin assignments in "
                    f"{relative_path}: {document.issues[0]}"
                )
            mismatches.extend(
                stm32_pin_map_mismatches(
                    pin_map,
                    observed,
                    document,
                    ioc_sha256=source_sha256,
                    map_sha256=map_sha256 or "",
                    netlist_sha256=netlist_sha256,
                )
            )
        mapped = tuple(item.reference for item in policy.stm32_pin_maps)
        unmapped = unmapped_stm32_devices(observed, mapped, netlist_sha256=netlist_sha256)
        return Stm32PinMapCoverageReport(
            status="INCOMPLETE" if unmapped else "COMPLETE",
            mode=mode,
            map_sha256=map_sha256,
            netlist_sha256=netlist_sha256,
            ioc_source_hashes=source_hashes,
            mapped_pin_count=sum(len(item.pins) for item in policy.stm32_pin_maps),
            excluded_pin_count=sum(len(item.exclusions) for item in policy.stm32_pin_maps),
            mismatches=tuple(mismatches),
            unmapped_devices=unmapped,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        return Stm32PinMapCoverageReport(
            status="BLOCKED",
            mode=mode,
            map_sha256=map_sha256,
            netlist_sha256=netlist_sha256,
            ioc_source_hashes=source_hashes,
            issue=f"Could not compare the project STM32 pin map with source evidence: {exc}",
        )
