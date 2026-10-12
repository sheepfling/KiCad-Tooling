"""Run the focused native gate for a named component return pin."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_component_named_return_pin import (
    COMPONENT_NAMED_RETURN_PIN_CASES,
    verify_component_named_return_pin_cases,
)
from .ci_hosted_connector_return_context import (
    ConnectorReturnLog,
    prepare_connector_return_fixture_context,
)
from .ci_hosted_connector_return_receipts import emit_connector_return_receipts


def component_named_return_pin_fixture_lane(
    root: Path, *, project: str, image: str, log: ConnectorReturnLog
) -> None:
    """Export only the named component return-pin fault and connected control."""
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=image,
        log=log,
        case_names=COMPONENT_NAMED_RETURN_PIN_CASES,
        stage_prefix="component-named-return-pin-fixture",
    )
    verify_component_named_return_pin_cases(context)
    emit_connector_return_receipts(context, {})
