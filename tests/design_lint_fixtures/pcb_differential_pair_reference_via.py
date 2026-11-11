"""Synthetic authored contracts for pair reference-via stitching review."""

from __future__ import annotations

import hashlib
from pathlib import Path

from kicad_tooling.hwrepo.design_lint_pcb_requirement_candidates import (
    pcb_requirement_coverage_candidates,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_drc_models import (
    PcbSignalPathRuleCoverageReport,
    PcbSignalPathRuleMap,
)
from tests.design_lint_fixtures.pcb_differential_pair_route_skew import (
    route_map,
    source_netlist,
)


def stitching_map(
    *,
    reference_net: str = "GND",
    maximum_distance_nm: int = 1_000_000,
) -> PcbSignalPathRuleMap:
    """Configure exact reference-net and proximity expectations for the synthetic pair."""
    base = route_map(maximum_skew_nm=10_000_000)
    bundle = base.bundles[0].model_copy(
        update={
            "max_skew": None,
            "reference_net": reference_net,
            "max_reference_via_distance_nm": maximum_distance_nm,
        }
    )
    payload = base.model_dump()
    payload["paths"] = tuple(
        {**path, "length": None, "edge_clearance": None} for path in payload["paths"]
    )
    payload["bundles"] = (bundle.model_dump(),)
    return PcbSignalPathRuleMap.model_validate(payload)


def stitching_netlist(*, include_reference: bool = True) -> NetlistContract:
    """Return the source-bound signal nets and optional authored reference domain."""
    base = source_netlist()
    nets = dict(base.nets)
    if include_reference:
        nets["GND"] = ("J1.3",)
    return NetlistContract(components={}, nets=nets)


def reference_via_candidate_ids(evidence_root: Path) -> set[str]:
    """Emit candidate IDs from a synthetic mapped pair with no reference via."""
    from kicad_tooling.hwrepo.pcb_differential_pair_reference_via_stitching import (
        measure_differential_pair_reference_via_stitching,
    )
    from tests.design_lint_fixtures.pcb_differential_pair_route_skew import (
        geometry_evidence,
        route_snapshot,
        source_hashes,
    )

    requirements = stitching_map()
    observed = stitching_netlist()
    evidence = geometry_evidence(
        evidence_root,
        route_snapshot(
            positive_length_nm=1_000_000,
            negative_length_nm=1_000_000,
            negative_layer_transition=True,
        ),
    )
    report = measure_differential_pair_reference_via_stitching(
        requirements,
        observed,
        evidence,
        source_hashes(),
        hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        "review",
    )
    coverage = PcbSignalPathRuleCoverageReport(reference_via_stitching=report)
    return {
        item.rule_id
        for item in pcb_requirement_coverage_candidates(pcb_signal_path_coverage=coverage)
    }
