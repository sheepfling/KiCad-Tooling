"""Source-bound regressions for connector alias metadata findings."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_metadata import (
    connector_footprint_peer_pin_metadata_assignment_divergences,
)
from kicad_tooling.hwrepo.connector_footprint_peer_metadata_open import (
    connector_footprint_peer_pin_metadata_open_outliers,
)
from kicad_tooling.hwrepo.connector_footprint_peer_missing_metadata import (
    connector_footprint_peer_pin_missing_metadata_assignment_divergences,
)
from kicad_tooling.hwrepo.connector_footprint_peer_missing_metadata_open import (
    connector_footprint_peer_pin_missing_metadata_open_outliers,
)
from kicad_tooling.hwrepo.design_lint_connector_footprint_peer_metadata_evidence import (
    ConnectorFootprintPeerMetadataCandidate,
    project_connector_footprint_peer_metadata_evidence,
)
from tests.connector_footprint_peer_support import (
    peer_metadata_divergence_netlist,
    peer_missing_metadata_netlist,
)
from tests.design_lint_fixtures.connector_peer_missing_metadata_open import (
    missing_metadata_open_peer_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def _metadata_candidates() -> tuple[ConnectorFootprintPeerMetadataCandidate, ...]:
    known_split = connector_footprint_peer_pin_metadata_assignment_divergences(
        peer_metadata_divergence_netlist()
    )
    known_open = connector_footprint_peer_pin_metadata_open_outliers(
        peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None))
    )
    missing_split = connector_footprint_peer_pin_missing_metadata_assignment_divergences(
        peer_missing_metadata_netlist()
    )
    missing_open = connector_footprint_peer_pin_missing_metadata_open_outliers(
        missing_metadata_open_peer_netlist()
    )
    known_split_candidate = known_split[0]
    known_open_candidate = known_open[0]
    missing_split_candidate = missing_split[0]
    missing_open_candidate = missing_open[0]
    assert isinstance(known_split_candidate, ConnectorFootprintPeerMetadataCandidate)
    assert isinstance(known_open_candidate, ConnectorFootprintPeerMetadataCandidate)
    assert isinstance(missing_split_candidate, ConnectorFootprintPeerMetadataCandidate)
    assert isinstance(missing_open_candidate, ConnectorFootprintPeerMetadataCandidate)
    return (
        known_split_candidate,
        known_open_candidate,
        missing_split_candidate,
        missing_open_candidate,
    )


def test_all_four_metadata_states_keep_typed_current_sources_and_wire_projections() -> None:
    candidates = _metadata_candidates()

    assert tuple(item.source_evidence.kind for item in candidates) == (
        "known_split",
        "known_open",
        "missing_split",
        "missing_open",
    )
    for candidate in candidates:
        assert (
            candidate.evidence
            == project_connector_footprint_peer_metadata_evidence(
                candidate.source_evidence
            ).evidence
        )


def test_every_metadata_state_rejects_a_changed_native_assignment_source() -> None:
    for candidate in _metadata_candidates():
        source = candidate.source_evidence
        changed_netlist = source.source.observed.model_copy(update={"nets": {}})
        changed_source = replace(source.source, observed=changed_netlist)

        with pytest.raises(ValueError, match="scope|assignment|anchor"):
            replace(source, source=changed_source)


def test_known_metadata_projection_preserves_native_text_spacing() -> None:
    source = peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None))
    observed = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "J1.2": " UART_RX "}}
    )
    candidate = connector_footprint_peer_pin_metadata_open_outliers(observed)[0]

    assert candidate.evidence["peer_pin_metadata"][0] == (
        "J1.2: function= UART_RX ; electrical_type=input"
    )
