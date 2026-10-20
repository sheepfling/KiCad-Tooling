"""Source-bound connector peers with missing pin metadata for hash-seed tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.connector_footprint_peer_support import peer_missing_metadata_netlist
from tests.design_lint_fixtures import coach


def _report(*, split: bool, part_id: bool = False) -> dict[str, object]:
    assignments = ("UART_RX_NET", "UART_TX_NET") if split else ("SHARED_PORT", "SHARED_PORT")
    part_id_value = "SYNTHETIC-PART-001" if part_id else None
    observed = peer_missing_metadata_netlist(
        target_assignments=assignments,
        part_id=part_id_value,
    )
    if part_id_value is not None:
        components = dict(observed.components)
        components["J2"] = components["J2"].model_copy(update={"part_id": part_id_value.casefold()})
        observed = observed.model_copy(update={"components": components})
    netlist_sha256 = sha256(model_json_bytes(observed)).hexdigest()
    report = evaluate(
        "synthetic-connector-peer-missing-metadata",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, object]:
    """Return missing-metadata split and common controls with and without PART_ID."""
    return {
        "connector_peer_missing_metadata_fault": _report(split=True),
        "connector_peer_missing_metadata_control": _report(split=False),
        "connector_peer_missing_metadata_part_id_fault": _report(split=True, part_id=True),
        "connector_peer_missing_metadata_part_id_control": _report(split=False, part_id=True),
    }
