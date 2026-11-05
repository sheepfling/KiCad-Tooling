"""Source-binding regressions for typed named connector all-open findings."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_footprint_named_power_input_all_open import (
    evaluate_footprint_named_power_input_all_open,
)
from kicad_tooling.hwrepo.connector_footprint_named_power_output_all_open import (
    evaluate_footprint_named_power_output_all_open,
)
from kicad_tooling.hwrepo.connector_footprint_named_signal_all_open import (
    evaluate_footprint_named_signal_all_open,
)
from kicad_tooling.hwrepo.connector_footprint_peer_pins import (
    scan_connector_footprint_peer_pin_assignments,
)
from kicad_tooling.hwrepo.design_lint_connector_footprint_all_open_candidate_evidence import (
    ConnectorFootprintAllOpenCandidate,
    ConnectorFootprintAllOpenEvidence,
    project_connector_footprint_all_open_evidence,
)
from tests.connector_footprint_peer_support import (
    named_power_input_all_open_netlist,
    named_power_output_all_open_netlist,
    named_signal_all_open_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.evidence_lint]


def test_named_all_open_candidates_retain_their_source_scan_and_projection() -> None:
    cases = (
        (
            named_power_input_all_open_netlist(),
            evaluate_footprint_named_power_input_all_open,
            "power_input",
        ),
        (
            named_power_output_all_open_netlist(),
            evaluate_footprint_named_power_output_all_open,
            "power_output",
        ),
        (named_signal_all_open_netlist(), evaluate_footprint_named_signal_all_open, "signal"),
    )
    candidates: list[ConnectorFootprintAllOpenCandidate] = []
    for observed, evaluate_all_open, kind in cases:
        scan = scan_connector_footprint_peer_pin_assignments(observed)
        (candidate,) = evaluate_all_open(scan).candidates
        assert isinstance(candidate, ConnectorFootprintAllOpenCandidate)
        source = candidate.source_evidence
        assert source.scan is scan
        assert source.kind == kind
        assert source.item in scan.named_all_open
        assert candidate.evidence == project_connector_footprint_all_open_evidence(source).evidence
        candidates.append(candidate)

    assert tuple(candidate.rule_id for candidate in candidates) == (
        "connector.footprint_named_power_input_all_open",
        "connector.footprint_named_power_output_all_open",
        "connector.footprint_named_signal_all_open",
    )


def test_named_all_open_source_rejects_a_record_outside_its_scan() -> None:
    scan = scan_connector_footprint_peer_pin_assignments(named_signal_all_open_netlist())
    (candidate,) = evaluate_footprint_named_signal_all_open(scan).candidates
    assert isinstance(candidate, ConnectorFootprintAllOpenCandidate)
    source = candidate.source_evidence
    changed_scan = replace(scan, named_all_open=())

    with pytest.raises(ValueError, match="belong to its current peer scan"):
        replace(source, scan=changed_scan)


def test_named_all_open_evidence_cannot_cross_contact_kinds() -> None:
    scan = scan_connector_footprint_peer_pin_assignments(named_power_input_all_open_netlist())
    item = scan.named_all_open[0]

    with pytest.raises(ValueError, match="power_out"):
        ConnectorFootprintAllOpenEvidence(scan=scan, item=item, kind="power_output")
