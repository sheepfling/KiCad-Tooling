"""Compatibility entry point for native polarized-capacitor fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_component_polarity import component_polarity_fixture_lane
from .hwrepo.component_polarized_capacitor_orientation import RULE_ID

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

POLARIZED_CAPACITOR_FIXTURE_CASES = {
    "fault": "polarized-capacitor-native/fault.kicad_sch",
    "control": "polarized-capacitor-native/control.kicad_sch",
}


def polarized_capacitor_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Run exact-version fault/control exports for polarized capacitors."""
    component_polarity_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        fixture_prefix="polarized-capacitor-fixture",
        project_id_prefix="synthetic-polarized-capacitor",
        rule_id=RULE_ID,
        fixtures=POLARIZED_CAPACITOR_FIXTURE_CASES,
        expected_subjects={
            "fault": "C1: polarized capacitor pin 1 is below pin 2",
            "control": None,
        },
    )
