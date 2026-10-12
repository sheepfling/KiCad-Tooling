"""Coordinate the deterministic connector return fixture themes."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_connector_return_context import (
    ConnectorReturnLog,
    prepare_connector_return_fixture_context,
)
from .ci_hosted_connector_return_db9_returns import verify_db9_neutral_return_cases
from .ci_hosted_connector_return_grounding import verify_connector_grounding_contracts
from .ci_hosted_connector_return_mapped_returns import verify_mapped_return_interfaces
from .ci_hosted_connector_return_mapped_supplies import verify_mapped_supply_interfaces
from .ci_hosted_connector_return_offboard import verify_offboard_connector_interfaces
from .ci_hosted_connector_return_peer_outliers import verify_peer_pin_outlier_cases
from .ci_hosted_connector_return_peer_pins import verify_peer_pin_assignments
from .ci_hosted_connector_return_peer_power import verify_peer_power_inputs
from .ci_hosted_connector_return_peer_scope import verify_connector_peer_scope
from .ci_hosted_connector_return_power import verify_connector_power_inputs
from .ci_hosted_connector_return_receipts import emit_connector_return_receipts
from .ci_hosted_connector_return_returns import (
    verify_connector_return_distribution,
    verify_numbered_pwm_return_cases,
)
from .ci_hosted_connector_return_supply import verify_positive_rail_return_cases


def connector_return_lint_fixture_lane(
    root: Path, *, project: str, image: str, log: ConnectorReturnLog
) -> None:
    """Run the themed synthetic connector-return fixture suite."""
    context = prepare_connector_return_fixture_context(root, project=project, image=image, log=log)
    db9_control_nets = verify_connector_return_distribution(context)
    verify_connector_power_inputs(context)
    verify_positive_rail_return_cases(context)
    verify_connector_grounding_contracts(context, db9_control_nets)
    verify_db9_neutral_return_cases(context)
    verify_peer_power_inputs(context)
    peer_pin_coverage_receipts = verify_peer_pin_assignments(context)
    verify_offboard_connector_interfaces(context)
    verify_peer_pin_outlier_cases(context)
    verify_mapped_return_interfaces(context)
    verify_mapped_supply_interfaces(context)
    verify_connector_peer_scope(context)
    emit_connector_return_receipts(context, peer_pin_coverage_receipts)


def numbered_pwm_return_fixture_lane(
    root: Path, *, project: str, image: str, log: ConnectorReturnLog
) -> None:
    """Run only the native numbered 0V PWM return fault/control cases."""
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=image,
        log=log,
        case_names=("four-db9-pwm-fault", "four-db9-pwm-control"),
    )
    verify_numbered_pwm_return_cases(context)
    emit_connector_return_receipts(context, {})
