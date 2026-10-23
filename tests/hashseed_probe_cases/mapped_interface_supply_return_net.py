"""Mapped-supply/return-label reports for hash-seed determinism tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from tests.design_lint_fixtures.connector_mapped_supply_return_net import (
    mapped_supply_return_net_netlist,
    mapped_supply_return_net_report,
)


def _report(net_name: str) -> dict[str, object]:
    observed = mapped_supply_return_net_netlist(target_net=net_name)
    report, coverage = mapped_supply_return_net_report(observed)
    return {
        "netlist_sha256": sha256(model_json_bytes(observed)).hexdigest(),
        "interface_catalog_sha256": str(coverage.interface_catalog_sha256),
        "coverage_sha256": sha256(model_json_bytes(coverage)).hexdigest(),
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> dict[str, object]:
    """Return a return-label fault and ordinary-net control."""
    return {
        "mapped_supply_return_net_fault": _report("GND"),
        "mapped_supply_return_net_control": _report("AUX_DATA"),
    }
