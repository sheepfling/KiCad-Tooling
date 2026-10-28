"""Guard theme ownership for peer coverage adapters and model imports."""

from __future__ import annotations

import ast
from types import MappingProxyType

import pytest

from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]

INTERFACE_COVERAGE_MODEL_OWNERS = MappingProxyType(
    {
        "component_peer_pin_models.py": ("ComponentPeerPinRuleCoverage",),
        "connector_peer_pin_models.py": (
            "ConnectorFootprintPeerPinCoverage",
            "ConnectorPeerPinHeuristicCoverage",
        ),
        "connector_part_id_peer_models.py": ("ConnectorPartIdPeerPinCoverage",),
        "digital_peer_voltage_models.py": ("DigitalPeerVoltageRuleCoverage",),
        "serial_peer_reference_models.py": (
            "SerialPeerReferenceLinkCoverageEntry",
            "SerialPeerReferenceCoverageReport",
        ),
        "usb_peer_reference_models.py": (
            "UsbPeerEndpointGroupCoverage",
            "UsbPeerReferencePinCoverage",
            "UsbPeerDataShuntBranchCoverage",
            "UsbPeerDataSeriesResistorCoverage",
            "UsbPeerDataLineCoverage",
            "UsbPeerDataPathCoverage",
            "UsbPeerReferencePathCoverageEntry",
            "UsbPeerReferenceCoverageReport",
        ),
    }
)
I2C_PEER_REFERENCE_MODELS = frozenset(
    {
        "I2cPeerReferenceBusCoverage",
        "I2cPeerReferenceCoverageReport",
    }
)
PEER_COVERAGE_SERVICES = (
    "component_peer_pin_coverage.py",
    "component_power_input_peer_scan.py",
    "digital_peer_voltage_coverage.py",
    "i2c_peer_reference_coverage.py",
    "serial_peer_reference_coverage.py",
    "usb_peer_reference_coverage.py",
    "connector_footprint_peer_coverage.py",
    "connector_part_id_peer_models.py",
)


def test_internal_interface_coverage_services_import_theme_owners() -> None:
    expected_by_service = {
        "connector_peer_pin_coverage.py": {
            "connector_part_id_peer_models": {"ConnectorPartIdPeerPinCoverage"},
            "connector_peer_pin_models": {"ConnectorPeerPinHeuristicCoverage"},
        },
        "connector_footprint_peer_coverage.py": {
            "connector_peer_pin_models": {"ConnectorFootprintPeerPinCoverage"},
        },
        "component_peer_pin_coverage.py": {
            "component_peer_pin_models": {"ComponentPeerPinRuleCoverage"},
        },
        "digital_peer_voltage_coverage.py": {
            "digital_peer_voltage_models": {"DigitalPeerVoltageRuleCoverage"},
        },
        "i2c_peer_reference_coverage.py": {
            "i2c_peer_reference_models": I2C_PEER_REFERENCE_MODELS,
        },
        "serial_peer_reference_coverage.py": {
            "serial_peer_reference_models": {
                "SerialPeerReferenceCoverageReport",
                "SerialPeerReferenceLinkCoverageEntry",
            },
        },
        "usb_peer_reference_coverage.py": {
            "usb_peer_reference_models": set(
                INTERFACE_COVERAGE_MODEL_OWNERS["usb_peer_reference_models.py"]
            ),
            "usb_peer_unsupported_models": {"UsbPeerUnsupportedMultiPinPathCoverage"},
        },
        "usb_peer_reference_models.py": {
            "usb_peer_unsupported_models": {"UsbPeerUnsupportedMultiPinPathCoverage"},
        },
        "design_lint_evaluation_types.py": {
            "component_peer_pin_models": {"ComponentPeerPinRuleCoverage"},
            "connector_peer_pin_models": {
                "ConnectorPeerPinHeuristicCoverage",
            },
            "digital_peer_voltage_models": {"DigitalPeerVoltageRuleCoverage"},
            "serial_peer_reference_models": {"SerialPeerReferenceCoverageReport"},
            "usb_peer_reference_models": {"UsbPeerReferenceCoverageReport"},
            "i2c_peer_reference_models": {"I2cPeerReferenceCoverageReport"},
        },
        "design_lint_peer_evaluation.py": {
            "digital_peer_voltage_models": {"DigitalPeerVoltageRuleCoverage"},
            "serial_peer_reference_models": {"SerialPeerReferenceCoverageReport"},
            "usb_peer_reference_models": {"UsbPeerReferenceCoverageReport"},
            "i2c_peer_reference_models": {"I2cPeerReferenceCoverageReport"},
        },
        "design_lint_report_models.py": {
            "i2c_peer_reference_models": {"I2cPeerReferenceCoverageReport"},
        },
    }
    model_names = (
        {name for names in INTERFACE_COVERAGE_MODEL_OWNERS.values() for name in names}
        | I2C_PEER_REFERENCE_MODELS
        | {"UsbPeerUnsupportedMultiPinPathCoverage"}
    )
    legacy_imports: list[str] = []
    for filename, expected_imports in expected_by_service.items():
        source = HWREPO / filename
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=filename)
        imported_from_owner: dict[str, set[str]] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 1:
                continue
            if node.module == "models":
                legacy_imports.extend(
                    f"{filename}:{alias.name}" for alias in node.names if alias.name in model_names
                )
            elif node.module in expected_imports:
                imported_from_owner[node.module] = {alias.name for alias in node.names}
        for owner, names in expected_imports.items():
            assert names <= imported_from_owner.get(owner, set())

    for source in sorted(HWREPO.glob("*.py")):
        if source.name == "models.py":
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=source.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module == "models":
                legacy_imports.extend(
                    f"{source.name}:{alias.name}"
                    for alias in node.names
                    if alias.name in model_names
                )

    assert not legacy_imports, (
        "Internal peer-pin services should import coverage models from their theme owners; "
        f"legacy imports: {legacy_imports}"
    )


def test_peer_coverage_adapters_stay_in_theme_owned_modules() -> None:
    module_sizes = {name: _line_count(HWREPO / name) for name in PEER_COVERAGE_SERVICES}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert all((HWREPO / name).is_file() for name in PEER_COVERAGE_SERVICES)
    assert not (HWREPO / "design_lint_peer_coverage.py").exists()
    assert not oversized, f"Peer coverage must remain split by theme: {oversized}"
