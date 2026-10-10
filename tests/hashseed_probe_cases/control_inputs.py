"""Control-input reports for deterministic synthetic verification."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach, control_input_pins


def _control_input_report(*, connected: bool) -> dict[str, object]:
    observed = control_input_pins(connected=connected)
    digest = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-control-input-hash-seed",
        coach(observed, digest),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, object]:
    return {
        "control_input_unconnected_fault": _control_input_report(connected=False),
        "control_input_connected_control": _control_input_report(connected=True),
    }
