"""Synthetic findings for every mapped regulator-support rule."""

from __future__ import annotations

import tests.test_regulator_support_pin_net_coverage as _support_net_coverage
import tests.test_regulator_support_pin_net_map as _support_pin_net
import tests.test_regulator_support_pin_roles as _support_pin_roles
from tests.regulator_support_pin_net_support import support_pin_netlist


def regulator_support_rule_ids() -> frozenset[str]:
    """Return findings for authored role, assignment, and map-coverage faults."""
    reports = (
        _support_pin_roles.lint(
            _support_pin_roles.support_netlist(fault="wrong-optocoupler-function")
        ),
        _support_pin_net._report(support_pin_netlist(fault="wrong-net")),
        _support_net_coverage._report(),
    )
    return frozenset(item.rule_id for report in reports for item in report.findings)
