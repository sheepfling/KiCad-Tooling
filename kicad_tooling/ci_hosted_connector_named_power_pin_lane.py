"""Run the focused native gate for named connector supply and return pins."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_connector_named_power_pins import (
    NAMED_CONNECTOR_POWER_PIN_CASES,
    verify_named_connector_power_pin_cases,
)
from .ci_hosted_connector_return_context import (
    ConnectorReturnLog,
    prepare_connector_return_fixture_context,
)
from .ci_hosted_connector_return_receipts import emit_connector_return_receipts


def connector_named_power_pin_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: ConnectorReturnLog,
    case_names: tuple[str, ...] = NAMED_CONNECTOR_POWER_PIN_CASES,
) -> None:
    """Export the requested named supply/return fault and connected control."""
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=image,
        log=log,
        case_names=case_names,
        stage_prefix="connector-named-power-pin-fixture",
    )
    verify_named_connector_power_pin_cases(context)
    emit_connector_return_receipts(context, {})
