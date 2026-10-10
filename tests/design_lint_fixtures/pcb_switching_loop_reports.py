"""Synthetic switching-loop inputs for focused regression suites."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbSwitchingLoopCoverageReport,
    PcbSwitchingLoopMap,
)
from kicad_tooling.hwrepo.pcb_switching_loop_review import pcb_switching_loop_entries
from tests.design_lint_fixtures.pcb_switching_loop_routes import routed_mapping, routed_snapshot


def coverage(
    specification: PcbSwitchingLoopMap, observed: PcbConnectivitySnapshot
) -> PcbSwitchingLoopCoverageReport:
    entries = pcb_switching_loop_entries(specification, observed)
    return PcbSwitchingLoopCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=hashlib.sha256(specification.model_dump_json().encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=observed.board_sha256,
        snapshot_path="build/design-lint/switching-loop/snapshot.json",
        snapshot_sha256=hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        probe_sha256=observed.probe_sha256,
        kicad_version=observed.kicad_version,
        image=observed.image,
        netlist_sha256="f" * 64,
        entries=entries,
    )


def coach() -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-loop",
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256="f" * 64,
    )


def design_lint_report(*, ambiguous_route: bool):
    """Build a complete synthetic routed-loop report for hash-seed coverage."""
    specification = routed_mapping()
    observed = routed_snapshot(branch=ambiguous_route)
    return evaluate(
        "synthetic-switching-loop-route-ambiguity",
        coach(),
        DesignLintPolicy(pcb_switching_loop_map=specification),
        pcb_switching_loop_coverage=coverage(specification, observed),
    )
