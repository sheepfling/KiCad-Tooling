"""Review open named power-input pins across footprint-alias connectors."""

from __future__ import annotations

from .connector_footprint_open_named_candidates import open_named_outlier_candidates
from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinScan
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate

RULE_ID: DesignLintRuleId = "connector.footprint_named_power_input_open_outlier"


def footprint_named_power_input_open_outlier_candidates(
    scan: ConnectorFootprintPeerPinScan,
) -> tuple[Candidate, ...]:
    """Review an explicit power-input contact left open on a footprint-alias peer."""
    records = tuple(
        item
        for item in scan.open_outliers
        if item.pin_electrical_type.strip().casefold() == "power_in"
        and not pin_function_is_generic(item.pin_function)
        and not is_named_supply_function(item.pin_function)
        and not is_return_function(item.pin_function)
    )
    return open_named_outlier_candidates(records, rule_id=RULE_ID, role_label="power-input")
