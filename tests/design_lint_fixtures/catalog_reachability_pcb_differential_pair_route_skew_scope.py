"""Synthetic reachability for pair skew bounds without signal-path bundles."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint_candidate_aggregation import candidates
from kicad_tooling.hwrepo.models import NetlistContract
from tests.test_pcb_drc_coverage import pair_map


def differential_pair_route_skew_scope_rule_ids() -> set[str]:
    """Return candidates emitted from a skew-bounded pair map without route scope."""
    return {
        item.rule_id
        for item in candidates(
            NetlistContract(components={}, nets={}),
            pcb_differential_pair_rule_map=pair_map(),
            is_pcb_project=True,
        )
    }
