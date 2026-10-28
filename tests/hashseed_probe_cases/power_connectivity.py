"""Authored power-connectivity check results for deterministic probes."""

from __future__ import annotations

import hashlib
from typing import Literal

from kicad_tooling.hwrepo.power_connectivity import power_connectivity_checks
from tests.electrical_power_connectivity_support import (
    power_connectivity_netlist,
    power_connectivity_requirement,
)
from tests.json_types import JsonObject

PowerConnectivityFault = Literal["source-wrong-net", "load-wrong-net"]


def _check_report(fault: PowerConnectivityFault | None) -> JsonObject:
    requirement = power_connectivity_requirement()
    netlist = power_connectivity_netlist(fault=fault)
    checks = power_connectivity_checks(requirement, netlist)
    return {
        "requirements_sha256": hashlib.sha256(
            requirement.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "netlist_sha256": hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest(),
        "checks": [check.model_dump(mode="json") for check in checks],
    }


def report_cases() -> dict[str, JsonObject]:
    """Serialize source, load, and valid-control check sets from the shared service."""
    return {
        "power_connectivity_source_fault": _check_report("source-wrong-net"),
        "power_connectivity_load_fault": _check_report("load-wrong-net"),
        "power_connectivity_control": _check_report(None),
    }
