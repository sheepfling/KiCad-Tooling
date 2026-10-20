"""Source-bound connector peers with missing pin metadata for hash-seed tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.connector_footprint_peer_support import peer_missing_metadata_netlist
from tests.design_lint_fixtures import coach


def _report(*, split: bool) -> dict[str, object]:
    assignments = ("UART_RX_NET", "UART_TX_NET") if split else ("SHARED_PORT", "SHARED_PORT")
    observed = peer_missing_metadata_netlist(target_assignments=assignments)
    netlist_sha256 = sha256(model_json_bytes(observed)).hexdigest()
    report = evaluate(
        "synthetic-connector-peer-missing-metadata",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, object]:
    """Return a split-assignment fault and a common-assignment control."""
    return {
        "connector_peer_missing_metadata_fault": _report(split=True),
        "connector_peer_missing_metadata_control": _report(split=False),
    }
