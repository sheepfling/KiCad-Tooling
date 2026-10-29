"""Hash-seed report cases for crossed RS-485 A/B line labels."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_line_label_mismatch import (
    rs485_line_label_mismatch_netlist,
)
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-rs485-line-label-mismatch-fault",
        coach(rs485_line_label_mismatch_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-rs485-line-label-mismatch-control",
        coach(rs485_line_label_mismatch_netlist(crossed=False)),
        DesignLintPolicy(),
    )
    return {
        "rs485_line_label_mismatch_fault": fault.model_dump(mode="json"),
        "rs485_line_label_mismatch_control": control.model_dump(mode="json"),
    }
