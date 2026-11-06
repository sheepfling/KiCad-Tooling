"""Source-bound mapped interface cases used by catalog reachability tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.signal_divider import (
    signal_divider_map,
    signal_divider_netlist,
)


def mapped_signal_divider_rule_ids() -> set[str]:
    """Reach the mapped-divider mismatch using its synthetic fault contract."""
    project_id = "synthetic-catalog-reachability-signal-divider"
    report = evaluate(
        project_id,
        coach(
            signal_divider_netlist(fault="top-resistor-value"),
            project_id=project_id,
        ),
        DesignLintPolicy(signal_divider_map=signal_divider_map()),
    )
    return {item.rule_id for item in report.findings}
