"""Keep protocol and peer-interface lint boundaries theme-scoped."""

from __future__ import annotations

import ast
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.hwrepo import (
    component_peer_pin_models,
    connector_part_id_peer_models,
    connector_peer_pin_models,
    digital_peer_voltage_models,
    i2c_peer_reference_models,
    i2c_pullup_voltage_models,
    serial_peer_reference_models,
    usb_peer_reference_models,
    usb_peer_unsupported_models,
)
from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import (
    FACADE_MAX_LINES,
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]

INTERFACE_COVERAGE_MODEL_OWNERS = MappingProxyType(
    {
        "component_peer_pin_models.py": ("ComponentPeerPinRuleCoverage",),
        "connector_peer_pin_models.py": ("ConnectorPeerPinHeuristicCoverage",),
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

USB_PEER_ANALYSIS_MODULES = (
    "usb_peer_reference_types.py",
    "usb_peer_endpoint_analysis.py",
    "usb_peer_data_crossing.py",
    "usb_peer_path_analysis.py",
    "usb_peer_inline_path_analysis.py",
    "usb_peer_protection_shunt_analysis.py",
    "usb_peer_reference_contract.py",
    "usb_peer_reference_decision.py",
    "usb_peer_reference_evidence.py",
    "usb_peer_reference_scan.py",
    "usb_peer_unsupported_topology.py",
)


SERIAL_PEER_ANALYSIS_MODULES = (
    "serial_peer_reference_types.py",
    "serial_peer_reference_domains.py",
    "serial_peer_reference_mapping.py",
    "serial_peer_reference_scan.py",
)


CONTROL_INPUT_MODULES = (
    "control_input_inventory.py",
    "control_input_checks.py",
    "control_input_bias.py",
)


DIGITAL_PEER_VOLTAGE_MODULES = (
    "digital_peer_voltage_types.py",
    "digital_peer_voltage_analysis.py",
    "digital_peer_voltage_scan.py",
)


def test_connector_pin_analysis_facade_stays_small() -> None:
    facade = HWREPO / "connector_pins.py"

    assert _line_count(facade) < FACADE_MAX_LINES


def test_i3c_named_rail_rule_stays_in_a_focused_protocol_module() -> None:
    module = HWREPO / "i3c_signal_named_rail.py"

    assert _line_count(module) < IMPLEMENTATION_MAX_LINES


def test_interface_coverage_models_live_in_theme_owners() -> None:
    owners = {
        "component_peer_pin_models.py": component_peer_pin_models,
        "connector_peer_pin_models.py": connector_peer_pin_models,
        "connector_part_id_peer_models.py": connector_part_id_peer_models,
        "digital_peer_voltage_models.py": digital_peer_voltage_models,
        "serial_peer_reference_models.py": serial_peer_reference_models,
        "usb_peer_reference_models.py": usb_peer_reference_models,
    }
    registry = HWREPO / "models.py"
    registry_tree = ast.parse(registry.read_text(encoding="utf-8"), filename=registry.name)
    registry_definitions = {
        node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)
    }

    for filename, model_names in INTERFACE_COVERAGE_MODEL_OWNERS.items():
        owner = HWREPO / filename
        assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
        owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
        owner_definitions = {
            node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)
        }
        assert set(model_names) <= owner_definitions
        assert not (set(model_names) & registry_definitions)
        owner_module = owners[filename]
        for name in model_names:
            assert getattr(shared_models, name) is getattr(owner_module, name)


def test_i2c_peer_reference_coverage_models_stay_in_their_theme_owner() -> None:
    owner = HWREPO / "i2c_peer_reference_models.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    owner_definitions = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}

    assert I2C_PEER_REFERENCE_MODELS <= owner_definitions
    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert all(not hasattr(shared_models, name) for name in I2C_PEER_REFERENCE_MODELS)
    assert i2c_peer_reference_models.I2cPeerReferenceCoverageReport.__module__.endswith(
        "i2c_peer_reference_models"
    )


