"""Aggregate synthetic reachability for unmapped PCB rule scopes."""

from __future__ import annotations

from tests.design_lint_fixtures.catalog_reachability_pcb_differential_pair_unmapped import (
    unmapped_differential_pair_rule_ids,
)
from tests.design_lint_fixtures.catalog_reachability_pcb_drc_exact_netclass_scope import (
    pcb_drc_exact_netclass_scope_rule_ids,
)
from tests.design_lint_fixtures.catalog_reachability_pcb_exact_net_scope import (
    exact_net_scope_rule_ids,
)
from tests.design_lint_fixtures.catalog_reachability_pcb_track_unmapped import (
    unmapped_track_rule_ids,
)


def unmapped_pcb_scope_rule_ids() -> set[str]:
    """Return active IDs emitted by synthetic unmapped PCB scope cases."""
    return (
        unmapped_track_rule_ids()
        | unmapped_differential_pair_rule_ids()
        | exact_net_scope_rule_ids()
        | pcb_drc_exact_netclass_scope_rule_ids()
    )
