"""Keep two-pin connector-return rules reachable from tooling-owned fixtures."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import candidates
from tests.design_lint_fixtures.rs485_connector_return import two_pin_rs485_connector_netlist
from tests.design_lint_fixtures.usb2_connector_return import two_pin_usb2_connector_netlist
from tests.design_lint_fixtures.usb_superspeed_connector_return import (
    two_pin_usb_superspeed_connector_netlist,
)

_RETURN_REVIEW_RULES = frozenset(
    {
        "connector.rs485_pair_without_return_review",
        "connector.usb2_pair_without_return_review",
        "connector.usb_superspeed_pair_without_return_review",
    }
)


def connector_return_catalog_rule_ids() -> set[str]:
    """Return the lint IDs emitted by focused RS-485 and USB connector cases."""
    return {
        item.rule_id
        for observed in (
            two_pin_rs485_connector_netlist(),
            two_pin_usb2_connector_netlist(),
            two_pin_usb_superspeed_connector_netlist(),
        )
        for item in candidates(observed)
        if item.rule_id in _RETURN_REVIEW_RULES
    }