def test_i2c_pullup_voltage_coverage_model_stays_in_its_theme_owner() -> None:
    owner = HWREPO / "i2c_pullup_voltage_models.py"
    model_service = HWREPO / "i2c_pullup_models.py"
    coverage_service = HWREPO / "i2c_pullup_voltage_coverage.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    owner_definitions = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}
    expected_import = "I2cPullupVoltageCoverageEntry"

    def imports_from_owner(path: Path) -> bool:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        return any(
            isinstance(node, ast.ImportFrom)
            and node.module == "i2c_pullup_voltage_models"
            and any(alias.name == expected_import for alias in node.names)
            for node in tree.body
        )

    assert "I2cPullupVoltageCoverageEntry" in owner_definitions
    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert not hasattr(shared_models, "I2cPullupVoltageCoverageEntry")
    assert imports_from_owner(model_service)
    assert imports_from_owner(coverage_service)
    assert _line_count(coverage_service) < IMPLEMENTATION_MAX_LINES
    assert i2c_pullup_voltage_models.I2cPullupVoltageCoverageEntry.__module__.endswith(
        "i2c_pullup_voltage_models"
    )


def test_usb_inline_component_coverage_model_stays_in_its_theme_owner() -> None:
    owner = HWREPO / "usb_peer_reference_models.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    owner_definitions = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}

    assert "UsbPeerDataInlineComponentCoverage" in owner_definitions
    assert not hasattr(shared_models, "UsbPeerDataInlineComponentCoverage")
    assert "UsbPeerDataProtectionShuntCoverage" in owner_definitions
    assert "UsbPeerDataProtectionShuntPinCoverage" in owner_definitions
    assert not hasattr(shared_models, "UsbPeerDataProtectionShuntCoverage")
    assert not hasattr(shared_models, "UsbPeerDataProtectionShuntPinCoverage")


def test_usb_unsupported_path_coverage_model_stays_in_its_theme_owner() -> None:
    owner = HWREPO / "usb_peer_unsupported_models.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    owner_definitions = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}

    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert "UsbPeerUnsupportedMultiPinPathCoverage" in owner_definitions
    assert not hasattr(shared_models, "UsbPeerUnsupportedMultiPinPathCoverage")
    assert usb_peer_unsupported_models.UsbPeerUnsupportedMultiPinPathCoverage.__module__.endswith(
        "usb_peer_unsupported_models"
    )


def test_bus_heuristics_compatibility_facade_stays_small() -> None:
    facade = HWREPO / "bus_heuristics.py"

    assert _line_count(facade) < FACADE_MAX_LINES


def test_resistor_array_evidence_is_shared_by_control_and_i2c_checks() -> None:
    helper = HWREPO / "resistor_array_paths.py"
    consumers = (
        "control_input_checks.py",
        "i2c_pullup_contract.py",
        "i2c_pullup_voltage_coverage.py",
    )

    assert _line_count(helper) < IMPLEMENTATION_MAX_LINES
    for name in consumers:
        tree = ast.parse((HWREPO / name).read_text(encoding="utf-8"), filename=name)
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "resistor_array_paths"
            and any(alias.name == "ResistorArrayNetlistEvidence" for alias in node.names)
            for node in tree.body
        ), f"{name} must reuse the shared resistor-array evidence service"


def test_can_tx_rx_same_net_rule_uses_a_focused_predicate_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == "bus.can_tx_rx_same_net")
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/can_tx_rx_same_net.py#can_tx_rx_same_net_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs


def test_rs485_data_same_net_rule_uses_a_focused_predicate_owner() -> None:
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.rs485_data_input_output_same_net"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/rs485_same_net.py#rs485_data_input_output_same_net_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/rs485_data_functions.py#rs485_data_pin_role"
        in rule.implementation_refs
    )


def test_rs485_named_rail_rule_uses_a_focused_predicate_owner() -> None:
    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "bus.rs485_signal_on_named_rail"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/rs485_signal_named_rail.py#rs485_signal_on_named_rail_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/rs485_data_functions.py#explicit_rs485_transceiver_identity"
        in rule.implementation_refs
    )


