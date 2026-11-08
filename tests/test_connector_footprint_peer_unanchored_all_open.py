"""Source-matched peer scope for unanchored footprint-alias all-open review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.connector_footprint_peer_support import (
    FOOTPRINT_ALL_OPEN_RULE_ID,
    NETLIST_SHA256,
    peer_netlist,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.connector_peer_pin_all_open import (
    generic_open_peer_coverage,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]

_RULE_ID = FOOTPRINT_ALL_OPEN_RULE_ID


def _review_policy() -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=_RULE_ID,
                mode="review",
                reason="Synthetic project opts into all-open footprint-alias review.",
            ),
        )
    )


def _report(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(
        "synthetic-footprint-peer-unanchored-all-open",
        coach(observed).model_copy(update={"netlist_sha256": NETLIST_SHA256}),
        policy or _review_policy(),
        connector_coverage=coverage,
    )


@pytest.mark.design_lint_rule(rule_id=_RULE_ID)
def test_source_matched_peer_group_scopes_unanchored_all_open_review() -> None:
    source = peer_netlist(assignments=(("PORT_A", "PORT_B"), (None, None)))
    coverage = generic_open_peer_coverage(source, groups=("serial-peers", "serial-peers"))
    assert coverage.status == "COMPLETE"

    default = _report(source, coverage, DesignLintPolicy())
    default_finding = next(item for item in default.findings if item.rule_id == _RULE_ID)
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"

    report = _report(source, coverage)
    (finding,) = tuple(item for item in report.findings if item.rule_id == _RULE_ID)
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"
    assert finding.evidence["common_anchor_pin_numbers"] == ()
    assert finding.evidence["peer_assignment_group"] == ("serial-peers",)
    assert "No common-net anchor exists" in finding.message
    assert "do not establish that the contact must connect" in finding.message

    footprint = report.connector_peer_pin_coverage.footprint_alias_coverage
    assert footprint.all_open_peer_pin_group_count == 1
    assert footprint.unanchored_all_open_peer_pin_group_count == 1
    assert footprint.unanchored_all_open_finding_count == 1
    assert footprint.all_open_finding_count == 1


@pytest.mark.design_lint_rule(rule_id=_RULE_ID)
def test_unanchored_all_open_requires_current_shared_peer_group() -> None:
    source = peer_netlist(assignments=(("PORT_A", "PORT_B"), (None, None)))
    shared = generic_open_peer_coverage(source, groups=("serial-peers", "serial-peers"))
    separate = generic_open_peer_coverage(source, groups=("serial-a", "serial-b"))

    assert _RULE_ID not in {item.rule_id for item in _report(source, None).findings}
    assert _RULE_ID not in {item.rule_id for item in _report(source, separate).findings}

    stale_source = source.model_copy(
        update={
            "nets": {
                "PORT_A_RENAMED": ("J1.1",),
                "PORT_B": ("J2.1",),
            }
        }
    )
    assert _RULE_ID not in {item.rule_id for item in _report(stale_source, shared).findings}


@pytest.mark.design_lint_rule(rule_id=_RULE_ID)
def test_unanchored_all_open_review_is_stable_under_map_ordering() -> None:
    source = peer_netlist(assignments=(("PORT_A", "PORT_B"), (None, None)))
    coverage = generic_open_peer_coverage(source, groups=("serial-peers", "serial-peers"))
    reordered = coverage.model_copy(update={"entries": tuple(reversed(coverage.entries))})

    first = next(item for item in _report(source, coverage).findings if item.rule_id == _RULE_ID)
    second = next(item for item in _report(source, reordered).findings if item.rule_id == _RULE_ID)
    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
