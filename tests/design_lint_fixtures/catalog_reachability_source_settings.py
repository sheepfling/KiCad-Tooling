"""Source-bound settings rule reachability inputs for the design-lint catalog."""

from __future__ import annotations

from tests.design_lint_fixtures.catalog_reachability_pcb_drc_nonstring_severity_values import (
    pcb_drc_nonstring_severity_value_rule_ids,
)
from tests.design_lint_fixtures.catalog_reachability_pcb_drc_severity_keys import (
    pcb_drc_unknown_severity_key_rule_ids,
)
from tests.design_lint_fixtures.catalog_reachability_pcb_drc_severity_values import (
    pcb_drc_invalid_severity_value_rule_ids,
)
from tests.design_lint_fixtures.schematic_erc_global_severity import (
    schematic_erc_global_severity_rule_ids,
)


def source_setting_rule_ids() -> frozenset[str]:
    """Reach source-bound schematic and PCB settings review rules."""
    return (
        schematic_erc_global_severity_rule_ids()
        | pcb_drc_unknown_severity_key_rule_ids()
        | pcb_drc_invalid_severity_value_rule_ids()
        | pcb_drc_nonstring_severity_value_rule_ids()
    )
