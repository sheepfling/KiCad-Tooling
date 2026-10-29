"""Connector-lint evidence retained by an incomplete contract-coach report."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.contract_coach import text_report
from kicad_tooling.hwrepo.models import ContractCoachReport
from kicad_tooling.hwrepo.return_nets import return_net_groups
from tests.design_lint_fixtures import four_db9_return_domains

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


def test_incomplete_contract_report_localizes_numbered_db9_return_nets() -> None:
    source = four_db9_return_domains()
    observed = source.model_copy(
        update={
            "nets": {
                f"0V PWM {reference}": (f"J{reference}.7", f"J{reference}.9")
                for reference in range(1, 5)
            }
        }
    )
    report = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-four-db9",
        observed=observed,
        return_net_groups=return_net_groups(observed),
        next_actions=("Review the independently authored connector pinout.",),
    )

    rendered = text_report(report)

    assert "Possible split returns (0V PWM):" in rendered
    for reference in range(1, 5):
        assert f"0V PWM {reference}: J{reference}.7, J{reference}.9" in rendered
    assert "independently authored" in rendered
