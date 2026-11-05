"""Source-bound regressions for unreviewed connector peer-scope evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_comparison_scope_types import ConnectorComparisonScope
from kicad_tooling.hwrepo.connector_footprint_peer_assignments import (
    connector_footprint_peer_pin_assignments,
    connector_footprint_peer_pin_net_map,
)
from kicad_tooling.hwrepo.connector_footprint_peer_pins import (
    scan_connector_footprint_peer_pin_assignments,
)
from kicad_tooling.hwrepo.connector_footprint_peer_unanchored_scope_review import (
    unreviewed_unanchored_connector_alias_scope,
)
from kicad_tooling.hwrepo.design_lint_connector_unanchored_scope_evidence import (
    ConnectorUnanchoredPeerScopeCandidate,
    project_connector_unanchored_peer_scope_evidence,
)
from tests.connector_footprint_peer_support import peer_netlist
from tests.connector_peer_unanchored_scope_support import reviewed_coverage

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def _candidate() -> ConnectorUnanchoredPeerScopeCandidate:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    scan = scan_connector_footprint_peer_pin_assignments(observed)
    coverage = reviewed_coverage(observed, (None, None))
    candidate = unreviewed_unanchored_connector_alias_scope(scan, observed, coverage)[0]
    assert isinstance(candidate, ConnectorUnanchoredPeerScopeCandidate)
    return candidate


def test_unreviewed_scope_candidate_keeps_current_scan_and_projection() -> None:
    candidate = _candidate()

    assert tuple(item.pin_number for item in candidate.source_evidence.divergences) == ("1", "2")
    assert (
        candidate.evidence
        == project_connector_unanchored_peer_scope_evidence(candidate.source_evidence).evidence
    )


def test_peer_pin_assignment_owner_normalizes_case_and_keeps_ambiguous_nets() -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    observed = observed.model_copy(update={"nets": {"Z_NET": ("J1.1",), "A_NET": ("j1.1",)}})
    pin_nets = connector_footprint_peer_pin_net_map(observed)

    assert connector_footprint_peer_pin_assignments(pin_nets, "J1.1") == (
        "A_NET",
        "Z_NET",
    )
    assert connector_footprint_peer_pin_assignments(pin_nets, "j1.1") == (
        "A_NET",
        "Z_NET",
    )


def test_unreviewed_scope_rejects_a_changed_netlist_and_its_stale_coverage() -> None:
    source = _candidate().source_evidence
    observed = source.observed.model_copy(
        update={
            "nets": {
                name: pins for name, pins in source.observed.nets.items() if "J2.1" not in pins
            }
        }
    )
    stale_scan = replace(source.scan, source=replace(source.scan.source, observed=observed))

    with pytest.raises(ValueError, match="maps|assignments"):
        replace(source, scan=stale_scan, observed=observed)


def test_unreviewed_scope_rejects_candidates_from_another_scan() -> None:
    candidate = _candidate()
    changed_observed = candidate.source_evidence.observed.model_copy(update={"nets": {}})
    changed_scan = scan_connector_footprint_peer_pin_assignments(changed_observed)

    with pytest.raises(ValueError, match="current native scan"):
        replace(candidate.source_evidence, scan=changed_scan, observed=changed_observed)


def test_unreviewed_scope_rejects_new_authored_peer_assignment_scope() -> None:
    source = _candidate().source_evidence
    changed_scan_source = replace(
        source.scan.source,
        peer_assignment_groups={"J1": ConnectorComparisonScope("reviewed-peers", "Reviewed group")},
    )

    with pytest.raises(ValueError, match="absence of peer groups"):
        replace(source, scan=replace(source.scan, source=changed_scan_source))
