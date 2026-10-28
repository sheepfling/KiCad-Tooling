"""Typed, immutable expectations for Ethernet label native fixtures."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .hwrepo.design_lint_rule_types import DesignLintRuleId
from .hwrepo.model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    RepositoryPath,
    StrictModel,
)

EthernetLabelFeature = Literal[
    "data", "management", "named_rail", "management_named_rail", "management_unconnected"
]


class EthernetLabelPinExpectation(StrictModel):
    """Native identity and expected network assignment of one pin."""

    reference: Reference
    function: NonEmptyText
    net: NetName | None


class EthernetLabelCaseExpectation(StrictModel):
    """Digest-pinned pin inventory expected for a control or fault source."""

    source_sha256: Digest
    pins: Annotated[tuple[EthernetLabelPinExpectation, ...], Field(min_length=1)]
    subjects: tuple[NonEmptyText, ...]

    @model_validator(mode="after")
    def pin_references_are_unique(self) -> EthernetLabelCaseExpectation:
        references = tuple(pin.reference.casefold() for pin in self.pins)
        if len(set(references)) != len(references):
            raise ValueError("Ethernet fixture pin references must be unique")
        return self


class EthernetLabelFixtureExpectation(StrictModel):
    """Complete immutable control/fault contract for one Ethernet lint feature."""

    directory: RepositoryPath
    rule_id: DesignLintRuleId
    stage_prefix: Identifier
    control: EthernetLabelCaseExpectation
    fault: EthernetLabelCaseExpectation
    complete_data_pairs: bool = False

    @field_validator("directory")
    @classmethod
    def directory_is_portable(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            "\\" in value
            or path.is_absolute()
            or path.as_posix() != value
            or any(part in {"", ".", ".."} for part in value.split("/"))
        ):
            raise ValueError("Ethernet fixture directory must be a portable relative path")
        return value

    @model_validator(mode="after")
    def control_and_fault_pin_inventories_match(self) -> EthernetLabelFixtureExpectation:
        control = {pin.reference.casefold(): pin.function.casefold() for pin in self.control.pins}
        fault = {pin.reference.casefold(): pin.function.casefold() for pin in self.fault.pins}
        if control != fault:
            raise ValueError("Ethernet control and fault pin inventories must match")
        return self


ETHERNET_LABEL_FIXTURES: Mapping[EthernetLabelFeature, EthernetLabelFixtureExpectation] = (
    MappingProxyType(
        {
            "data": EthernetLabelFixtureExpectation(
                directory="ethernet-data-label-native",
                rule_id="bus.ethernet_data_label_mismatch",
                stage_prefix="ethernet-label-fixture",
                control=EthernetLabelCaseExpectation(
                    source_sha256="9fae1afdb0395354f6e61eae17623f5d940b2f90bf82d452ff8339bfed1e421e",
                    subjects=(),
                    pins=(
                        EthernetLabelPinExpectation(
                            reference="U1.1", function="TDP", net="ETH_TX_P"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.2", function="TDN", net="ETH_TX_N"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.3", function="RDP", net="ETH_RX_P"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.4", function="RDN", net="ETH_RX_N"
                        ),
                    ),
                ),
                fault=EthernetLabelCaseExpectation(
                    source_sha256="8b42bc11362cedc71519b7ffb2477da399c52374efcf44bcb69d35149f9a1b92",
                    subjects=(
                        "U1.1: TDP on ETH_RX_P",
                        "U1.2: TDN on ETH_RX_N",
                        "U1.3: RDP on ETH_TX_P",
                        "U1.4: RDN on ETH_TX_N",
                    ),
                    pins=(
                        EthernetLabelPinExpectation(
                            reference="U1.1", function="TDP", net="ETH_RX_P"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.2", function="TDN", net="ETH_RX_N"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.3", function="RDP", net="ETH_TX_P"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.4", function="RDN", net="ETH_TX_N"
                        ),
                    ),
                ),
                complete_data_pairs=True,
            ),
            "management": EthernetLabelFixtureExpectation(
                directory="ethernet-management-label-native",
                rule_id="bus.ethernet_management_label_mismatch",
                stage_prefix="ethernet-management-label-fixture",
                control=EthernetLabelCaseExpectation(
                    source_sha256="3ddd8d2919eade8a6bb8f7a8c059dafbe9b348aacbb5a6bb8398b0c62944d31b",
                    subjects=(),
                    pins=(
                        EthernetLabelPinExpectation(
                            reference="U1.5", function="MDC", net="ETH_MDC"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.6", function="MDIO", net="ETH_MDIO"
                        ),
                    ),
                ),
                fault=EthernetLabelCaseExpectation(
                    source_sha256="f63b39e17d68c36202e323534f2ea58b63247a2e55b0188bc048056d26cf1495",
                    subjects=("U1.5: MDC on ETH_MDIO", "U1.6: MDIO on ETH_MDC"),
                    pins=(
                        EthernetLabelPinExpectation(
                            reference="U1.5", function="MDC", net="ETH_MDIO"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.6", function="MDIO", net="ETH_MDC"
                        ),
                    ),
                ),
            ),
            "management_named_rail": EthernetLabelFixtureExpectation(
                directory="ethernet-management-named-rail",
                rule_id="bus.ethernet_management_signal_on_named_rail",
                stage_prefix="ethernet-management-named-rail-fixture",
                control=EthernetLabelCaseExpectation(
                    source_sha256="3ddd8d2919eade8a6bb8f7a8c059dafbe9b348aacbb5a6bb8398b0c62944d31b",
                    subjects=(),
                    pins=(
                        EthernetLabelPinExpectation(
                            reference="U1.5", function="MDC", net="ETH_MDC"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.6", function="MDIO", net="ETH_MDIO"
                        ),
                    ),
                ),
                fault=EthernetLabelCaseExpectation(
                    source_sha256="6ab770da2bd563b08152d89a12f10f1eb872550233815e3f1b398c4e290fc86a",
                    subjects=("U1.5: MDC on return-like net GND",),
                    pins=(
                        EthernetLabelPinExpectation(reference="U1.5", function="MDC", net="GND"),
                        EthernetLabelPinExpectation(
                            reference="U1.6", function="MDIO", net="ETH_MDIO"
                        ),
                    ),
                ),
            ),
            "management_unconnected": EthernetLabelFixtureExpectation(
                directory="ethernet-management-unconnected-native",
                rule_id="bus.ethernet_management_unconnected_pin",
                stage_prefix="ethernet-management-unconnected-fixture",
                control=EthernetLabelCaseExpectation(
                    source_sha256="c3c259a0ce8d0b4be736be63bb106096657b4c596985557460351a88a0e326d6",
                    subjects=(),
                    pins=(
                        EthernetLabelPinExpectation(
                            reference="U1.5", function="MDC", net="ETH_MDC"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.6", function="MDIO", net="ETH_MDIO"
                        ),
                    ),
                ),
                fault=EthernetLabelCaseExpectation(
                    source_sha256="d2324d82038d896ed81727d7934c80e0549e7605c369adabd5c5f2ca81604988",
                    subjects=("U1.5: MDC is open while MDIO U1.6 is assigned to ETH_MDIO",),
                    pins=(
                        EthernetLabelPinExpectation(reference="U1.5", function="MDC", net=None),
                        EthernetLabelPinExpectation(
                            reference="U1.6", function="MDIO", net="ETH_MDIO"
                        ),
                    ),
                ),
            ),
            "named_rail": EthernetLabelFixtureExpectation(
                directory="ethernet-signal-named-rail",
                rule_id="bus.ethernet_signal_on_named_rail",
                stage_prefix="ethernet-signal-named-rail-fixture",
                control=EthernetLabelCaseExpectation(
                    source_sha256="b8460f781f7f3ef341b375656ae487ed926cd3a3824098180c5b7460fe61fecd",
                    subjects=(),
                    pins=(
                        EthernetLabelPinExpectation(
                            reference="U1.1", function="TDP", net="ETH_TX_P"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.2", function="TDN", net="ETH_TX_N"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.3", function="RDP", net="ETH_RX_P"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.4", function="RDN", net="ETH_RX_N"
                        ),
                    ),
                ),
                fault=EthernetLabelCaseExpectation(
                    source_sha256="1db5c1e1efa99eaf09df7f9a853fe37f4c621afb56481ccc7f909fa0d96c3531",
                    subjects=("U1.1: TDP on return-like net GND",),
                    pins=(
                        EthernetLabelPinExpectation(reference="U1.1", function="TDP", net="GND"),
                        EthernetLabelPinExpectation(
                            reference="U1.2", function="TDN", net="ETH_TX_N"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.3", function="RDP", net="ETH_RX_P"
                        ),
                        EthernetLabelPinExpectation(
                            reference="U1.4", function="RDN", net="ETH_RX_N"
                        ),
                    ),
                ),
            ),
        }
    )
)
