"""Synthetic tests for exact differential-pair native DRC rule coverage."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    PcbDifferentialPairRuleCoverageReport,
    PcbDifferentialPairRuleMap,
    PcbDifferentialPairRuleRequirement,
    PcbDrcMaximumRequirement,
    PcbDrcMinMaxRequirement,
)
from kicad_tooling.hwrepo.pcb_drc_rule_coverage import compare_native_rules

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
]


FIXTURES = Path(__file__).parent / "fixtures/design_lint/differential-pair"


def pair_map() -> PcbDifferentialPairRuleMap:
    return PcbDifferentialPairRuleMap(
        basis="Synthetic reviewed pair requirement",
        requirements=(
            PcbDifferentialPairRuleRequirement(
                id="usb-data",
                basis="Synthetic interface requirement",
                positive_net="USB_D_P",
                negative_net="USB_D_N",
                pair_selector="USB_D_",
                track_width=PcbDrcMinMaxRequirement(min_nm=250_000),
                diff_pair_gap=PcbDrcMinMaxRequirement(min_nm=150_000, max_nm=500_000),
                skew=PcbDrcMaximumRequirement(max_nm=100_000),
                uncoupled_length=PcbDrcMaximumRequirement(max_nm=200_000),
            ),
        ),
    )


def rules_text() -> str:
    return (FIXTURES / "control.kicad_dru").read_text(encoding="utf-8")


def incomplete_report() -> PcbDifferentialPairRuleCoverageReport:
    (entry,) = compare_native_rules(pair_map(), "", frozenset())
    return PcbDifferentialPairRuleCoverageReport(
        status="INCOMPLETE",
        mode="review",
        map_sha256="a" * 64,
        source_inventory_sha256="b" * 64,
        project_path="kicad/controller.kicad_pro",
        project_sha256="c" * 64,
        rules_path="kicad/controller.kicad_dru",
        board_path="kicad/controller.kicad_pcb",
        board_sha256="d" * 64,
        native_summary_path="build/native/summary.json",
        native_summary_sha256="e" * 64,
        native_drc_path="build/native/drc.json",
        native_drc_sha256="f" * 64,
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5@sha256:" + "a" * 64,
        entries=(entry,),
    )


def test_no_rules_skew_fixture_is_identical_and_has_no_native_rule_file() -> None:
    assert (FIXTURES / "no-rules-skew.kicad_pcb").read_bytes() == (
        FIXTURES / "fault-skew.kicad_pcb"
    ).read_bytes()
    assert not (FIXTURES / "no-rules-skew.kicad_dru").exists()


def test_exact_native_rules_cover_authored_pair_constraints() -> None:
    (entry,) = compare_native_rules(pair_map(), rules_text(), frozenset())
    assert entry.status == "COMPLETE"
    assert [item.status for item in entry.constraints] == [
        "COVERED",
        "COVERED",
        "COVERED",
        "COVERED",
    ]
    assert entry.constraints[0].observed_min_nm == 250_000
    assert entry.constraints[1].observed_max_nm == 500_000


def test_rule_and_requirement_order_preserve_coverage_but_bound_mutation_is_detected() -> None:
    usb_pair_map = pair_map()
    serial_requirement = PcbDifferentialPairRuleRequirement(
        id="serial-data",
        basis="Synthetic serial pair requirement",
        positive_net="SERIAL+",
        negative_net="SERIAL-",
        pair_selector="SERIAL",
        track_width=PcbDrcMinMaxRequirement(min_nm=250_000),
    )
    requirements = usb_pair_map.model_copy(
        update={"requirements": (*usb_pair_map.requirements, serial_requirement)}
    )
    reordered_requirements = requirements.model_copy(
        update={"requirements": tuple(reversed(requirements.requirements))}
    )
    native_source = rules_text()
    chunks = re.split(r"(?m)(?=^\(rule )", native_source.strip())
    assert len(chunks) > 2
    reordered_native_source = chunks[0] + "\n" + "\n".join(reversed(chunks[1:])) + "\n"

    source_coverage = compare_native_rules(requirements, native_source, frozenset())
    native_reordered_coverage = compare_native_rules(
        requirements, reordered_native_source, frozenset()
    )
    map_reordered_coverage = compare_native_rules(
        reordered_requirements, native_source, frozenset()
    )
    by_id = lambda entries: {item.id: item.model_dump(mode="json") for item in entries}
    assert source_coverage == native_reordered_coverage
    assert by_id(source_coverage) == by_id(map_reordered_coverage)
    assert [item.id for item in map_reordered_coverage] == [
        item.id for item in reversed(source_coverage)
    ]
    assert hashlib.sha256(native_source.encode("utf-8")).hexdigest() != (
        hashlib.sha256(reordered_native_source.encode("utf-8")).hexdigest()
    )
    assert hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest() != (
        hashlib.sha256(reordered_requirements.model_dump_json().encode("utf-8")).hexdigest()
    )

    changed_bound_source = native_source.replace("(min 0.25mm)", "(min 0.2mm)", 1)
    changed_coverage = compare_native_rules(requirements, changed_bound_source, frozenset())
    changed_usb_width = next(
        item for item in changed_coverage[0].constraints if item.constraint == "track_width"
    )
    assert changed_usb_width.status == "MISMATCH"


def test_missing_rules_are_a_coverage_gap() -> None:
    (entry,) = compare_native_rules(pair_map(), "", frozenset())
    assert entry.status == "INCOMPLETE"
    assert {item.status for item in entry.constraints} == {"MISSING"}


def test_wrong_bound_is_a_mismatch() -> None:
    altered = rules_text().replace("(max 0.5mm)", "(max 0.45mm)")
    (entry,) = compare_native_rules(pair_map(), altered, frozenset())
    gap = next(item for item in entry.constraints if item.constraint == "diff_pair_gap")
    assert gap.status == "MISMATCH"
    assert gap.observed_max_nm == 450_000


def test_duplicate_matching_rules_are_ambiguous() -> None:
    duplicate = """
