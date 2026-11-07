"""Run the focused native generic connector power-input fixture lane."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_connector_return_context import (
    ConnectorReturnLog,
    prepare_connector_return_fixture_context,
)
from .ci_hosted_connector_return_power import verify_generic_connector_power_input
from .ci_hosted_connector_return_receipts import emit_connector_return_receipts


def connector_unconnected_power_input_fixture_lane(
    root: Path, *, project: str, image: str, log: ConnectorReturnLog
) -> None:
    """Export only the generic connector power-input fault and common-supply control."""
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=image,
        log=log,
        case_names=(
            "unconnected-generic-power-input-fault",
            "unconnected-generic-power-input-control",
        ),
        stage_prefix="connector-power-input-fixture",
    )
    verify_generic_connector_power_input(context)
    emit_connector_return_receipts(context, {})
