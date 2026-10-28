"""Source-matched connector scope reports for hash-seed tests."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.connector_mixed_return import two_usb_one_serial_return_case
from tests.json_types import JsonObject


def _scope_report(*, isolated_serial_scope: bool) -> JsonObject:
    if isolated_serial_scope:
        groups = {
            "J1": "usb-returns",
            "J2": "serial-return",
            "J3": "usb-returns",
        }
        project_id = "synthetic-mixed-connector-return-scope-fault"
    else:
        groups = {reference: "external-returns" for reference in ("J1", "J2", "J3")}
        project_id = "synthetic-mixed-connector-return-scope-control"

    observed, coverage = two_usb_one_serial_return_case(
        common_return=True,
        return_comparison_groups=groups,
    )
    netlist_sha256 = hashlib.sha256(model_json_bytes(observed)).hexdigest()
    coverage_sha256 = hashlib.sha256(model_json_bytes(coverage)).hexdigest()
    report = evaluate(
        project_id,
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return {
        "netlist_sha256": netlist_sha256,
        "coverage_sha256": coverage_sha256,
        "interface_catalog_sha256": str(coverage.interface_catalog_sha256),
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> JsonObject:
    """Return an isolated return-scope fault and a shared-scope control."""
    return {
        "connector_return_scope_singleton_fault": _scope_report(isolated_serial_scope=True),
        "connector_return_scope_singleton_control": _scope_report(isolated_serial_scope=False),
    }
