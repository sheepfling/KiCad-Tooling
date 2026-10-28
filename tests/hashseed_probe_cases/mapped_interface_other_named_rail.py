"""Source-matched mapped-other rail label reports for hash-seed tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from tests.design_lint_fixtures.connector_mapped_other_named_rail import (
    mapped_other_named_rail_netlist,
    mapped_other_named_rail_report,
)
from tests.json_types import JsonObject


def _report(net_name: str) -> JsonObject:
    observed = mapped_other_named_rail_netlist(target_net=net_name)
    report, coverage = mapped_other_named_rail_report(observed)
    return {
        "netlist_sha256": sha256(model_json_bytes(observed)).hexdigest(),
        "interface_catalog_sha256": str(coverage.interface_catalog_sha256),
        "coverage_sha256": sha256(model_json_bytes(coverage)).hexdigest(),
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> JsonObject:
    """Return a named-return fault and unrelated-net control."""
    return {
        "mapped_other_named_rail_fault": _report("GND"),
        "mapped_other_named_rail_control": _report("AUX_DATA"),
    }
