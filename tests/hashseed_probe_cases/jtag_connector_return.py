"""JTAG connector return-review reports for hash-seed determinism probes."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.jtag_generic_connector_pair import generic_jtag_connector_netlist
from tests.json_types import JsonObject


def _report(*, return_identified: bool) -> JsonObject:
    connector_functions = tuple(f"Pin_{number}" for number in range(1, 5)) + (
        ("GND",) if return_identified else ("Pin_5",)
    )
    observed = generic_jtag_connector_netlist(connector_functions=connector_functions)
    netlist_sha256 = hashlib.sha256(model_json_bytes(observed)).hexdigest()
    project_id = (
        "synthetic-jtag-return-control" if return_identified else "synthetic-jtag-return-fault"
    )
    report = evaluate(
        project_id,
        coach(observed, netlist_sha256, project_id=project_id),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, JsonObject]:
    """Return complete missing-role fault and native-return control reports."""
    return {
        "jtag_connector_return_fault": _report(return_identified=False),
        "jtag_connector_return_control": _report(return_identified=True),
    }
