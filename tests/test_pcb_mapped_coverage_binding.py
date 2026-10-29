"""Source and map identity checks for project-mapped PCB coverage reports."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures.pcb_reference_planes import (
    coach as reference_plane_coach,
)
from tests.design_lint_fixtures.pcb_reference_planes import (
    mapping as reference_plane_mapping,
)
from tests.design_lint_fixtures.pcb_reference_planes import (
    report as reference_plane_report,
)
from tests.design_lint_fixtures.pcb_reference_planes import (
    snapshot as reference_plane_snapshot,
)
from tests.design_lint_fixtures.pcb_reference_planes import (
    track,
)
from tests.design_lint_fixtures.pcb_switching_loop import (
    coach as switching_loop_coach,
)
from tests.design_lint_fixtures.pcb_switching_loop import (
    coverage as switching_loop_coverage,
)
from tests.design_lint_fixtures.pcb_switching_loop import (
    mapping as switching_loop_mapping,
)
from tests.design_lint_fixtures.pcb_switching_loop import (
    snapshot as switching_loop_snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.return_path_lint]


def test_switching_loop_requires_current_map_and_board() -> None:
    mapped = switching_loop_mapping()
    measured = switching_loop_coverage(mapped, switching_loop_snapshot())
    board_path = "projects/synthetic/board.kicad_pcb"
    stale_board = switching_loop_coach().model_copy(
        update={"source_hashes": {board_path: "d" * 64}}
    )

    stale_source_report = evaluate(
        "synthetic-loop",
        stale_board,
        DesignLintPolicy(pcb_switching_loop_map=mapped),
        pcb_switching_loop_coverage=measured,
    )
    stale_map = mapped.model_copy(update={"basis": "Changed authored map"})
    stale_map_report = evaluate(
        "synthetic-loop",
        switching_loop_coach(),
        DesignLintPolicy(pcb_switching_loop_map=stale_map),
        pcb_switching_loop_coverage=measured,
    )

    assert stale_source_report.pcb_switching_loop.status == "BLOCKED"
    assert stale_map_report.pcb_switching_loop.status == "BLOCKED"


def test_reference_plane_requires_current_map_and_board() -> None:
    mapped = reference_plane_mapping()
    measured = reference_plane_report(mapped, reference_plane_snapshot(track()))
    board_path = "projects/synthetic/board.kicad_pcb"
    stale_board = reference_plane_coach().model_copy(
        update={"source_hashes": {board_path: "d" * 64}}
    )

    stale_source_report = evaluate(
        "synthetic-plane",
        stale_board,
        DesignLintPolicy(pcb_reference_plane_map=mapped),
        pcb_reference_plane_coverage=measured,
    )
    stale_map = mapped.model_copy(update={"basis": "Changed authored map"})
    stale_map_report = evaluate(
        "synthetic-plane",
        reference_plane_coach(),
        DesignLintPolicy(pcb_reference_plane_map=stale_map),
        pcb_reference_plane_coverage=measured,
    )

    assert stale_source_report.pcb_reference_plane.status == "BLOCKED"
    assert stale_map_report.pcb_reference_plane.status == "BLOCKED"


def test_explicit_off_disables_mapped_routes_without_maps() -> None:
    native = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-disabled-routes",
        observed=NetlistContract(components={}, nets={}),
    )
    policy = DesignLintPolicy(
        rules=tuple(
            DesignLintRuleOverride(rule_id=rule_id, mode="off", reason="Synthetic disposition")
            for rule_id in (
                "pcb.switching_loop_geometry",
                "pcb.reference_plane_coverage",
                "pcb.protection_entry_path",
            )
        )
    )

    report = evaluate("synthetic-disabled-routes", native, policy)

    assert report.pcb_switching_loop.status == "DISABLED"
    assert report.pcb_reference_plane.status == "DISABLED"
    assert report.pcb_protection_path.status == "DISABLED"
