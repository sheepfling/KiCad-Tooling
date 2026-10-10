"""Focused synthetic regressions for numbered and unroled return labels."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach, four_db9_return_domains

pytestmark = [pytest.mark.design_lint, pytest.mark.return_path_lint]

UNINDEXED_RETURN_RULE = "net.return_labels_without_pin_roles"
NUMBERED_RETURN_RULE = "net.numbered_returns"
REPEATED_PIN_RULE = "connector.repeated_pin_function"


def _source_bound_report(
    netlist: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    netlist_sha256 = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
    return evaluate(
        "synthetic-four-db9",
        coach(netlist, netlist_sha256),
        DesignLintPolicy() if policy is None else policy,
    )


def _finding(report: DesignLintReport, rule_id: str):
    return next(item for item in report.findings if item.rule_id == rule_id)


def test_four_db9_separately_named_return_domains_are_reviewed() -> None:
    report = evaluate("synthetic-four-db9", coach(four_db9_return_domains()), DesignLintPolicy())
    repeated_pin_findings = [item for item in report.findings if item.rule_id == REPEATED_PIN_RULE]
    return_finding = _finding(report, NUMBERED_RETURN_RULE)

    assert report.status == "REVIEW"
    assert len(repeated_pin_findings) == 2
    assert {pin for item in repeated_pin_findings for pin in item.evidence} == {
        f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)
    }
    assert return_finding.evidence == {
        f"RETURN_PORT_{reference}": (f"J{reference}.7", f"J{reference}.9")
        for reference in range(1, 5)
    }
    assert "intentionally isolated" in return_finding.message


def test_four_db9_common_return_control_clears_review_findings() -> None:
    report = evaluate(
        "synthetic-four-db9-common",
        coach(four_db9_return_domains(common=True)),
        DesignLintPolicy(),
    )

    assert report.status == "PASS"
    assert not report.findings


def test_project_policy_can_disposition_intentional_return_isolation() -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=REPEATED_PIN_RULE,
                mode="off",
                reason="Synthetic isolation control reviewed as intentional",
            ),
            DesignLintRuleOverride(
                rule_id=NUMBERED_RETURN_RULE,
                mode="off",
                reason="Synthetic isolation control reviewed as intentional",
            ),
        )
    )

    report = evaluate(
        "synthetic-four-db9-isolated",
        coach(four_db9_return_domains()),
        policy,
    )

    assert report.status == "PASS"
    assert all(item.disposition == "RULE_OFF" for item in report.findings)


def test_neutral_net_renaming_preserves_repeated_pin_review() -> None:
    isolated = four_db9_return_domains()
    renamed = isolated.model_copy(
        update={
            "nets": {
                f"NET_{index}": pins for index, pins in enumerate(isolated.nets.values(), start=1)
            }
        }
    )

    report = evaluate("synthetic-four-db9-neutral-nets", coach(renamed), DesignLintPolicy())
    repeated_pin_findings = [item for item in report.findings if item.rule_id == REPEATED_PIN_RULE]
    rules = {item.rule_id for item in report.findings}

    assert report.status == "REVIEW"
    assert len(repeated_pin_findings) == 2
    assert {pin for item in repeated_pin_findings for pin in item.evidence} == {
        f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)
    }
    assert NUMBERED_RETURN_RULE not in rules
    assert UNINDEXED_RETURN_RULE not in rules


def test_neutral_common_return_clears_repeated_pin_review() -> None:
    report = evaluate(
        "synthetic-four-db9-neutral-common",
        coach(four_db9_return_domains(common=True)),
        DesignLintPolicy(),
    )

    assert REPEATED_PIN_RULE not in {item.rule_id for item in report.findings}


def test_numbered_return_fingerprint_is_stable_under_mapping_reordering() -> None:
    isolated = four_db9_return_domains()
    reordered = isolated.model_copy(
        update={
            "nets": dict(reversed(tuple(isolated.nets.items()))),
            "component_symbols": dict(reversed(tuple(isolated.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(isolated.pin_functions.items()))),
        }
    )

    original_report = _source_bound_report(isolated)
    reordered_report = _source_bound_report(reordered)
    original_finding = _finding(original_report, NUMBERED_RETURN_RULE)
    reordered_finding = _finding(reordered_report, NUMBERED_RETURN_RULE)

    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        original_finding.fingerprint,
        original_finding.evidence,
    )
    assert reordered_report.netlist_sha256 != original_report.netlist_sha256


def test_unrelated_component_does_not_change_numbered_return_fingerprint() -> None:
    isolated = four_db9_return_domains()
    unrelated = isolated.model_copy(
        update={
            "components": {
                **isolated.components,
                "R9": ComponentContract(value="10k", footprint="Synthetic:R_0603"),
            },
            "nets": {
                **isolated.nets,
                "UNRELATED_A": ("R9.1",),
                "UNRELATED_B": ("R9.2",),
            },
            "component_symbols": {**isolated.component_symbols, "R9": "Device:R"},
            "component_pin_numbers": {**isolated.component_pin_numbers, "R9": ("1", "2")},
        }
    )

    original_report = _source_bound_report(isolated)
    unrelated_report = _source_bound_report(unrelated)
    original_finding = _finding(original_report, NUMBERED_RETURN_RULE)
    unrelated_finding = _finding(unrelated_report, NUMBERED_RETURN_RULE)

    assert unrelated_report.netlist_sha256 != original_report.netlist_sha256
    assert (unrelated_finding.fingerprint, unrelated_finding.evidence) == (
        original_finding.fingerprint,
        original_finding.evidence,
    )


@pytest.mark.parametrize(
    "add_unrelated_component",
    [pytest.param(False, id="original-source"), pytest.param(True, id="unrelated-change")],
)
def test_numbered_return_ignore_keeps_exact_scope(
    add_unrelated_component: bool,
) -> None:
    isolated = four_db9_return_domains()
    source = isolated.model_copy(
        update={
            "components": {
                **isolated.components,
                **(
                    {"R9": ComponentContract(value="10k", footprint="Synthetic:R_0603")}
                    if add_unrelated_component
                    else {}
                ),
            },
            "nets": {
                **isolated.nets,
                **(
                    {"UNRELATED_A": ("R9.1",), "UNRELATED_B": ("R9.2",)}
                    if add_unrelated_component
                    else {}
                ),
            },
            "component_symbols": {
                **isolated.component_symbols,
                **({"R9": "Device:R"} if add_unrelated_component else {}),
            },
            "component_pin_numbers": {
                **isolated.component_pin_numbers,
                **({"R9": ("1", "2")} if add_unrelated_component else {}),
            },
        }
    )
    original_finding = _finding(_source_bound_report(isolated), NUMBERED_RETURN_RULE)
    ignore = DesignLintIgnore(
        rule_id=NUMBERED_RETURN_RULE,
        fingerprint=original_finding.fingerprint,
        reason="Synthetic review accepts this explicit return-domain arrangement",
    )

    report = _source_bound_report(source, DesignLintPolicy(ignores=(ignore,)))

    assert _finding(report, NUMBERED_RETURN_RULE).fingerprint == original_finding.fingerprint
    assert _finding(report, NUMBERED_RETURN_RULE).disposition == "IGNORED"
    assert REPEATED_PIN_RULE in {
        item.rule_id for item in report.findings if item.disposition == "OPEN"
    }


@pytest.mark.parametrize(
    "add_unrelated_component",
    [pytest.param(False, id="original-source"), pytest.param(True, id="unrelated-change")],
)
def test_repeated_pin_ignore_does_not_hide_numbered_return_review(
    add_unrelated_component: bool,
) -> None:
    isolated = four_db9_return_domains()
    source = isolated
    if add_unrelated_component:
        source = isolated.model_copy(
            update={
                "components": {
                    **isolated.components,
                    "R9": ComponentContract(value="10k", footprint="Synthetic:R_0603"),
                },
                "nets": {
                    **isolated.nets,
                    "UNRELATED_A": ("R9.1",),
                    "UNRELATED_B": ("R9.2",),
                },
                "component_symbols": {**isolated.component_symbols, "R9": "Device:R"},
                "component_pin_numbers": {**isolated.component_pin_numbers, "R9": ("1", "2")},
            }
        )
    original_report = _source_bound_report(isolated)
    repeated_pin_findings = sorted(
        (item for item in original_report.findings if item.rule_id == REPEATED_PIN_RULE),
        key=lambda item: item.subject,
    )
    assert len(repeated_pin_findings) == 2
    ignored_peer, remaining_peer = repeated_pin_findings
    policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=REPEATED_PIN_RULE,
                fingerprint=ignored_peer.fingerprint,
                reason="Synthetic review accepts this one connector return-group difference",
            ),
        )
    )

    report = _source_bound_report(source, policy)
    peer_findings = {
        item.fingerprint: item for item in report.findings if item.rule_id == REPEATED_PIN_RULE
    }

    assert peer_findings[ignored_peer.fingerprint].disposition == "IGNORED"
    assert peer_findings[remaining_peer.fingerprint].disposition == "OPEN"
    assert _finding(report, NUMBERED_RETURN_RULE).disposition == "OPEN"


def test_commoned_returns_clear_numbered_return_hint() -> None:
    report = _source_bound_report(four_db9_return_domains(common=True))

    assert report.status == "PASS"
    assert NUMBERED_RETURN_RULE not in {item.rule_id for item in report.findings}
