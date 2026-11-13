"""Aggregate synthetic reachability for omitted PCB track scopes."""

from __future__ import annotations

from tests.design_lint_fixtures.catalog_reachability_pcb_signal_path_unmapped import (
    unmapped_signal_path_rule_ids,
)
from tests.design_lint_fixtures.catalog_reachability_pcb_track_angle_unmapped import (
    unmapped_track_angle_rule_ids,
)
from tests.design_lint_fixtures.catalog_reachability_pcb_track_width_unmapped import (
    unmapped_track_width_rule_ids,
)


def unmapped_track_rule_ids() -> set[str]:
    """Return active-rule IDs emitted by synthetic unmapped track-scope cases."""
    return (
        unmapped_track_angle_rule_ids()
        | unmapped_track_width_rule_ids()
        | unmapped_signal_path_rule_ids()
    )
