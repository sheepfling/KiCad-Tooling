"""Review mode-dependent named signal contacts open across connector aliases."""

from __future__ import annotations

from .connector_footprint_open_named_candidates import open_named_outlier_candidates
from .connector_footprint_peer_pin_types import (
    SIGNAL_ELECTRICAL_TYPES,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate

RULE_ID: DesignLintRuleId = "connector.footprint_named_signal_mode_dependent_open_outlier"
MODE_DEPENDENT_SIGNAL_TYPES = SIGNAL_ELECTRICAL_TYPES - {"input", "output"}


def footprint_named_signal_mode_dependent_open_outlier_candidates(
    scan: ConnectorFootprintPeerPinScan,
) -> tuple[Candidate, ...]:
    """Review named bidirectional or high-impedance signal pins open on some peers."""
    records = tuple(
        item
        for item in scan.open_outliers
        if item.pin_electrical_type.strip().casefold() in MODE_DEPENDENT_SIGNAL_TYPES
        and not pin_function_is_generic(item.pin_function)
        and not is_named_supply_function(item.pin_function)
        and not is_return_function(item.pin_function)
    )
    return open_named_outlier_candidates(
        records,
        rule_id=RULE_ID,
        role_label="mode-dependent signal",
    )
