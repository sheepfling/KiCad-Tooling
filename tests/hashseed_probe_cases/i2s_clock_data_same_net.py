"""Cross-process report cases for I2S clock/data same-net review."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i2s_clock_data_same_net import i2s_clock_data_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    reports: JsonObject = {}
    for case, shared in (("fault", True), ("control", False)):
        project_id = f"synthetic-i2s-clock-data-{case}"
        observed = i2s_clock_data_netlist(shared=shared)
        netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
        result = evaluate(
            project_id,
            coach(observed, netlist_sha256, project_id=project_id),
            DesignLintPolicy(),
        )
        reports[f"i2s_clock_data_same_net_{case}"] = result.model_dump(mode="json")
    return reports
