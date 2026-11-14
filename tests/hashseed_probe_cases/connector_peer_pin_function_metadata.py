"""Generic-versus-named connector pin-function reports for hash-seed probes."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.connector_footprint_peer_pin_function_metadata_support import metadata_peer_netlist
from tests.design_lint_fixtures import coach
from tests.json_types import JsonObject


def _report(*, fault: bool) -> JsonObject:
    observed = metadata_peer_netlist(generic_peer="J1" if fault else "none")
    netlist_sha256 = sha256(model_json_bytes(observed)).hexdigest()
    report = evaluate(
        "synthetic-connector-peer-pin-function-metadata-fault"
        if fault
        else "synthetic-connector-peer-pin-function-metadata-control",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def report_cases() -> JsonObject:
    """Return generic-function fault and matching-function control reports."""
    return {
        "connector_peer_pin_function_metadata_fault": _report(fault=True),
        "connector_peer_pin_function_metadata_control": _report(fault=False),
    }
