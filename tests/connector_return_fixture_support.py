"""Synthetic typed-netlist registry for hosted connector-return acceptance."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
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
from tests.design_lint_fixtures.repeated_signal_pin_functions import (
    repeated_signal_pin_component,
    repeated_signal_pin_with_unassigned_member,
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
    observed.update(
        {
            "repeated-signal-pin-fault": repeated_signal_pin_component(split=True),
            "repeated-signal-pin-control": repeated_signal_pin_component(split=False),
            "repeated-signal-pin-unassigned-fault": repeated_signal_pin_with_unassigned_member(),
            "repeated-signal-pin-unassigned-control": repeated_signal_pin_component(split=False),
            "mapped-distinct-signals-share-net": _mapped_signal_assignments(shared=True),
            "mapped-same-signal-split-nets": _mapped_signal_assignments(shared=False),
            "stateful-contact-fault": _stateful_contact(tip_pair_same_net=True),
            "stateful-contact-control": _stateful_contact(tip_pair_same_net=False),
        }
    )
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


def _mapped_signal_assignments(*, shared: bool) -> NetlistContract:
    """Build mapped connector contacts that share or split their assigned nets."""
    nets = (
        {"SHARED_SIGNAL_NET": ("J1.1", "J1.2")}
        if shared
        else {"CONTACT_NET_A": ("J1.1",), "CONTACT_NET_B": ("J1.2",)}
    )
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={"J1": "Synthetic:MappedConnector"},
        component_pin_numbers={"J1": ("1", "2")},
        pin_functions={"J1.1": "1", "J1.2": "2"},
    )


def _stateful_contact(*, tip_pair_same_net: bool) -> NetlistContract:
    """Build exact synthetic audio-jack contacts for the stateful-map lane."""
    nets = (
        {"AUDIO_TIP": ("J1.1", "J1.2")}
        if tip_pair_same_net
        else {"AUDIO_TIP": ("J1.1",), "AUDIO_TIP_SWITCH": ("J1.2",)}
    )
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic Audio Jack",
                footprint="Synthetic:AudioJack_2Contact",
                part_id="SYNTH-AUDIO-JACK-001",
            )
        },
        nets=nets,
        component_symbols={"J1": "Synthetic:AudioJack_2Contact"},
        component_pin_numbers={"J1": ("1", "2")},
    )
