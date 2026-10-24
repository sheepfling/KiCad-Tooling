"""Synthetic SPI roster-coverage hints and project rule decisions."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
    SpiAnalysis,
)
from kicad_tooling.hwrepo.spi_participants import SpiRosterContext, unmapped_spi_participants

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]

_CONTRACT_SHA256 = "b" * 64


from tests.spi_participant_support import coach, spi_netlist, spi_roster


def test_unlisted_participant_is_order_stable_and_roster_entry_clears_it() -> None:
    source = spi_netlist()
    rule_id = "bus.spi_unmapped_participant"
    omitted_device_roster = spi_roster(device_references=("U2",))
    complete_roster = spi_roster()

    def lint(netlist: NetlistContract, analysis: SpiAnalysis) -> tuple[str, str, DesignLintReport]:
        netlist_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
        roster_hash = hashlib.sha256(analysis.model_dump_json().encode("utf-8")).hexdigest()
        context = SpiRosterContext(
            state="required",
            analysis=analysis,
            source_path="projects/synthetic-spi-roster/electrical.json",
            source_sha256=roster_hash,
        )
        report = evaluate(
            "synthetic-spi-roster",
            coach(netlist, netlist_hash),
            DesignLintPolicy(),
            spi_roster=context,
        )
        return netlist_hash, roster_hash, report

    source_hash, roster_hash, original = lint(source, omitted_device_roster)
    assert original.netlist_sha256 == source_hash
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    assert tuple(original_findings) == ("U3: SPI roster coverage",)
    original_finding = original_findings["U3: SPI roster coverage"]
    assert original_finding[1]["electrical_contract_sha256"] == (roster_hash,)

    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered_hash, reordered_roster_hash, reordered = lint(reordered_source, omitted_device_roster)
    assert source_hash != reordered_hash
    assert roster_hash == reordered_roster_hash
    assert reordered.netlist_sha256 == reordered_hash
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings

    mapped_hash, mapped_roster_hash, mapped = lint(source, complete_roster)
    assert mapped_hash == source_hash
    assert mapped_roster_hash != roster_hash
    assert rule_id not in {item.rule_id for item in mapped.findings}


def test_unmapped_spi_ic_without_roster_is_review_candidate() -> None:
    report = evaluate(
        "synthetic-spi-roster",
        coach(spi_netlist()),
        DesignLintPolicy(),
    )
    findings = [item for item in report.findings if item.rule_id == "bus.spi_unmapped_participant"]
    assert report.status == "REVIEW"
    assert {item.subject for item in findings} == {
        "U1: SPI roster coverage",
        "U2: SPI roster coverage",
        "U3: SPI roster coverage",
    }
    assert "no configured project SPI device map" in findings[0].message
    assert findings[2].evidence["SCK_pins"] == ("U3.1",)
    assert findings[2].evidence["input_data_pins"] == ("U3.2",)
    assert findings[2].evidence["output_data_pins"] == ("U3.3",)
    assert findings[2].evidence["chip_select_pins"] == ("U3.4",)


def test_unlisted_spi_peer_is_found_when_roster_covers_another_device() -> None:
    context = SpiRosterContext(
        state="required",
        analysis=spi_roster(device_references=("U2",)),
        source_path="projects/synthetic-spi-roster/electrical.json",
        source_sha256=_CONTRACT_SHA256,
    )
    report = evaluate(
        "synthetic-spi-roster",
        coach(spi_netlist()),
        DesignLintPolicy(),
        spi_roster=context,
    )
    findings = [item for item in report.findings if item.rule_id == "bus.spi_unmapped_participant"]
    assert tuple(item.subject for item in findings) == ("U3: SPI roster coverage",)
    finding = findings[0]
    assert "not listed in the project SPI device map" in finding.message
    assert finding.evidence["electrical_contract_path"] == (
        "projects/synthetic-spi-roster/electrical.json",
    )
    assert finding.evidence["electrical_contract_sha256"] == (_CONTRACT_SHA256,)


def test_dnp_non_ic_and_incomplete_signal_patterns_are_excluded() -> None:
    observed = spi_netlist(dnp=("U3",), include_connector=True, partial_ic=True)
    candidates = unmapped_spi_participants(observed, SpiRosterContext(state="not_configured"))
    assert {item.reference for item in candidates} == {"U1", "U2"}


def test_candidate_obeys_review_block_off_and_exact_ignore_decisions() -> None:
    observed = spi_netlist()
    review = evaluate("synthetic-spi-roster", coach(observed), DesignLintPolicy())
    finding = next(
        item for item in review.findings if item.rule_id == "bus.spi_unmapped_participant"
    )
    assert finding.mode == "review"

    blocked = evaluate(
        "synthetic-spi-roster",
        coach(observed),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.spi_unmapped_participant",
                    mode="block",
                    reason="Every fitted SPI-capable IC needs a reviewed roster disposition",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-spi-roster",
        coach(observed),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.spi_unmapped_participant",
                    mode="off",
                    reason="This project records SPI membership elsewhere",
                ),
            )
        ),
    )
    disabled_finding = next(
        item for item in disabled.findings if item.rule_id == "bus.spi_unmapped_participant"
    )
    assert disabled.status == "PASS"
    assert disabled_finding.disposition == "RULE_OFF"

    ignored = evaluate(
        "synthetic-spi-roster",
        coach(observed),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="This synthetic controller is intentionally outside the roster",
                ),
            )
        ),
    )
    ignored_finding = next(
        item
        for item in ignored.findings
        if item.rule_id == "bus.spi_unmapped_participant"
        and item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"
