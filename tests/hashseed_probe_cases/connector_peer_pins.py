"""Source-bound connector peer-pin reports for hash-seed tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.connector_peer_pin_all_open import (
    generic_open_peer_netlist,
    review_generic_peer_pin_policy,
)


def generic_peer_all_open_report(*, open_pin_assignments: bool) -> dict[str, object]:
    """Serialize an all-open generic contact or its connected control."""
    observed = generic_open_peer_netlist(open_pin_assignments=open_pin_assignments)
    netlist_sha256 = sha256(model_json_bytes(observed)).hexdigest()
    report = evaluate(
        "synthetic-connector-peer-pin-all-open",
        coach(observed, netlist_sha256),
        review_generic_peer_pin_policy(),
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, object]:
    """Return the opt-in all-open fault and assigned-pin control."""
    return {
        "connector_generic_peer_pin_all_open_fault": generic_peer_all_open_report(
            open_pin_assignments=True,
        ),
        "connector_generic_peer_pin_all_open_control": generic_peer_all_open_report(
            open_pin_assignments=False,
        ),
    }
