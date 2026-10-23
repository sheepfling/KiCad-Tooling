"""Components report cases for deterministic synthetic verification."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    NetlistContract,
)
from kicad_tooling.hwrepo.mosfet_stress import mosfet_stress_checks
from kicad_tooling.hwrepo.mosfet_stress_models import MosfetVoltageInterval
from tests.design_lint_fixtures import (
    coach,
)
from tests.design_lint_fixtures.diode_rail_orientation import netlist as diode_rail_netlist
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
) -> dict[str, object]:
    """Serialize component lint against a hash of its normalized netlist."""
    digest = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    return evaluate(
        project_id,
        coach(observed, netlist_sha256=digest),
        DesignLintPolicy(),
    ).model_dump(mode="json")


def diode_rail_orientation_report(*, anode_net: str, cathode_net: str) -> dict[str, object]:
    """Serialize a diode rail review with a digest of its normalized netlist."""
    observed = diode_rail_netlist(anode_net=anode_net, cathode_net=cathode_net)
    return source_bound_component_report("synthetic-diode-rail-return", observed)


def mosfet_gate_peer_report(*, has_driver: bool) -> dict[str, object]:
    """Serialize a supported MOSFET gate with and without a fitted net peer."""
    observed = mosfet_gate_netlist(gate_net_members=("U1.1",) if has_driver else None)
    return source_bound_component_report("synthetic-mosfet-gate-hashseed", observed)


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
