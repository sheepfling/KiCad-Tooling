"""Exact-part connector pin-inventory reports for hash-seed probes."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.connector_footprint_peer_pin_inventory_support import (
    connector_peer_pin_inventory_netlist,
)
from tests.design_lint_fixtures import coach
from tests.json_types import JsonObject


def _report(*, fault: bool) -> JsonObject:
    observed: NetlistContract = connector_peer_pin_inventory_netlist(
        extra_numbers=("3",) if fault else (),
    )
    netlist_sha256 = sha256(model_json_bytes(observed)).hexdigest()
    report = evaluate(
        "synthetic-connector-peer-pin-inventory-fault"
        if fault
        else "synthetic-connector-peer-pin-inventory-control",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def report_cases() -> JsonObject:
    """Return complete-inventory fault and matching-inventory control reports."""
    return {
        "connector_peer_pin_inventory_fault": _report(fault=True),
        "connector_peer_pin_inventory_control": _report(fault=False),
    }
