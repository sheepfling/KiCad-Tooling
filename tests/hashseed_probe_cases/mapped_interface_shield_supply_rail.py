"""Source-mapped shields assigned to supply rails for hash-seed tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from tests.design_lint_fixtures.connector_mapped_named_rail import (
    mapped_named_rail_netlist,
    mapped_named_rail_report,
)


def _report(net_name: str) -> dict[str, object]:
    observed = mapped_named_rail_netlist(target_net=net_name)
    report, coverage = mapped_named_rail_report(observed, role="shield")
    return {
        "netlist_sha256": sha256(model_json_bytes(observed)).hexdigest(),
        "interface_catalog_sha256": str(coverage.interface_catalog_sha256),
        "coverage_sha256": sha256(model_json_bytes(coverage)).hexdigest(),
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> dict[str, object]:
    """Return a named-supply fault and unrelated-net control."""
    return {
        "mapped_shield_supply_rail_fault": _report("+5V"),
        "mapped_shield_supply_rail_control": _report("CHASSIS_SHIELD"),
    }