(rule "duplicate-gap"
  (condition "A.inDiffPair('USB_D_')")
  (constraint diff_pair_gap (min 0.15mm) (max 0.5mm)))
"""
    (entry,) = compare_native_rules(pair_map(), rules_text() + duplicate, frozenset())
    gap = next(item for item in entry.constraints if item.constraint == "diff_pair_gap")
    assert gap.status == "AMBIGUOUS"
    assert set(gap.rule_names) == {"synthetic-dp-gap", "duplicate-gap"}


def test_native_ignored_severity_is_not_credited_as_coverage() -> None:
    (entry,) = compare_native_rules(pair_map(), rules_text(), frozenset({"skew_out_of_range"}))
    skew = next(item for item in entry.constraints if item.constraint == "skew")
    assert skew.status == "IGNORED"


def test_explicit_custom_rule_ignore_severity_is_not_credited_as_coverage() -> None:
    ignored_skew_rule = rules_text().replace(
        '(rule "synthetic-dp-skew"',
        '(rule "synthetic-dp-skew"\n  (severity ignore)',
        1,
    )
    (entry,) = compare_native_rules(pair_map(), ignored_skew_rule, frozenset())
    skew = next(item for item in entry.constraints if item.constraint == "skew")
    assert entry.status == "INCOMPLETE"
    assert skew.status == "IGNORED"
    assert "custom-rule severity is 'ignore'" in (skew.issue or "")


def test_unrecognized_custom_rule_severity_remains_unsupported() -> None:
    unsupported_skew_rule = rules_text().replace(
        '(rule "synthetic-dp-skew"',
        '(rule "synthetic-dp-skew"\n  (severity silent)',
        1,
    )
    (entry,) = compare_native_rules(pair_map(), unsupported_skew_rule, frozenset())
    skew = next(item for item in entry.constraints if item.constraint == "skew")
    assert entry.status == "INCOMPLETE"
    assert skew.status == "UNSUPPORTED"
    assert "expected error, warning, ignore, or exclusion" in (skew.issue or "")


def test_unsupported_rule_units_remain_visible() -> None:
    altered = rules_text().replace("(max 0.5mm)", "(max 0.5inch)")
    (entry,) = compare_native_rules(pair_map(), altered, frozenset())
    gap = next(item for item in entry.constraints if item.constraint == "diff_pair_gap")
    assert gap.status == "UNSUPPORTED"
    assert "use mm or mil" in (gap.issue or "")


def test_rule_for_another_pair_does_not_cover_requirement() -> None:
    altered = rules_text().replace("USB_D_", "USB_A_")
    (entry,) = compare_native_rules(pair_map(), altered, frozenset())
    assert {item.status for item in entry.constraints} == {"MISSING"}


def test_unsupported_net_suffix_pattern_is_not_claimed_as_covered() -> None:
    requirement = (
        pair_map()
        .requirements[0]
        .model_copy(
            update={
                "positive_net": "USB_DP",
                "negative_net": "USB_DN",
                "pair_selector": "USB_D",
            }
        )
    )
    requirements = pair_map().model_copy(update={"requirements": (requirement,)})
    (entry,) = compare_native_rules(requirements, rules_text(), frozenset())
    assert entry.status == "INCOMPLETE"
    assert any("suffix pattern" in issue for issue in entry.issues)


def test_plus_minus_pair_names_and_mil_bounds_are_supported() -> None:
    requirements = PcbDifferentialPairRuleMap(
        basis="Synthetic serial pair requirement",
        requirements=(
            PcbDifferentialPairRuleRequirement(
                id="serial-pair",
                basis="Synthetic serial interface requirement",
                positive_net="SERIAL+",
                negative_net="SERIAL-",
                pair_selector="SERIAL",
                track_width=PcbDrcMinMaxRequirement(min_nm=254_000),
            ),
        ),
    )
    native_rules = (
        '(version 1)\n(rule "serial-width" '
        "(condition \"A.inDiffPair('SERIAL')\") "
        "(constraint track_width (min 10mil)))"
    )
    (entry,) = compare_native_rules(requirements, native_rules, frozenset())
    assert entry.status == "COMPLETE"
    assert entry.constraints[0].observed_min_nm == 254_000


def test_incomplete_coverage_emits_a_configurable_review_finding() -> None:
    from kicad_tooling.hwrepo.design_lint import evaluate
    from tests.design_lint_fixtures import coach, observed

    report = evaluate(
        "synthetic-pair",
        coach(observed()),
        DesignLintPolicy(pcb_differential_pair_rule_map=pair_map()),
        pcb_differential_pair_coverage=incomplete_report(),
    )
    finding = next(
        item for item in report.findings if item.rule_id == "pcb.differential_pair_rule_coverage"
    )
    assert report.status == "REVIEW"
    assert finding.disposition == "OPEN"

    blocked = evaluate(
        "synthetic-pair",
        coach(observed()),
        DesignLintPolicy(
            pcb_differential_pair_rule_map=pair_map(),
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.differential_pair_rule_coverage",
                    mode="block",
                    reason="Synthetic test policy",
                ),
            ),
        ),
        pcb_differential_pair_coverage=incomplete_report(),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-pair",
        coach(observed()),
        DesignLintPolicy(
            pcb_differential_pair_rule_map=pair_map(),
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.differential_pair_rule_coverage",
                    mode="off",
                    reason="Synthetic test policy",
                ),
            ),
        ),
        pcb_differential_pair_coverage=incomplete_report(),
    )
    assert disabled.status == report.status
    assert disabled.pcb_differential_pair_rules.status == "DISABLED"
    assert not any(
        item.rule_id == "pcb.differential_pair_rule_coverage" for item in disabled.findings
    )

    ignored = evaluate(
        "synthetic-pair",
        coach(observed()),
        DesignLintPolicy(
            pcb_differential_pair_rule_map=pair_map(),
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic review accepts this exact coverage gap",
                ),
            ),
        ),
        pcb_differential_pair_coverage=incomplete_report(),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "pcb.differential_pair_rule_coverage"
    )
    assert ignored.status == report.status
    assert ignored_finding.disposition == "IGNORED"
