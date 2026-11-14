"""Numbered negative supply rail reports for hash-seed probes."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures import coach
from tests.json_types import JsonObject


def _report(*, common: bool) -> JsonObject:
    nets = (
        {"-5V_1": ("J1.3", "J2.3")}
        if common
        else {
            "-5V_1": ("J1.3",),
            "-5V_2": ("J2.3",),
        }
    )
    observed = NetlistContract(components={}, nets=nets)
    project_id = (
        "synthetic-negative-numbered-rail-control"
        if common
        else ("synthetic-negative-numbered-rail-fault")
    )
    return evaluate(project_id, coach(observed), DesignLintPolicy()).model_dump(mode="json")


def report_cases() -> JsonObject:
    """Build fault/control reports for the signed numbered rail heuristic."""
    return {
        "numbered_negative_power_rail_fault": _report(common=False),
        "numbered_negative_power_rail_control": _report(common=True),
    }
