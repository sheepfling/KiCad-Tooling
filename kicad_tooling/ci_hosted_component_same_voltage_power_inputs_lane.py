"""Run the exact-version native same-voltage power-input fixture lane."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_component_same_voltage_power_inputs import (
    RULE_ID,
    SAME_VOLTAGE_POWER_INPUT_CASES,
    verify_same_voltage_power_input_cases,
)
from .ci_hosted_connector_return_context import (
    ConnectorReturnLog,
    prepare_connector_return_fixture_context,
)
from .ci_hosted_connector_return_receipts import emit_connector_return_receipts


def same_voltage_power_input_fixture_lane(
    root: Path, *, project: str, image: str, log: ConnectorReturnLog
) -> None:
    """Export only the split-domain fault and common-rail control twice."""
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=image,
        log=log,
        case_names=SAME_VOLTAGE_POWER_INPUT_CASES,
        stage_prefix="same-voltage-power-input-fixture",
        rule_overrides_by_case={case: (RULE_ID,) for case in SAME_VOLTAGE_POWER_INPUT_CASES},
    )
    verify_same_voltage_power_input_cases(context)
    emit_connector_return_receipts(context, {})
