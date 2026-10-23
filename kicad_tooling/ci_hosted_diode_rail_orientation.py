"""Exact-version native acceptance for diode rail-orientation lint."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_component_lint import component_lint_fixture_lane
from .hwrepo.component_diode_rail_orientation import RULE_ID

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

DIODE_RAIL_FIXTURE_CASES = {
    "fault_numeric": "diode-rail-orientation-native/fault.kicad_sch",
    "fault_return": "diode-rail-orientation-native/fault-return.kicad_sch",
    "control": "diode-rail-orientation-native/control.kicad_sch",
}


def diode_rail_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Run exact-version fault/control exports for diode rail orientation."""
    component_lint_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        fixture_prefix="diode-rail-fixture",
        project_id_prefix="synthetic-diode-rail",
        rule_id=RULE_ID,
        fixtures=DIODE_RAIL_FIXTURE_CASES,
        expected_subjects={
            "fault_numeric": "D1: diode anode is below its cathode on named rails",
            "fault_return": "D1: diode anode is below its cathode on named rails",
            "control": None,
        },
    )
