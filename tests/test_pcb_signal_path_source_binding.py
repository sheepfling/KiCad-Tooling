"""Signal-path DRC coverage must bind the current map and source inventory."""

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintRuleOverride,
    PcbSignalPathRuleCoverageReport,
)
from tests.design_lint_fixtures import coach, observed
from tests.design_lint_fixtures.pcb_signal_path import (
    design_lint_report,
    incomplete_signal_report,
    path_map,
    signal_source_hashes,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]


def test_complete_signal_path_coverage_cannot_cross_source_inventories() -> None:
    original = design_lint_report(fault=False)
    assert original.pcb_signal_path_rules.status == "COMPLETE"
    full_map = path_map()
    requirements = full_map.model_copy(update={"paths": (full_map.paths[0],), "bundles": ()})
    changed_sources = dict(original.source_hashes)
    changed_sources["hardware/synthetic-paths.kicad_pcb"] = "1" * 64
    result = evaluate(
        "synthetic-path",
        coach(observed()).model_copy(update={"source_hashes": changed_sources}),
        DesignLintPolicy(pcb_signal_path_rule_map=requirements),
        pcb_signal_path_coverage=original.pcb_signal_path_rules,
    )
    assert result.status == "BLOCKED"
    assert result.pcb_signal_path_rules.status == "BLOCKED"
    assert "current native source inventory" in (result.pcb_signal_path_rules.issue or "")


@pytest.mark.parametrize(
    "change", ["none", "board", "project", "rules-removed", "other-added", "empty", "forged-rules"]
)
def test_signal_path_requires_current_sources(change: str) -> None:
    coverage = incomplete_signal_report(path_map())
    hashes = signal_source_hashes()
    if change == "board":
        hashes["hardware/synthetic.kicad_pcb"] = "1" * 64
    elif change == "project":
        hashes["hardware/synthetic.kicad_pro"] = "1" * 64
    elif change == "rules-removed":
        del hashes["hardware/synthetic.kicad_dru"]
    elif change == "other-added":
        hashes["hardware/other.kicad_sch"] = "1" * 64
    elif change == "empty":
        hashes = {}
    elif change == "forged-rules":
        coverage = coverage.model_copy(update={"rules_sha256": "1" * 64})

    coverage = PcbSignalPathRuleCoverageReport.model_validate_json(coverage.model_dump_json())
    result = evaluate(
        "synthetic-path",
        coach(observed()).model_copy(update={"source_hashes": hashes}),
        DesignLintPolicy(pcb_signal_path_rule_map=path_map()),
        pcb_signal_path_coverage=coverage,
    )
    if change == "none":
        assert result.pcb_signal_path_rules.status == "INCOMPLETE"
        assert any(item.rule_id == "pcb.signal_path_rule_coverage" for item in result.findings)
    else:
        assert result.status == "BLOCKED"
        assert result.pcb_signal_path_rules.status == "BLOCKED"
        assert "current native source inventory" in (result.pcb_signal_path_rules.issue or "")
        assert not any(item.rule_id == "pcb.signal_path_rule_coverage" for item in result.findings)


@pytest.mark.parametrize("state", ["wrong-map", "not-requested", "disabled", "no-map"])
def test_signal_path_rejects_unbound_coverage(state: str) -> None:
    coverage = incomplete_signal_report(path_map())
    policy = DesignLintPolicy(pcb_signal_path_rule_map=path_map())
    if state == "wrong-map":
        coverage = coverage.model_copy(update={"map_sha256": "0" * 64})
    elif state == "not-requested":
        coverage = PcbSignalPathRuleCoverageReport()
    elif state == "disabled":
        coverage = PcbSignalPathRuleCoverageReport(status="DISABLED", mode="off")
    else:
        policy = DesignLintPolicy()
    result = evaluate(
        "synthetic-path",
        coach(observed()).model_copy(update={"source_hashes": signal_source_hashes()}),
        policy,
        pcb_signal_path_coverage=coverage,
    )
    assert result.status == "BLOCKED"
    assert result.pcb_signal_path_rules.status == "BLOCKED"
    assert not any(item.rule_id == "pcb.signal_path_rule_coverage" for item in result.findings)


def test_signal_path_off_does_not_require_current_evidence() -> None:
    result = evaluate(
        "synthetic-path",
        coach(observed()),
        DesignLintPolicy(
            pcb_signal_path_rule_map=path_map(),
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.signal_path_rule_coverage", mode="off", reason="Synthetic policy"
                ),
            ),
        ),
        pcb_signal_path_coverage=incomplete_signal_report(path_map()),
    )
    assert result.pcb_signal_path_rules.status == "DISABLED"
