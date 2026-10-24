"""Run the exact native repeated signal-function unassigned-pin lane."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_component_repeated_signal_pin_unassigned import (
    COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CASES,
    COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_FAULT,
    COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_RULE_ID,
    verify_component_repeated_signal_pin_unassigned_cases,
)
from .ci_hosted_connector_return_context import (
    ConnectorReturnLog,
    prepare_connector_return_fixture_context,
)
from .ci_hosted_connector_return_receipts import emit_connector_return_receipts


def component_repeated_signal_pin_unassigned_fixture_lane(
    root: Path, *, project: str, image: str, log: ConnectorReturnLog
) -> None:
    """Export only the open repeated-pin fault and common-net control."""
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=image,
        log=log,
        case_names=COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CASES,
        stage_prefix="component-repeated-signal-pin-unassigned-fixture",
        rule_overrides_by_case={
            COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_FAULT: (
                COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_RULE_ID,
            )
        },
    )
    verify_component_repeated_signal_pin_unassigned_cases(context)
    emit_connector_return_receipts(context, {})
