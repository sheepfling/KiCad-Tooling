"""Run the focused native generic peer power-input fixture lane."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_component_peer_power_input import (
    COMPONENT_PEER_POWER_INPUT_CASES,
    verify_component_peer_power_input_cases,
)
from .ci_hosted_connector_return_context import (
    ConnectorReturnLog,
    prepare_connector_return_fixture_context,
)
from .ci_hosted_connector_return_receipts import emit_connector_return_receipts


def component_peer_power_input_fixture_lane(
    root: Path, *, project: str, image: str, log: ConnectorReturnLog
) -> None:
    """Export only the generic peer power-input fault and common-rail control."""
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=image,
        log=log,
        case_names=COMPONENT_PEER_POWER_INPUT_CASES,
        stage_prefix="component-peer-power-input-fixture",
    )
    verify_component_peer_power_input_cases(context)
    emit_connector_return_receipts(context, {})
