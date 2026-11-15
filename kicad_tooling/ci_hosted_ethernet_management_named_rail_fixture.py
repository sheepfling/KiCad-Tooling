"""Source-bound native fixture expectation for Ethernet management rail lint."""

from __future__ import annotations

from .ci_hosted_ethernet_label_models import (
    EthernetLabelCaseExpectation,
    EthernetLabelFixtureExpectation,
    EthernetLabelPinExpectation,
)

ETHERNET_MANAGEMENT_NAMED_RAIL_FIXTURE = EthernetLabelFixtureExpectation(
    directory="ethernet-management-named-rail",
    rule_id="bus.ethernet_management_signal_on_named_rail",
    stage_prefix="ethernet-management-named-rail-fixture",
    control=EthernetLabelCaseExpectation(
        source_sha256="a45a5f2054c52cf6a972fd59712944d7ac3a952c4452f2c1d30648a4c6e316ba",
        subjects=(),
        pins=(
            EthernetLabelPinExpectation(reference="J2.1", function="MDC", net="ETH_MDC"),
            EthernetLabelPinExpectation(reference="J2.2", function="MDIO", net="ETH_MDIO"),
            EthernetLabelPinExpectation(reference="U1.5", function="MDC", net="ETH_MDC"),
            EthernetLabelPinExpectation(reference="U1.6", function="MDIO", net="ETH_MDIO"),
        ),
    ),
    fault=EthernetLabelCaseExpectation(
        source_sha256="648fdd77ba46a330a313a7f4929c8a8f89fde89382ba449b47fa17037f6fdbd9",
        subjects=(
            "J2.1: MDC on return-like net GND",
            "U1.5: MDC on return-like net GND",
        ),
        pins=(
            EthernetLabelPinExpectation(reference="J2.1", function="MDC", net="GND"),
            EthernetLabelPinExpectation(reference="J2.2", function="MDIO", net="ETH_MDIO"),
            EthernetLabelPinExpectation(reference="U1.5", function="MDC", net="GND"),
            EthernetLabelPinExpectation(reference="U1.6", function="MDIO", net="ETH_MDIO"),
        ),
    ),
)
