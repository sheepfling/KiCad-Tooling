"""Cross-process report cases for SWD signal same-net review."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.swd_signal_same_net import swd_signal_same_net_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    reports: JsonObject = {}
    for case, shared in (("fault", True), ("control", False)):
        project_id = f"synthetic-swd-signal-same-net-{case}"
        observed = swd_signal_same_net_netlist(shared=shared)
        netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
        result = evaluate(
            project_id,
            coach(observed, netlist_sha256, project_id=project_id),
            DesignLintPolicy(),
        )
        reports[f"swd_signal_same_net_{case}"] = result.model_dump(mode="json")
    return reports
