"""Differential-pair coverage must describe the current source inventory."""

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintRuleOverride,
    PcbDifferentialPairRuleCoverageReport,
)
from kicad_tooling.hwrepo.pcb_drc_rule_coverage import compare_native_rules
from tests.design_lint_fixtures import coach, observed
from tests.test_pcb_drc_coverage import incomplete_report, pair_map, pair_source_hashes, rules_text

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]


@pytest.mark.parametrize("complete", [False, True])
@pytest.mark.parametrize(
    "change", ["none", "board", "project", "rules-added", "other-added", "empty", "forged-board"]
)
def test_pair_coverage_requires_current_sources(complete: bool, change: str) -> None:
    coverage = incomplete_report()
    if complete:
        coverage = coverage.model_copy(
            update={
                "status": "COMPLETE",
                "entries": compare_native_rules(pair_map(), rules_text(), frozenset()),
            }
        )
    hashes = pair_source_hashes()
    if change == "board":
        hashes["kicad/controller.kicad_pcb"] = "1" * 64
    elif change == "project":
        hashes["kicad/controller.kicad_pro"] = "1" * 64
    elif change == "rules-added":
        hashes["kicad/controller.kicad_dru"] = "1" * 64
    elif change == "other-added":
        hashes["kicad/other.kicad_sch"] = "1" * 64
    elif change == "empty":
        hashes = {}
    elif change == "forged-board":
        coverage = coverage.model_copy(update={"board_sha256": "1" * 64})

    # Existing serialized reports remain readable even when their sources are stale.
    coverage = PcbDifferentialPairRuleCoverageReport.model_validate_json(coverage.model_dump_json())
    result = evaluate(
        "synthetic-pair",
        coach(observed()).model_copy(update={"source_hashes": hashes}),
        DesignLintPolicy(pcb_differential_pair_rule_map=pair_map()),
        pcb_differential_pair_coverage=coverage,
    )
    if change == "none":
        assert result.pcb_differential_pair_rules.status == coverage.status
    else:
        assert result.status == "BLOCKED"
        assert result.pcb_differential_pair_rules.status == "BLOCKED"
        assert "current native source inventory" in (result.pcb_differential_pair_rules.issue or "")
        assert not any(
            item.rule_id == "pcb.differential_pair_rule_coverage" for item in result.findings
        )


def test_disabled_pair_rule_does_not_require_current_source_evidence() -> None:
    result = evaluate(
        "synthetic-pair",
        coach(observed()),
        DesignLintPolicy(
            pcb_differential_pair_rule_map=pair_map(),
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.differential_pair_rule_coverage",
                    mode="off",
                    reason="Synthetic disabled policy",
                ),
            ),
        ),
        pcb_differential_pair_coverage=incomplete_report(),
    )
    assert result.pcb_differential_pair_rules.status == "DISABLED"


def test_configured_pair_map_without_a_scan_is_blocked() -> None:
    result = evaluate(
        "synthetic-pair",
        coach(observed()).model_copy(update={"source_hashes": pair_source_hashes()}),
        DesignLintPolicy(pcb_differential_pair_rule_map=pair_map()),
    )

    assert result.status == "BLOCKED"
    assert result.pcb_differential_pair_rules.status == "BLOCKED"
    assert "was not supplied" in (result.pcb_differential_pair_rules.issue or "")
