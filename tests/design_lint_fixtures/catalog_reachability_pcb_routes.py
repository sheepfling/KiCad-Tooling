"""Synthetic PCB route cases for active-rule catalog reachability."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.design_lint_pcb_requirement_candidates import (
    pcb_requirement_coverage_candidates,
)
from kicad_tooling.hwrepo.pcb_differential_pair_route_skew import (
    measure_differential_pair_route_skew,
)
from kicad_tooling.hwrepo.pcb_drc_models import PcbSignalPathRuleCoverageReport
from tests.design_lint_fixtures.pcb_differential_pair_route_skew import (
    geometry_evidence as route_geometry_evidence,
)
from tests.design_lint_fixtures.pcb_differential_pair_route_skew import (
    route_map,
    route_snapshot,
)
from tests.design_lint_fixtures.pcb_differential_pair_route_skew import (
    source_hashes as route_source_hashes,
)
from tests.design_lint_fixtures.pcb_differential_pair_route_skew import (
    source_netlist as route_netlist,
)


def pcb_route_rule_ids(netlist_sha256: str) -> set[str]:
    """Return IDs surfaced by routed-skew and pair-layer-profile fault cases."""
    cases = (
        (route_map(), route_snapshot()),
        (
            route_map(maximum_skew_nm=0),
            route_snapshot(
                positive_length_nm=1_000_000,
                negative_length_nm=1_000_000,
                negative_layer_transition=True,
            ),
        ),
    )
    result: set[str] = set()
    for requirements, snapshot in cases:
        report = measure_differential_pair_route_skew(
            requirements,
            route_netlist(),
            route_geometry_evidence(Path("build"), snapshot),
            route_source_hashes(),
            netlist_sha256,
            "review",
        )
        result.update(
            item.rule_id
            for item in pcb_requirement_coverage_candidates(
                pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(route_skew=report)
            )
        )
    return result
