"""Typed source and report projections for unconnected connector pins."""

from __future__ import annotations

from typing import Literal, cast

import pytest

from kicad_tooling.hwrepo.connector_return_pins import (
    UnconnectedConnectorPinCategory,
    UnconnectedConnectorPinRoleSource,
    UnconnectedGenericPowerInputConnectorPin,
    UnconnectedGenericPowerOutputConnectorPin,
    UnconnectedNamedConnectorPin,
)
from kicad_tooling.hwrepo.design_lint_connector_unconnected_pin_candidate_evidence import (
    UnconnectedConnectorPinCandidate,
    project_unconnected_connector_pin_evidence,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.evidence_lint]


@pytest.mark.parametrize(
    ("source", "rule_id", "expected_evidence"),
    [
        (
            UnconnectedNamedConnectorPin(
                pin="J1.1", function="VDD", category="supply", role_source="native_symbol"
            ),
            "connector.unconnected_supply_pin",
            {"J1.1": ()},
        ),
        (
            UnconnectedNamedConnectorPin(
                pin="J1.2",
                function="RETURN",
                category="return",
                role_source="project_interface",
            ),
            "connector.unconnected_return_pin",
            {"J1.2": (), "role_source": ("project interface catalog",)},
        ),
        (
            UnconnectedGenericPowerInputConnectorPin(
                pin="J2.1",
                symbol="Synthetic:GenericPowerInputConnector",
                function="1",
                electrical_type="power_in",
            ),
            "connector.unconnected_power_input",
            {
                "symbol": ("Synthetic:GenericPowerInputConnector",),
                "pin_electrical_type": ("power_in",),
                "J2.1": (),
                "native_pin_function": ("1",),
            },
        ),
        (
            UnconnectedGenericPowerOutputConnectorPin(
                pin="J2.2",
                symbol="Synthetic:GenericPowerOutputConnector",
                function=None,
                electrical_type="power_out",
            ),
            "connector.unconnected_power_output",
            {
                "symbol": ("Synthetic:GenericPowerOutputConnector",),
                "pin_electrical_type": ("power_out",),
                "J2.2": (),
            },
        ),
    ],
)
def test_connector_pin_candidates_retain_source_and_preserve_wire_fields(
    source: (
        UnconnectedNamedConnectorPin
        | UnconnectedGenericPowerInputConnectorPin
        | UnconnectedGenericPowerOutputConnectorPin
    ),
    rule_id: str,
    expected_evidence: dict[str, tuple[str, ...]],
) -> None:
    candidate = UnconnectedConnectorPinCandidate.from_source_evidence(
        source,
        subject="J1.1: synthetic connector contact",
        message="Review the approved connector pinout.",
    )

    assert candidate.source_evidence is source
    assert candidate.rule_id == rule_id
    assert candidate.evidence == expected_evidence
    assert project_unconnected_connector_pin_evidence(source).evidence == expected_evidence


def test_connector_pin_projection_rejects_invalid_roles_and_candidate_drift() -> None:
    invalid_category = UnconnectedNamedConnectorPin(
        pin="J1.1",
        function="VDD",
        category=cast(UnconnectedConnectorPinCategory, "signal"),
    )
    invalid_role_source = UnconnectedNamedConnectorPin(
        pin="J1.2",
        function="GND",
        category="return",
        role_source=cast(UnconnectedConnectorPinRoleSource, "inferred"),
    )
    invalid_power_type = UnconnectedGenericPowerInputConnectorPin(
        pin="J2.1",
        symbol="Synthetic:GenericPowerInputConnector",
        function="1",
        electrical_type=cast(Literal["power_in"], "power_out"),
    )

    with pytest.raises(ValueError, match="supply or return category"):
        project_unconnected_connector_pin_evidence(invalid_category)
    with pytest.raises(ValueError, match="unsupported role source"):
        project_unconnected_connector_pin_evidence(invalid_role_source)
    with pytest.raises(ValueError, match="power_in role"):
        project_unconnected_connector_pin_evidence(invalid_power_type)

    valid_source = UnconnectedNamedConnectorPin(pin="J1.1", function="VDD", category="supply")
    with pytest.raises(ValueError, match="rule must match"):
        UnconnectedConnectorPinCandidate(
            rule_id="connector.unconnected_return_pin",
            subject="J1.1: VDD",
            message="Review the open pin.",
            evidence={"J1.1": ()},
            source_evidence=valid_source,
        )
