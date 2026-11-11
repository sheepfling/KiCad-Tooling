"""Deterministic routed differential-pair skew analysis for exact project maps."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence, map_sha256
from .model_primitives import Digest
from .netlist_contract_models import NetlistContract
from .pcb_differential_pair_skew_models import (
    PcbDifferentialPairRouteSkewEntry,
    PcbDifferentialPairRouteSkewReport,
)
from .pcb_signal_path_native_route import measure_project_mapped_signal_path
from .pcb_signal_path_rule_models import PcbSignalPathRuleMap
from .source_inventory_fingerprint import source_inventory_sha256
from .source_state_models import SourceHashInventory

RouteSkewMode = Literal["review", "block", "off"]


def measure_differential_pair_route_skew(
    requirements: PcbSignalPathRuleMap,
    observed: NetlistContract,
    evidence: PcbGeometrySourceEvidence,
    source_hashes: SourceHashInventory,
    netlist_sha256: Digest,
    mode: RouteSkewMode,
) -> PcbDifferentialPairRouteSkewReport:
    """Measure exact mapped route lengths against each authored bundle maximum."""
    requirement_sha256 = map_sha256(requirements)
    skew_bundles = tuple(item for item in requirements.bundles if item.max_skew is not None)
    if not skew_bundles:
        return PcbDifferentialPairRouteSkewReport(map_sha256=requirement_sha256)
    if mode == "off":
        return PcbDifferentialPairRouteSkewReport(
            status="DISABLED",
            mode=mode,
            map_sha256=requirement_sha256,
        )

    paths = {item.id.casefold(): item for item in requirements.paths}
    entries: list[PcbDifferentialPairRouteSkewEntry] = []
    for bundle in sorted(skew_bundles, key=lambda item: item.id.casefold()):
        if bundle.max_skew is None:
            continue
        members = tuple(
            measure_project_mapped_signal_path(
                paths[path_id.casefold()],
                observed=observed,
                evidence=evidence,
            )
            for path_id in sorted(bundle.path_ids, key=str.casefold)
        )
        unresolved = tuple(item for item in members if item.status != "RESOLVED")
        if unresolved:
            entries.append(
                PcbDifferentialPairRouteSkewEntry(
                    bundle_id=bundle.id,
                    max_skew_nm=bundle.max_skew.max_nm,
                    status="INCOMPLETE",
                    paths=members,
                    issue="; ".join(
                        f"{item.path_id}: {item.issue}" for item in unresolved if item.issue
                    ),
                )
            )
            continue
        lengths = tuple(item.length_nm for item in members)
        skew = max(item for item in lengths if item is not None) - min(
            item for item in lengths if item is not None
        )
        entries.append(
            PcbDifferentialPairRouteSkewEntry(
                bundle_id=bundle.id,
                max_skew_nm=bundle.max_skew.max_nm,
                measured_skew_nm=skew,
                status="WITHIN_LIMIT" if skew <= bundle.max_skew.max_nm else "EXCEEDS_LIMIT",
                paths=members,
            )
        )

    return PcbDifferentialPairRouteSkewReport(
        status="COMPLETE"
        if all(item.status == "WITHIN_LIMIT" for item in entries)
        else "INCOMPLETE",
        mode=mode,
        map_sha256=requirement_sha256,
        source_inventory_sha256=source_inventory_sha256(source_hashes),
        netlist_sha256=netlist_sha256,
        board_path=evidence.board_path,
        board_sha256=evidence.board_sha256,
        snapshot_path=evidence.snapshot_relative_path,
        snapshot_sha256=evidence.snapshot_sha256,
        command_path=PurePosixPath(evidence.snapshot_relative_path)
        .with_name(evidence.command_path.name)
        .as_posix(),
        command_sha256=evidence.command_sha256,
        probe_sha256=evidence.probe_sha256,
        kicad_version=evidence.snapshot.kicad_version,
        image=evidence.snapshot.image,
        entries=tuple(entries),
    )
