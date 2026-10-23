"""Source-matched report builder for generic connector contacts mapped as other."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import ContractCoachReport, NetlistContract
from tests.connector_mapped_interface_support import interface_coverage

PROJECT_ID = "synthetic-mapped-interface-other"


def mapped_interface_other_report(
    observed: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    unconnected_reason: str | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    """Evaluate one synthetic report with current role=other interface evidence."""
    if coverage is None:
        coverage = interface_coverage(
            observed,
            target_role="other",
            unconnected_reason=unconnected_reason,
        )
    netlist_sha256 = sha256(model_json_bytes(observed)).hexdigest()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=PROJECT_ID,
        observed=observed,
        netlist_sha256=netlist_sha256,
    )
    report = evaluate(
        PROJECT_ID,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return report, coverage
