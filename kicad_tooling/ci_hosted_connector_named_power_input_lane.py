"""Run the focused native connector named power-input alias lane."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_connector_named_power_input import CASES, verify_connector_named_power_input_cases
from .ci_hosted_connector_return_context import (
    ConnectorReturnLog,
    prepare_connector_return_fixture_context,
)
from .ci_hosted_connector_return_receipts import emit_connector_return_receipts


def connector_named_power_input_fixture_lane(
    root: Path, *, project: str, image: str, log: ConnectorReturnLog
) -> None:
    """Export only the named cross-symbol power-input fault and common control."""
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=image,
        log=log,
        case_names=CASES,
        stage_prefix="connector-named-power-input-alias-fixture",
    )
    verify_connector_named_power_input_cases(context)
    emit_connector_return_receipts(context, {})
