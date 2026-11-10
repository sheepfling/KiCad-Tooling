"""Baseline for named mapped signal peers assigned to separate nets."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_connector_named_peer_signal_split_candidate_evidence import (
    MappedNamedPeerSignalSplitCandidate,
    project_mapped_named_peer_signal_split_evidence,
)
from kicad_tooling.hwrepo.design_lint_connectors_named_peer_signal_splits import (
    mapped_named_peer_signal_split_net_candidates,
)
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from tests.design_lint_fixtures.connector_reviewed_peer_signal_split import (
    peer_signal_coverage,
    peer_signal_netlist,
    peer_signal_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_named_peer_signal_split_nets"


def _findings(report: DesignLintReport):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_mapped_peer_signal_split_has_no_existing_specific_prompt() -> None:
    observed = peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B"))
    coverage = peer_signal_coverage(observed)
    report = peer_signal_report(observed, coverage=coverage)

    assert coverage.status == "COMPLETE"
    existing_specific = tuple(
        item.rule_id
        for item in report.findings
        if item.rule_id
        in {
            "connector.mapped_signals_split_nets",
            "connector.reviewed_peer_signal_assignment_split",
            "connector.peer_pin_assignment_divergence",
            "connector.peer_pin_assignment_outlier",
            "connector.footprint_peer_pin_assignment_divergence",
        }
    )
    assert not existing_specific
    (finding,) = _findings(report)
    assert report.status == "REVIEW"
    assert finding.subject == (
        "serial-peers: mapped peer signal UART_RX (logic-3v3) uses separate native nets"
    )
    assert finding.evidence["connector_references"] == ("J1", "J2")
    assert finding.evidence["component_pin"] == ("J1.2", "J2.7")
    assert finding.evidence["interface_signal"] == ("UART_RX",)
    assert finding.evidence["voltage_domain"] == ("logic-3v3",)
    assert finding.evidence["peer_assignment_group"] == ("serial-peers",)
    assert "do not require direct commoning" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_unscoped_generic_and_role_controls_stay_quiet() -> None:
    common = peer_signal_netlist(
        nets=("COMMON_RX", "COMMON_RX"),
        functions=("CONTACT_A", "CONTACT_B"),
    )
    distinct_signal = peer_signal_coverage(
        peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
        signals=("USB_RX", "SERIAL_RX"),
    )
    distinct_domain = peer_signal_coverage(
        peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
        voltage_domains=("logic-3v3", "logic-5v"),
    )
    distinct_group = peer_signal_coverage(
        peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
        peer_groups=("usb-port", "serial-port"),
    )
    case_distinct_signal = peer_signal_coverage(
        peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
        signals=("UART_RX", "uart_rx"),
    )
    case_distinct_domain = peer_signal_coverage(
        peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
        voltage_domains=("logic-3v3", "Logic-3V3"),
    )
    case_distinct_group = peer_signal_coverage(
        peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
        peer_groups=("serial-peers", "Serial-Peers"),
    )
    unscoped_peer = peer_signal_coverage(
        peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
        peer_groups=("serial-peers", None),
    )
    generic = peer_signal_netlist(functions=("Pin_2", "Pin_7"))
    known_roles = peer_signal_netlist(functions=("VBUS", "GND"))
    non_signal_role = peer_signal_coverage(
        peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
        roles=("return", "return"),
    )
    same_symbol = peer_signal_netlist(
        functions=("CONTACT_A", "CONTACT_B"),
        symbols=("Synthetic:SamePort", "Synthetic:SamePort"),
    )

    reports = (
        peer_signal_report(common),
        peer_signal_report(
            peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
            coverage=distinct_signal,
        ),
        peer_signal_report(
            peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
            coverage=distinct_domain,
        ),
        peer_signal_report(
            peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
            coverage=distinct_group,
        ),
        peer_signal_report(
            peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
            coverage=case_distinct_signal,
        ),
        peer_signal_report(
            peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
            coverage=case_distinct_domain,
        ),
        peer_signal_report(
            peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
            coverage=case_distinct_group,
        ),
        peer_signal_report(
            peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
            coverage=unscoped_peer,
        ),
        peer_signal_report(generic),
        peer_signal_report(known_roles),
        peer_signal_report(
            peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B")),
            coverage=non_signal_role,
        ),
        peer_signal_report(same_symbol),
    )
    assert all(not _findings(report) for report in reports)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_stale_incomplete_and_digestless_controls() -> None:
    dnp = peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B"), dnp=("J2",))
    opened = peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B"), open_pins=("J2.7",))
    open_coverage = peer_signal_coverage(
        opened,
        unconnected_reasons=(None, "Synthetic intentionally open signal"),
    )
    ambiguous = peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B"))
    ambiguous = ambiguous.model_copy(
        update={"nets": {**ambiguous.nets, "ALTERNATE_NET": ("J2.7",)}}
    )
    observed = peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B"))
    current = peer_signal_coverage(observed)
    stale = peer_signal_netlist(functions=("UPDATED_CONTACT_A", "CONTACT_B"))

    for source, coverage in (
        (dnp, None),
        (opened, open_coverage),
        (ambiguous, None),
        (stale, current),
        (observed, current.model_copy(update={"status": "INCOMPLETE"})),
        (observed, current.model_copy(update={"interface_catalog_sha256": None})),
    ):
        assert not _findings(peer_signal_report(source, coverage=coverage))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_review() -> None:
    observed = peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B"))
    baseline = _findings(peer_signal_report(observed))[0]
    blocked = peer_signal_report(
        observed,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic reviewed peers require this signal review.",
                ),
            )
        ),
    )
    disabled = peer_signal_report(
        observed,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project reviewed this intentional signal split.",
                ),
            )
        ),
    )
    ignored = peer_signal_report(
        observed,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic signal branches are intentionally separate.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert _findings(disabled)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_projection_rejects_stale_map_and_stays_deterministic() -> None:
    observed = peer_signal_netlist(functions=("CONTACT_A", "CONTACT_B"))
    coverage = peer_signal_coverage(observed)
    (candidate,) = mapped_named_peer_signal_split_net_candidates(observed, coverage)
    assert isinstance(candidate, MappedNamedPeerSignalSplitCandidate)
    reordered = observed.model_copy(
        update={
            "nets": {
                name: tuple(reversed(pins)) for name, pins in reversed(tuple(observed.nets.items()))
            }
        }
    )
    reordered_candidates = mapped_named_peer_signal_split_net_candidates(
        reordered,
        peer_signal_coverage(reordered),
    )
    reordered_map = coverage.model_copy(update={"entries": tuple(reversed(coverage.entries))})
    (reordered_map_candidate,) = mapped_named_peer_signal_split_net_candidates(
        observed,
        reordered_map,
    )
    renamed = peer_signal_netlist(
        nets=("NEUTRAL_A", "NEUTRAL_B"),
        functions=("CONTACT_A", "CONTACT_B"),
    )
    (renamed_candidate,) = mapped_named_peer_signal_split_net_candidates(
        renamed,
        peer_signal_coverage(renamed),
    )

    public_candidate = (candidate.rule_id, candidate.subject, candidate.message, candidate.evidence)
    assert public_candidate == (
        reordered_candidates[0].rule_id,
        reordered_candidates[0].subject,
        reordered_candidates[0].message,
        reordered_candidates[0].evidence,
    )
    assert public_candidate == (
        reordered_map_candidate.rule_id,
        reordered_map_candidate.subject,
        reordered_map_candidate.message,
        reordered_map_candidate.evidence,
    )
    assert (
        project_mapped_named_peer_signal_split_evidence(candidate.source_evidence).evidence
        == candidate.evidence
    )
    assert candidate.evidence["component_pin"] == renamed_candidate.evidence["component_pin"]
    assert (
        candidate.evidence["split_native_nets"] != renamed_candidate.evidence["split_native_nets"]
    )

    stale = observed.model_copy(
        update={"pin_functions": {**observed.pin_functions, "J1.2": "UPDATED_CONTACT"}}
    )
    with pytest.raises(ValueError, match="complete current peer set"):
        replace(candidate.source_evidence, observed=stale)
