"""Synthetic source-mapped connector contacts assigned to named rail nets."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.connector_peer_pin_models import ConnectorPinRole
from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import ContractCoachReport, NetlistContract
from tests.connector_mapped_interface_support import interface_coverage
from tests.design_lint_fixtures.connector_mapped_interface_signal import (
    mapped_interface_netlist,
)


def mapped_named_rail_netlist(
    *,
    target_net: str = "GND",
    target_function: str = "Pin_2",
    target_type: str = "input",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build one generic connector contact with a controlled assigned label."""
    return mapped_interface_netlist(
        target_net=target_net,
        target_function=target_function,
        target_type=target_type,
        dnp=dnp,
    )


def mapped_named_rail_report(
    observed: NetlistContract,
    *,
    role: ConnectorPinRole,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    """Evaluate one complete source-matched interface with the selected role."""
    if coverage is None:
        coverage = interface_coverage(observed, target_role=role)
    project_id = "synthetic-mapped-named-rail"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        observed=observed,
        netlist_sha256=sha256(model_json_bytes(observed)).hexdigest(),
    )
    report = evaluate(
        project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return report, coverage
