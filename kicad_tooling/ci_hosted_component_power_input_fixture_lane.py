"""Run the focused native generic component power-input fixture lane."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_component_power_input import (
    GENERIC_COMPONENT_POWER_INPUT_CASES,
    verify_generic_component_power_input_cases,
)
from .ci_hosted_connector_return_context import (
    ConnectorReturnLog,
    prepare_connector_return_fixture_context,
)
from .ci_hosted_connector_return_receipts import emit_connector_return_receipts


def component_power_input_fixture_lane(
    root: Path, *, project: str, image: str, log: ConnectorReturnLog
) -> None:
    """Export only the component power-input fault and control schematics."""
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=image,
        log=log,
        case_names=GENERIC_COMPONENT_POWER_INPUT_CASES,
        stage_prefix="component-power-input-fixture",
    )
    verify_generic_component_power_input_cases(context)
    emit_connector_return_receipts(context, {})
