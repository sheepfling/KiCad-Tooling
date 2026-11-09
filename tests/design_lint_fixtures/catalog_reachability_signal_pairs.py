"""Catalog-reachability cases for same-net protocol clock/data pairs."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import candidates
from tests.design_lint_fixtures.i2s_clock_frame_same_net import i2s_clock_frame_netlist
from tests.design_lint_fixtures.swd_signal_same_net import swd_signal_same_net_netlist


def signal_pair_same_net_rule_ids() -> set[str]:
    """Return active same-net protocol rules reached by synthetic pair faults."""
    sources = (i2s_clock_frame_netlist(), swd_signal_same_net_netlist())
    return {candidate.rule_id for source in sources for candidate in candidates(source)}