def test_spi_data_same_net_rule_uses_a_focused_predicate_owner() -> None:
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.spi_data_input_output_same_net"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/spi_same_net.py#spi_data_input_output_same_net_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/spi_participants.py#spi_data_function_role_and_channel"
        in rule.implementation_refs
    )


def test_spi_clock_control_data_same_net_rule_uses_a_focused_predicate_owner() -> None:
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.spi_clock_control_data_same_net"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/spi_clock_data_same_net.py#spi_clock_control_data_same_net_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/spi_participants.py#spi_signal_role_and_channel"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/spi_role_assignments.py#spi_role_assignment_groups"
        in rule.implementation_refs
    )


def test_spi_clock_chip_select_same_net_rule_uses_a_focused_predicate_owner() -> None:
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.spi_clock_chip_select_same_net"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/spi_control_same_net.py#spi_clock_chip_select_same_net_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/spi_role_assignments.py#spi_role_assignment_groups"
        in rule.implementation_refs
    )


def test_usb_peer_reference_review_stays_split_by_responsibility() -> None:
    facade = HWREPO / "usb_peer_reference_review.py"
    modules = [HWREPO / name for name in USB_PEER_ANALYSIS_MODULES]

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all(path.is_file() for path in modules)
    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        "Keep USB endpoint, path, map, and scan logic in reviewable modules below 500 lines; "
        f"oversized modules: {oversized}"
    )


def test_usb_peer_reference_rule_refs_point_to_the_owning_modules() -> None:
    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "bus.usb_peer_reference_review"
    )
    references = {
        item.split("#", maxsplit=1)[0].rsplit("/", maxsplit=1)[-1]
        for item in rule.implementation_refs
    }

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/usb_peer_reference_decision.py#usb_peer_reference_disposition"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/usb_peer_inline_path_analysis.py#mapped_inline_usb_data_link"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/usb_peer_protection_shunt_analysis.py#mapped_protection_shunt_usb_data_link"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/bus_signal_pairs.py#usb_superspeed_function_identity"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/usb_peer_endpoint_analysis.py#usb_superspeed_endpoints"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/usb_peer_reference_evidence.py"
        "#usb_reference_net_component_observations"
    ) in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/usb_peer_path_analysis.py#usb_superspeed_direct_data_link"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/usb_peer_unsupported_topology.py#unsupported_usb_multi_pin_path_candidates"
        in rule.implementation_refs
    )
    assert references <= {
        *USB_PEER_ANALYSIS_MODULES,
        "bus_signal_pairs.py",
        "peer_reference_assignments.py",
        "design_lint_candidate_aggregation.py",
    }


def test_serial_peer_reference_review_stays_split_by_responsibility() -> None:
    facade = HWREPO / "serial_peer_reference_review.py"
    modules = [HWREPO / name for name in SERIAL_PEER_ANALYSIS_MODULES]

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all(path.is_file() for path in modules)
    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        "Keep serial reference-domain, map, and scan logic in reviewable modules below 500 lines; "
        f"oversized modules: {oversized}"
    )


def test_serial_peer_reference_rule_refs_point_to_the_owning_modules() -> None:
    catalog = HWREPO / "design-lint-rules.json"

    assert "kicad_tooling/hwrepo/serial_peer_reference_review.py#" not in catalog.read_text(
        encoding="utf-8"
    )


def test_control_input_analysis_stays_split_by_responsibility() -> None:
    facade = HWREPO / "control_inputs.py"
    modules = [HWREPO / name for name in CONTROL_INPUT_MODULES]

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all(path.is_file() for path in modules)
    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        f"Keep control inventory, checks, and contract coverage in reviewable modules: {oversized}"
    )


def test_digital_peer_voltage_review_stays_split_by_responsibility() -> None:
    facade = HWREPO / "digital_peer_voltage_review.py"
    modules = [HWREPO / name for name in DIGITAL_PEER_VOLTAGE_MODULES]

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all(path.is_file() for path in modules)
    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, f"Keep digital peer review modules below 500 lines: {oversized}"
