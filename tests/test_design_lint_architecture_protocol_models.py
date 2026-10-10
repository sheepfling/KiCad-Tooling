"""Keep protocol requirements in their theme-owned model modules."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    can_termination_models,
    digital_peer_voltage_models,
    i2c_address_models,
    i2c_pullup_models,
    model_primitives,
    reference_bond_models,
    rs485_models,
    serial_logic_models,
    serial_peer_models,
    spi_models,
)
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES
from tests.lint_architecture_support import line_count as _line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

PROTOCOL_MODEL_OWNERS = {
    "can_termination_models.py": (
        can_termination_models,
        (
            "CanTerminationResistorRequirement",
            "CanTerminationMidpointCapacitorRequirement",
            "CanTerminationEndpointRequirement",
            "CanTerminationBusRequirement",
            "CanTerminationAnalysis",
        ),
    ),
    "i2c_address_models.py": (
        i2c_address_models,
        (
            "I2cAddressBitRequirement",
            "I2cResponderAddressRequirement",
            "I2cAddressSegmentRequirement",
            "I2cAddressMap",
            "I2cAddressBitEvidence",
            "I2cResponderAddressCoverageEntry",
            "I2cAddressCoverageReport",
        ),
    ),
    "i2c_pullup_models.py": (
        i2c_pullup_models,
        (
            "I2cPullupArrayChannelRequirement",
            "I2cPullupArrayRequirement",
            "I2cPullupInputVoltageLimit",
            "I2cPullupVoltageCompatibilityRequirement",
            "I2cPullupElectricalWindow",
            "I2cPullupLineRequirement",
            "I2cPullupSeriesResistorRequirement",
            "I2cPullupSeriesPathRequirement",
            "I2cPullupBusRequirement",
            "I2cPullupAnalysis",
            "I2cPullupHeuristicEntry",
            "I2cPullupHeuristicCoverage",
        ),
    ),
    "spi_models.py": (
        spi_models,
        (
            "SpiPinNetRequirement",
            "SpiPinUnconnectedRequirement",
            "SpiMisoConnectedRequirement",
            "SpiPinNotPresent",
            "SpiControllerRequirement",
            "SpiDeviceRequirement",
            "SpiBridgePathRequirement",
            "SpiBridgeRequirement",
            "SpiBusRequirement",
            "SpiAnalysis",
        ),
    ),
    "serial_logic_models.py": (
        serial_logic_models,
        (
            "SerialPinNetRequirement",
            "SerialLogicOutputLimits",
            "SerialLogicInputLimits",
            "SerialLogicLimits",
            "SerialLabelFixtureExpectedNets",
        ),
    ),
    "serial_peer_models.py": (
        serial_peer_models,
        (
            "SerialEndpointRequirement",
            "SerialBridgePathRequirement",
            "SerialBridgeRequirement",
            "SerialDirectPeerRequirement",
            "SerialShiftedPeerRequirement",
            "SerialExternalPeerRequirement",
            "SerialPeerLinkRequirement",
            "SerialPeerAnalysis",
        ),
    ),
    "rs485_models.py": (
        rs485_models,
        (
            "Rs485EndpointPinRequirement",
            "Rs485EndpointRequirement",
            "Rs485TerminationResistorRequirement",
            "Rs485DnpResistorRequirement",
            "Rs485TerminationEndpointRequirement",
            "Rs485BiasResistorRequirement",
            "Rs485LocalBiasRequirement",
            "Rs485RemoteBiasRequirement",
            "Rs485InternalFailSafeRequirement",
            "Rs485NoBiasRequirement",
            "Rs485SignalPairRequirement",
            "Rs485BusRequirement",
            "Rs485Analysis",
        ),
    ),
    "reference_bond_models.py": (
        reference_bond_models,
        ("ReferenceBondRequirement",),
    ),
    "digital_peer_voltage_models.py": (
        digital_peer_voltage_models,
        (
            "DigitalLogicOutputLimits",
            "DigitalLogicInputLimits",
            "DigitalPeerPinRequirement",
            "DigitalPeerVoltageLink",
            "DigitalPeerVoltageAnalysis",
        ),
    ),
}

PROTOCOL_MODEL_TYPE_ALIASES = {
    "spi_models.py": (spi_models, ("SpiMisoRequirement",)),
    "serial_peer_models.py": (serial_peer_models, ("SerialPeerRequirement",)),
    "rs485_models.py": (rs485_models, ("Rs485BiasRequirement",)),
}


def test_protocol_models_live_in_theme_owners_and_services_import_them_directly() -> None:
    model_names = {name for _, names in PROTOCOL_MODEL_OWNERS.values() for name in names}
    model_names.update(name for _, names in PROTOCOL_MODEL_TYPE_ALIASES.values() for name in names)
    registry = HWREPO / "models.py"
    registry_tree = ast.parse(registry.read_text(encoding="utf-8"), filename=registry.name)
    registry_definitions = {
        node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)
    }
    legacy_imports: list[str] = []

    for filename, (owner_module, names) in PROTOCOL_MODEL_OWNERS.items():
        owner = HWREPO / filename
        assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
        owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=filename)
        owner_definitions = {
            node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)
        }
        assert set(names) <= owner_definitions
        assert not (set(names) & registry_definitions)
        for name in names:
            assert getattr(shared_models, name) is getattr(owner_module, name)

    for filename, (owner_module, names) in PROTOCOL_MODEL_TYPE_ALIASES.items():
        assert _line_count(HWREPO / filename) < IMPLEMENTATION_MAX_LINES
        for name in names:
            assert getattr(shared_models, name) is getattr(owner_module, name)

    for source in sorted(HWREPO.parent.rglob("*.py")):
        if source.name == "models.py":
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=source.name)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (node.module == "models" or node.module.endswith(".models"))
            ):
                legacy_imports.extend(
                    f"{source.name}:{alias.name}"
                    for alias in node.names
                    if alias.name in model_names
                )

    assert not legacy_imports, (
        f"Protocol services should import their theme-owned models: {legacy_imports}"
    )
    assert shared_models.ElectricalPositive is model_primitives.ElectricalPositive
    assert shared_models.FiniteMeasure is model_primitives.FiniteMeasure
    assert shared_models.NonNegativeMeasure is model_primitives.NonNegativeMeasure
