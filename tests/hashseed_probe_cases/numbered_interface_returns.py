"""Numbered-return reports for mixed USB and serial connector peers."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.connector_mixed_return import two_usb_one_serial_return_case
from tests.json_types import JsonObject


def _report(*, common_return: bool) -> JsonObject:
    observed, coverage = two_usb_one_serial_return_case(
        common_return=common_return,
        split_return_net_names=("USB1_GND", "USB2_GND"),
    )
    netlist_sha256 = hashlib.sha256(model_json_bytes(observed)).hexdigest()
    project_id = (
        "synthetic-numbered-interface-return-control"
        if common_return
        else "synthetic-numbered-interface-return-fault"
    )
    report = evaluate(
        project_id,
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return report.model_dump(mode="json")


def report_cases() -> JsonObject:
    """Build one split-domain fault and one common-return control report."""
    return {
        "mixed_interface_numbered_return_fault": _report(common_return=False),
        "mixed_interface_numbered_return_control": _report(common_return=True),
    }
