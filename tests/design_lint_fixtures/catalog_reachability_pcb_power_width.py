"""Reachability input for power-pin width-map coverage review."""

from kicad_tooling.hwrepo.pcb_power_pin_track_width_coverage import (
    power_pin_net_track_width_map_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectKind
from tests.design_lint_fixtures.pcb_power_pin_track_width import native_power_netlist


def power_pin_width_map_rule_ids() -> set[str]:
    return {
        item.rule_id
        for item in power_pin_net_track_width_map_candidates(
            native_power_netlist(), ProjectKind.PCB, None, "a" * 64
        )
    }
