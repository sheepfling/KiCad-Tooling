"""Components report cases for deterministic synthetic verification."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    MosfetVoltageInterval,
)
from kicad_tooling.hwrepo.mosfet_stress import mosfet_stress_checks
from tests.design_lint_fixtures import (
    coach,
)
from tests.test_led_output_heuristics import observed_report as led_output_observed_report
from tests.test_led_output_heuristics import output_led_netlist as led_output_netlist
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


def report_cases() -> dict[str, object]:
    return {
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
