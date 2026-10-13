"""Named connector power-alias reports for cross-process determinism checks."""

from __future__ import annotations

import hashlib
from typing import Literal

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.connector_named_power_aliases import (
    named_connector_power_alias_netlist,
)


def _named_power_alias_report(
    direction: Literal["input", "output"], *, split: bool
) -> dict[str, object]:
    electrical_type = "power_in" if direction == "input" else "power_out"
    function = "BIAS_IN" if direction == "input" else "BIAS_OUT"
    part_id = f"SYNTHETIC-NAMED-{direction.upper()}-001"
    assignments = (
        ("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B") if split else ("SYNTHETIC_RAIL", "SYNTHETIC_RAIL")
    )
    observed = named_connector_power_alias_netlist(
        assignments=assignments,
        part_ids=(part_id, part_id),
        target_functions=(function, function),
        target_types=(electrical_type, electrical_type),
    )
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        f"synthetic-named-connector-power-{direction}-"
        f"{'divergence' if split else 'common-control'}",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, object]:
    """Return fault/control reports for named input and output alias rules."""
    return {
        "named_connector_power_input_divergence_fault": _named_power_alias_report(
            "input", split=True
        ),
        "named_connector_power_input_common_control": _named_power_alias_report(
            "input", split=False
        ),
        "named_connector_power_output_divergence_fault": _named_power_alias_report(
            "output", split=True
        ),
        "named_connector_power_output_common_control": _named_power_alias_report(
            "output", split=False
        ),
    }
