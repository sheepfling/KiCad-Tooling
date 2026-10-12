"""Run the focused native connector named power-output alias lane."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_connector_named_power_output import (
    CASES,
    verify_connector_named_power_output_cases,
)
from .ci_hosted_connector_return_context import (
    ConnectorReturnLog,
    prepare_connector_return_fixture_context,
)
from .ci_hosted_connector_return_receipts import emit_connector_return_receipts


def connector_named_power_output_fixture_lane(
    root: Path, *, project: str, image: str, log: ConnectorReturnLog
) -> None:
    """Export the named power-output alias fault and all-open/common controls."""
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=image,
        log=log,
        case_names=CASES,
        stage_prefix="connector-named-power-output-open-fixture",
    )
    verify_connector_named_power_output_cases(context)
    emit_connector_return_receipts(context, {})
