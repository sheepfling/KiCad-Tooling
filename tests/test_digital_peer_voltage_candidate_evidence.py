"""Digital-peer voltage candidates preserve native and authored scan evidence."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

import pytest

from kicad_tooling.hwrepo.design_lint_digital_peer_voltage_candidate_evidence import (
    DigitalPeerVoltageCandidate,
    DigitalPeerVoltageFindingEvidence,
    project_digital_peer_voltage_evidence,
)
from kicad_tooling.hwrepo.digital_peer_voltage_types import (
    DigitalPeerLink,
    DigitalPeerVoltageLintContext,
    DigitalPeerVoltageReview,
    VoltageNamedRail,
)


def _source(interface: Literal["SPI", "serial"]) -> DigitalPeerVoltageFindingEvidence:
    output_role = "clock" if interface == "SPI" else "tx"
    input_role = "clock" if interface == "SPI" else "rx"
    output_function = "SCK" if interface == "SPI" else "TX"
    input_function = "SCK" if interface == "SPI" else "RX"
    link = DigitalPeerLink(
        interface=interface,
        output_role=output_role,
        output_reference="U1",
        output_pin="U1.1",
        output_function=output_function,
        output_type="output",
        input_reference="U2",
        input_role=input_role,
        input_pin="U2.1",
        input_function=input_function,
        input_type="input",
        net=f"{interface}_SIGNAL",
    )
    peer = DigitalPeerVoltageReview(
        interface=interface,
        output_reference="U1",
        input_reference="U2",
        output_rail=VoltageNamedRail(net="VDD", voltage_v=Decimal("3.300")),
        input_rail=VoltageNamedRail(net="VCC", voltage_v=Decimal("1.8")),
        links=(link,),
    )
    scope = DigitalPeerVoltageLintContext(
        state="required",
        source_path="electrical/digital-peer-voltage.toml",
        source_sha256="a" * 64,
    )
    return DigitalPeerVoltageFindingEvidence(peer=peer, scope=scope)


@pytest.mark.parametrize(
    ("interface", "rule_id", "assignment_key"),
    [
        pytest.param("SPI", "bus.spi_peer_voltage_review", "shared_SPI_pin_assignments", id="spi"),
        pytest.param(
            "serial",
            "bus.serial_peer_voltage_review",
            "shared_serial_pin_assignments",
            id="serial",
        ),
    ],
)
def test_digital_peer_voltage_projection_retains_typed_sources_and_wire_fields(
    interface: Literal["SPI", "serial"],
    rule_id: str,
    assignment_key: str,
) -> None:
    source = _source(interface)
    projection = project_digital_peer_voltage_evidence(source)
    candidate = DigitalPeerVoltageCandidate.from_source_evidence(
        source,
        subject=f"U1 -> U2: {interface} voltage review",
        message="Review device limits.",
    )
    output_function = "SCK" if interface == "SPI" else "TX"
    input_function = "SCK" if interface == "SPI" else "RX"
    expected_link = (
        f"{interface}_SIGNAL: U1.1 ({output_function}, output) -> U2.1 ({input_function}, input)"
    )

    assert projection.rule_id == rule_id
    assert dict(projection.evidence) == {
        "output_component": ("U1",),
        "input_component": ("U2",),
        "output_supply_net": ("VDD",),
        "output_supply_label_value": ("3.3 V",),
        "input_supply_net": ("VCC",),
        "input_supply_label_value": ("1.8 V",),
        assignment_key: (expected_link,),
        "authored_voltage_map_state": ("required",),
        "electrical_contract_path": ("electrical/digital-peer-voltage.toml",),
        "electrical_contract_sha256": ("a" * 64,),
    }
    assert candidate.source_evidence is source
    assert candidate.rule_id == rule_id
    assert candidate.evidence == projection.evidence


def test_digital_peer_voltage_candidate_rejects_projection_mismatch() -> None:
    source = _source("SPI")
    projection = project_digital_peer_voltage_evidence(source)

    with pytest.raises(ValueError, match="typed source projection"):
        DigitalPeerVoltageCandidate(
            rule_id=projection.rule_id,
            subject="review",
            message="inspect",
            evidence={"authored_voltage_map_state": ("pending",)},
            source_evidence=source,
        )


@pytest.mark.parametrize("interface", ["SPI", "serial"])
def test_unconfigured_voltage_map_keeps_only_its_explicit_state(
    interface: Literal["SPI", "serial"],
) -> None:
    source = _source(interface)
    unconfigured = DigitalPeerVoltageFindingEvidence(
        peer=source.peer,
        scope=DigitalPeerVoltageLintContext(state="not_configured"),
    )

    evidence = project_digital_peer_voltage_evidence(unconfigured).evidence

    assert evidence["authored_voltage_map_state"] == ("not_configured",)
    assert "electrical_contract_path" not in evidence
    assert "electrical_contract_sha256" not in evidence
