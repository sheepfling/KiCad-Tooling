"""Catalog reachability cases for source-mapped connector roles and domains."""

from __future__ import annotations

import tests.test_connector_mapped_interface_other_named_rail as _mapped_other_rail
import tests.test_connector_mapped_interface_other_unassigned as _mapped_other_contact
import tests.test_connector_mapped_interface_power_contact_unassigned as _mapped_power_contact
import tests.test_connector_mapped_interface_shield_on_return_net as _mapped_shield_return
import tests.test_connector_mapped_interface_shield_on_supply_rail as _mapped_shield_supply
import tests.test_connector_mapped_interface_signal_on_named_rail as _mapped_signal_rail
from tests.design_lint_fixtures.connector_mapped_peer_return_split import (
    mapped_peer_return_coverage,
    mapped_peer_return_netlist,
    mapped_peer_return_report,
)


def mapped_connector_rule_ids() -> set[str]:
    """Reach mapped contact-role and return-domain split findings together."""
    power, _ = _mapped_power_contact._report(_mapped_power_contact._source(), role="supply")
    other, _ = _mapped_other_contact._report()
    other_rail, _ = _mapped_other_rail._report(_mapped_other_rail._netlist())
    signal, _ = _mapped_signal_rail._report(
        _mapped_signal_rail.mapped_named_rail_netlist(target_net="GND")
    )
    shield_return, _ = _mapped_shield_return._report(
        _mapped_shield_return.mapped_named_rail_netlist(target_net="RET")
    )
    shield_supply, _ = _mapped_shield_supply._report(
        _mapped_shield_supply.mapped_named_rail_netlist(target_net="+5V")
    )
    mapped_returns = mapped_peer_return_netlist()
    mapped_return_report, _ = mapped_peer_return_report(
        mapped_returns,
        coverage=mapped_peer_return_coverage(mapped_returns),
    )
    return {
        item.rule_id
        for report in (
            power,
            other,
            other_rail,
            signal,
            shield_return,
            shield_supply,
            mapped_return_report,
        )
        for item in report.findings
    }
