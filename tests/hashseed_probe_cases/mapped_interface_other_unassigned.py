"""Source-matched mapped-other connector reports for hash-seed tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from tests.design_lint_fixtures.connector_mapped_interface_other import (
    mapped_interface_other_report,
)
from tests.design_lint_fixtures.connector_mapped_interface_signal import (
    mapped_interface_netlist,
)
from tests.json_types import JsonObject


def _report(*, connected: bool) -> JsonObject:
    observed = mapped_interface_netlist(
        target_net="AUXILIARY" if connected else None,
        target_function="2",
        target_type="input",
    )
    report, coverage = mapped_interface_other_report(observed)
    return {
        "netlist_sha256": sha256(model_json_bytes(observed)).hexdigest(),
        "interface_catalog_sha256": str(coverage.interface_catalog_sha256),
        "coverage_sha256": sha256(model_json_bytes(coverage)).hexdigest(),
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> JsonObject:
    """Return an open-contact fault and an assigned-contact control."""
    return {
        "mapped_interface_other_fault": _report(connected=False),
        "mapped_interface_other_control": _report(connected=True),
    }
