"""CLI and MCP share exact native length-rule omission prompts."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    PcbDrcMinMaxRequirement,
    PcbSignalPathRequirement,
    PcbSignalPathRuleMap,
)
from tests.pcb_signal_path_unmapped_parity_support import (
    assert_signal_path_cli_mcp_parity,
    signal_path_surface_reports,
)
from tests.pcb_signal_path_unmapped_rule_support import native_rule

RULE_ID = "pcb.signal_path_unmapped_native_rule"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_unmapped_exact_length_scope_matches_cli_and_mcp(tmp_path: Path) -> None:
    rules = "\n".join(
        (
            "(version 1)",
            native_rule(
                "mapped-data-length",
                "DATA",
                condition="A.fromTo('J1-1', 'D1-1')",
            ),
            native_rule("unmapped-extra-length", "EXTRA"),
        )
    )
    requirements = DesignLintPolicy(
        pcb_signal_path_rule_map=PcbSignalPathRuleMap(
            basis="Synthetic reviewed route scope",
            paths=(
                PcbSignalPathRequirement(
                    id="data-path",
                    basis="Synthetic exact endpoint route",
                    net="DATA",
                    from_pad="J1.1",
                    to_pad="D1.1",
                    length=PcbDrcMinMaxRequirement(max_nm=25_000_000),
                ),
            ),
        )
    )
    cli_report, mcp_report = signal_path_surface_reports(
        tmp_path,
        requirements=requirements,
        rules_source=rules,
        nets={"DATA": ("J1.1", "D1.1"), "EXTRA": ("R1.1",)},
    )

    assert_signal_path_cli_mcp_parity(cli_report, mcp_report)
    assert mcp_report.status == "REVIEW", mcp_report.issues
    (finding,) = tuple(item for item in mcp_report.findings if item.rule_id == RULE_ID)
    assert finding.subject == "unmapped-extra-length: EXTRA is absent from signal-path coverage"
    assert finding.mode == "review" and finding.disposition == "OPEN"
    assert finding.evidence["net"] == ("EXTRA",)
    assert finding.evidence["source_sha256"] == (
        mcp_report.source_hashes["projects/controller/kicad/controller.kicad_dru"],
    )
    assert finding.evidence["source_netlist_sha256"] == (mcp_report.netlist_sha256,)
