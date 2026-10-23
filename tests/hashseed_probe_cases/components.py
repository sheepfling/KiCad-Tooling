"""Components report cases for deterministic synthetic verification."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.models import DesignLintPolicy, NetlistContract
from kicad_tooling.hwrepo.mosfet_stress import mosfet_stress_checks
from kicad_tooling.hwrepo.mosfet_stress_models import MosfetVoltageInterval
from tests.design_lint_fixtures import (
    coach,
)
from tests.design_lint_fixtures.bjt_base_bias import bjt_base_bias_netlist
from tests.design_lint_fixtures.bjt_base_drive import bjt_base_drive_netlist
from tests.design_lint_fixtures.bjt_collector_emitter_same_net import (
    bjt_base_emitter_netlist,
    bjt_collector_emitter_netlist,
)
from tests.design_lint_fixtures.bjt_terminal_order import bjt_terminal_order_netlist
from tests.design_lint_fixtures.diode_rail_orientation import netlist as diode_rail_netlist
from tests.design_lint_fixtures.mosfet_drain_source_same_net import mosfet_drain_source_netlist
from tests.design_lint_fixtures.mosfet_terminal_order import mosfet_terminal_order_netlist
from tests.test_led_output_heuristics import observed_report as led_output_observed_report
from tests.test_led_output_heuristics import output_led_netlist as led_output_netlist
from tests.test_mosfet_gate_connectivity import mosfet_netlist as mosfet_gate_netlist
from tests.test_mosfet_stress import multi_device_netlist, multi_device_requirement
from tests.test_two_pin_crystals import crystal_netlist
from tests.test_two_pin_diodes import diode_netlist
from tests.test_two_pin_ferrites import ferrite_netlist
from tests.test_two_pin_fuses import fuse_netlist
from tests.test_two_pin_switches import switch_netlist


def led_output_lint_report(*, topology: str) -> dict[str, object]:
    """Serialize direct-drive, parallel-resistor, or series-path LED evidence."""
    return led_output_observed_report(led_output_netlist(topology)).model_dump(mode="json")


def mosfet_stress_check_result(*, q2_over_limit: bool) -> dict[str, object]:
    """Serialize a multi-device MOSFET stress contract and its typed results."""
    requirement = multi_device_requirement(
        q2_drain_on=MosfetVoltageInterval(minimum_v=0.0, maximum_v=60.0) if q2_over_limit else None
    )
    observed = multi_device_netlist()
    checks = mosfet_stress_checks(requirement, observed)
    return {
        "requirements_sha256": hashlib.sha256(
            requirement.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "netlist_sha256": hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        "checks": [check.model_dump(mode="json") for check in checks],
    }


def source_bound_component_report(
    project_id: str,
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> dict[str, object]:
    """Serialize component lint against a hash of its normalized netlist."""
    digest = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    return evaluate(
        project_id,
        coach(observed, netlist_sha256=digest),
        policy or DesignLintPolicy(),
    ).model_dump(mode="json")


def diode_rail_orientation_report(*, anode_net: str, cathode_net: str) -> dict[str, object]:
    """Serialize a diode rail review with a digest of its normalized netlist."""
    observed = diode_rail_netlist(anode_net=anode_net, cathode_net=cathode_net)
    return source_bound_component_report("synthetic-diode-rail-return", observed)


def mosfet_gate_peer_report(*, has_driver: bool) -> dict[str, object]:
    """Serialize a supported MOSFET gate with and without a fitted net peer."""
    observed = mosfet_gate_netlist(gate_net_members=("U1.1",) if has_driver else None)
    return source_bound_component_report("synthetic-mosfet-gate-hashseed", observed)


def mosfet_terminal_order_report(*, reversed_order: bool) -> dict[str, object]:
    """Serialize an enabled MOSFET named-rail order fault or valid control."""
    observed = mosfet_terminal_order_netlist(reversed_order=reversed_order)
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="component.mosfet_terminal_order_on_named_rails",
                mode="review",
                reason="Hash-seed stability fixture",
            ),
        )
    )
    return source_bound_component_report(
        "synthetic-mosfet-terminal-order-hashseed", observed, policy
    )


def mosfet_drain_source_same_net_report(*, same_net: bool) -> dict[str, object]:
    """Serialize a same-net MOSFET terminal fault or distinct-net control."""
    observed = mosfet_drain_source_netlist(same_net=same_net)
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="component.mosfet_drain_source_same_net",
                mode="review",
                reason="Hash-seed stability fixture",
            ),
        )
    )
    return source_bound_component_report(
        "synthetic-mosfet-main-terminals-hashseed", observed, policy
    )


def bjt_terminal_order_report(*, family: str, reversed_order: bool) -> dict[str, object]:
    """Serialize an enabled BJT named-rail order fault or valid control."""
    observed = bjt_terminal_order_netlist(family=family, reversed_order=reversed_order)
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="component.bjt_terminal_order_on_named_rails",
                mode="review",
                reason="Hash-seed stability fixture",
            ),
        )
    )
    return source_bound_component_report("synthetic-bjt-terminal-order-hashseed", observed, policy)


def bjt_collector_emitter_same_net_report(*, same_net: bool) -> dict[str, object]:
    """Serialize a BJT same-net terminal fault or distinct-net control."""
    observed = bjt_collector_emitter_netlist(same_net=same_net)
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="component.bjt_collector_emitter_same_net",
                mode="review",
                reason="Hash-seed stability fixture",
            ),
        )
    )
    return source_bound_component_report("synthetic-bjt-main-terminals-hashseed", observed, policy)


def bjt_base_emitter_same_net_report(*, same_net: bool) -> dict[str, object]:
    """Serialize an enabled BJT base/emitter same-net fault or control."""
    observed = bjt_base_emitter_netlist(same_net=same_net)
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="component.bjt_base_emitter_same_net",
                mode="review",
                reason="Hash-seed stability fixture",
            ),
        )
    )
    return source_bound_component_report("synthetic-bjt-base-emitter-hashseed", observed, policy)


def bjt_base_drive_report(*, series_resistor: bool) -> dict[str, object]:
    """Serialize direct BJT output drive and its visible series-resistor control."""
    observed = bjt_base_drive_netlist(series_resistor=series_resistor)
    return source_bound_component_report("synthetic-bjt-base-drive-hashseed", observed)


def bjt_base_bias_report(*, bias_resistor: bool) -> dict[str, object]:
    """Serialize an opt-in BJT base-bias fault or direct-resistor control."""
    observed = bjt_base_bias_netlist(bias_value="100k" if bias_resistor else None)
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="component.bjt_base_without_visible_emitter_bias",
                mode="review",
                reason="Hash-seed stability fixture",
            ),
        )
    )
    return source_bound_component_report("synthetic-bjt-base-bias-hashseed", observed, policy)


def report_cases() -> dict[str, object]:
    return {
        "diode_rail_named_return_fault": diode_rail_orientation_report(
            anode_net="GND", cathode_net="+3V3"
        ),
        "diode_rail_named_return_control": diode_rail_orientation_report(
            anode_net="+3V3", cathode_net="GND"
        ),
        "mosfet_gate_no_peer_fault": mosfet_gate_peer_report(has_driver=False),
        "mosfet_gate_driver_control": mosfet_gate_peer_report(has_driver=True),
        "mosfet_terminal_order_fault": mosfet_terminal_order_report(reversed_order=True),
        "mosfet_terminal_order_control": mosfet_terminal_order_report(reversed_order=False),
        "mosfet_drain_source_same_net_fault": mosfet_drain_source_same_net_report(same_net=True),
        "mosfet_drain_source_same_net_control": mosfet_drain_source_same_net_report(same_net=False),
        "bjt_npn_terminal_order_fault": bjt_terminal_order_report(
            family="npn", reversed_order=True
        ),
        "bjt_npn_terminal_order_control": bjt_terminal_order_report(
            family="npn", reversed_order=False
        ),
        "bjt_pnp_terminal_order_fault": bjt_terminal_order_report(
            family="pnp", reversed_order=True
        ),
        "bjt_pnp_terminal_order_control": bjt_terminal_order_report(
            family="pnp", reversed_order=False
        ),
        "bjt_collector_emitter_same_net_fault": bjt_collector_emitter_same_net_report(
            same_net=True
        ),
        "bjt_collector_emitter_same_net_control": bjt_collector_emitter_same_net_report(
            same_net=False
        ),
        "bjt_base_emitter_same_net_fault": bjt_base_emitter_same_net_report(same_net=True),
        "bjt_base_emitter_same_net_control": bjt_base_emitter_same_net_report(same_net=False),
        "bjt_base_direct_drive_fault": bjt_base_drive_report(series_resistor=False),
        "bjt_base_series_resistor_control": bjt_base_drive_report(series_resistor=True),
        "bjt_base_bias_fault": bjt_base_bias_report(bias_resistor=False),
        "bjt_base_bias_resistor_control": bjt_base_bias_report(bias_resistor=True),
        "diode_fault": evaluate(
            "synthetic-two-pin-diode-hash-seed-fault", coach(diode_netlist()), DesignLintPolicy()
        ).model_dump(mode="json"),
        "diode_control": evaluate(
            "synthetic-two-pin-diode-hash-seed-control",
            coach(diode_netlist(same_net=False)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "crystal_fault": evaluate(
            "synthetic-two-pin-crystal-hash-seed-fault",
            coach(crystal_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "crystal_control": evaluate(
            "synthetic-two-pin-crystal-hash-seed-control",
            coach(crystal_netlist(same_net=False)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "fuse_fault": evaluate(
            "synthetic-two-pin-fuse-hash-seed-fault", coach(fuse_netlist()), DesignLintPolicy()
        ).model_dump(mode="json"),
        "fuse_control": evaluate(
            "synthetic-two-pin-fuse-hash-seed-control",
            coach(fuse_netlist(same_net=False)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "ferrite_fault": evaluate(
            "synthetic-two-pin-ferrite-hash-seed-fault",
            coach(ferrite_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "ferrite_control": evaluate(
            "synthetic-two-pin-ferrite-hash-seed-control",
            coach(ferrite_netlist(same_net=False)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "switch_fault": evaluate(
            "synthetic-two-pin-switch-hash-seed-fault", coach(switch_netlist()), DesignLintPolicy()
        ).model_dump(mode="json"),
        "switch_control": evaluate(
            "synthetic-two-pin-switch-hash-seed-control",
            coach(switch_netlist(same_net=False)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "mosfet_stress_q2_over_limit": mosfet_stress_check_result(q2_over_limit=True),
        "mosfet_stress_multi_device_control": mosfet_stress_check_result(q2_over_limit=False),
        "led_output_direct_fault": led_output_lint_report(topology="direct"),
        "led_output_parallel_resistor_fault": led_output_lint_report(topology="parallel-resistor"),
        "led_output_series_control": led_output_lint_report(topology="series-return-side"),
    }
