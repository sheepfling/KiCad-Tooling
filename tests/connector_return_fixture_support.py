"""Synthetic typed-netlist registry for hosted connector-return acceptance."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import NetlistContract
from tests.component_peer_pin_support import generic_component_peer_power_assignment_netlist
from tests.component_peer_power_input_support import (
    generic_peer_power_input_netlist,
    named_peer_power_input_netlist,
)
from tests.connector_return_named_peer_cases import named_connector_peer_fixture_contracts
from tests.design_lint_fixtures.connector_named_power_peer_cases import (
    named_connector_power_peer_cases,
)
from tests.design_lint_fixtures.connector_peer_pin_cases import peer_pin_case_contracts
from tests.design_lint_fixtures.connector_power_cases import (
    connector_power_case_contracts,
    generic_component_power_input_cases,
    named_connector_power_pin_cases,
)
from tests.design_lint_fixtures.connector_return_cases import (
    pwm_return_case_contracts,
    ret_return_label_case_contracts,
    return_case_contracts,
    return_positive_rail_case_contracts,
)
from tests.design_lint_fixtures.named_component_power_pins import (
    named_component_return_pin_cases,
    named_component_supply_pin_cases,
)


def connector_return_fixture_contracts() -> dict[str, NetlistContract]:
    """Assemble the deterministic netlists for every hosted lane source case."""
    observed: dict[str, NetlistContract] = {}
    observed.update(return_case_contracts())
    observed.update(pwm_return_case_contracts())
    observed.update(ret_return_label_case_contracts())
    observed.update(return_positive_rail_case_contracts())
    observed.update(peer_pin_case_contracts())
    observed.update(named_connector_peer_fixture_contracts())
    observed.update(named_connector_power_peer_cases())
    observed.update(connector_power_case_contracts())
    observed.update(named_connector_power_pin_cases())
    observed.update(named_component_supply_pin_cases())
    observed.update(named_component_return_pin_cases())
    observed.update(generic_component_power_input_cases())
    observed.update(
        {
            "peer-generic-power-input-fault": generic_peer_power_input_netlist(),
            "peer-generic-power-input-control": generic_peer_power_input_netlist(
                assignments=("+3V3", "+3V3")
            ),
            "peer-named-power-input-open-fault": named_peer_power_input_netlist(),
            "peer-named-power-input-open-control": named_peer_power_input_netlist(
                assignments=("+3V3", "+3V3")
            ),
            "peer-named-power-input-divergence-fault": named_peer_power_input_netlist(
                assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B")
            ),
            "peer-named-power-input-divergence-control": named_peer_power_input_netlist(
                assignments=("+3V3", "+3V3")
            ),
            "peer-named-power-input-all-open-fault": named_peer_power_input_netlist(
                assignments=(None, None)
            ),
            "peer-named-power-input-all-open-control": named_peer_power_input_netlist(
                assignments=("+3V3", "+3V3")
            ),
            "component-peer-assignment-outlier-fault": (
                generic_component_peer_power_assignment_netlist(outlier_open=True)
            ),
            "component-peer-assignment-outlier-control": (
                generic_component_peer_power_assignment_netlist(outlier_open=False)
            ),
        }
    )
    return observed
