"""Cross-process reports for same-role serial connector/IC endpoint wiring."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.serial_endpoint_role_collision import (
    serial_endpoint_role_netlist,
)
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-serial-endpoint-role-collision-fault",
        coach(serial_endpoint_role_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-serial-endpoint-role-collision-control",
        coach(serial_endpoint_role_netlist(collision=False)),
        DesignLintPolicy(),
    )
    return {
        "serial_endpoint_role_collision_fault": fault.model_dump(mode="json"),
        "serial_endpoint_role_collision_control": control.model_dump(mode="json"),
    }
