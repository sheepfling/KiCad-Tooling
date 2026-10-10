"""Keep protocol and peer-interface lint boundaries theme-scoped."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    component_peer_pin_models,
    connector_peer_pin_models,
    design_lint_peer_candidates,
    digital_peer_voltage_models,
    digital_peer_voltage_types,
    serial_peer_reference_models,
    usb_peer_reference_models,
)
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import (
    FACADE_MAX_LINES,
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = pytest.mark.design_lint

INTERFACE_COVERAGE_MODEL_OWNERS = {
    "component_peer_pin_models.py": ("ComponentPeerPinRuleCoverage",),
    "connector_peer_pin_models.py": (
        "ConnectorPartIdPeerPinCoverage",
        "ConnectorPeerPinHeuristicCoverage",
    ),
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

BUS_ANALYSIS_MODULES = (
    "bus_signal_roles.py",
    "bus_signal_pairs.py",
    "resistor_paths.py",
    "i2c_pullup_contract_paths.py",
    "i2c_pullup_contract.py",
    "i2c_pullup_heuristics.py",
    "can_termination_contract.py",
    "can_termination_heuristics.py",
    "can_peer_heuristics.py",
    "usb_c_vbus.py",
    "usb_c_contract.py",
    "spi_bias_heuristics.py",
    "spi_contract.py",
)


USB_PEER_ANALYSIS_MODULES = (
    "usb_peer_reference_types.py",
    "usb_peer_endpoint_analysis.py",
    "usb_peer_path_analysis.py",
    "usb_peer_reference_contract.py",
    "usb_peer_reference_scan.py",
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


def test_interface_coverage_models_live_in_theme_owners() -> None:
    owners = {
        "component_peer_pin_models.py": component_peer_pin_models,
        "connector_peer_pin_models.py": connector_peer_pin_models,
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


def test_internal_interface_coverage_services_import_theme_owners() -> None:
    expected_by_service = {
        "connector_peer_pin_coverage.py": {
            "connector_peer_pin_models": {
                "ConnectorPartIdPeerPinCoverage",
                "ConnectorPeerPinHeuristicCoverage",
            }
        },
        "design_lint_peer_coverage.py": {
            "component_peer_pin_models": {"ComponentPeerPinRuleCoverage"},
            "digital_peer_voltage_models": {"DigitalPeerVoltageRuleCoverage"},
            "serial_peer_reference_models": {
                "SerialPeerReferenceCoverageReport",
                "SerialPeerReferenceLinkCoverageEntry",
            },
            "usb_peer_reference_models": set(
                INTERFACE_COVERAGE_MODEL_OWNERS["usb_peer_reference_models.py"]
            ),
        },
        "design_lint_evaluation_types.py": {
            "component_peer_pin_models": {"ComponentPeerPinRuleCoverage"},
            "connector_peer_pin_models": {
                "ConnectorPeerPinHeuristicCoverage",
            },
            "digital_peer_voltage_models": {"DigitalPeerVoltageRuleCoverage"},
            "serial_peer_reference_models": {"SerialPeerReferenceCoverageReport"},
            "usb_peer_reference_models": {"UsbPeerReferenceCoverageReport"},
        },
        "design_lint_peer_evaluation.py": {
            "digital_peer_voltage_models": {"DigitalPeerVoltageRuleCoverage"},
            "serial_peer_reference_models": {"SerialPeerReferenceCoverageReport"},
            "usb_peer_reference_models": {"UsbPeerReferenceCoverageReport"},
        },
    }
    model_names = {name for names in INTERFACE_COVERAGE_MODEL_OWNERS.values() for name in names}
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


def test_bus_heuristics_compatibility_facade_stays_small() -> None:
    facade = HWREPO / "bus_heuristics.py"

    assert _line_count(facade) < FACADE_MAX_LINES


def test_bus_protocol_implementation_modules_stay_below_review_limit() -> None:
    modules = [HWREPO / name for name in BUS_ANALYSIS_MODULES]
    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        "Split bus-protocol modules at the 500-line review threshold; "
        f"oversized modules: {oversized}"
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
    catalog = HWREPO / "design-lint-rules.json"

    assert "kicad_tooling/hwrepo/usb_peer_reference_review.py#" not in catalog.read_text(
        encoding="utf-8"
    )


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


@pytest.mark.interface_lint
def test_peer_candidate_coordinator_delegates_by_protocol() -> None:
    facade = HWREPO / "design_lint_peer_candidates.py"
    modules = (
        "design_lint_serial_peer_candidates.py",
        "design_lint_usb_peer_candidates.py",
        "design_lint_spi_peer_candidates.py",
        "design_lint_digital_peer_voltage_candidates.py",
        "design_lint_usb_c_candidates.py",
    )

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all((HWREPO / name).is_file() for name in modules)

    tree = ast.parse(facade.read_text(encoding="utf-8"), filename=facade.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    candidate_constructions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
    ]

    assert {
        "serial_unmapped_peer_candidates",
        "serial_reference_candidates",
        "usb_peer_reference_candidates",
        "spi_participant_candidates",
        "digital_peer_voltage_candidates",
        "usb_c_port_candidates",
    } <= calls
    assert not candidate_constructions, "Peer dispatch should not construct lint findings."
    assert (
        design_lint_peer_candidates.DigitalPeerVoltageLintContext
        is digital_peer_voltage_types.DigitalPeerVoltageLintContext
    )


@pytest.mark.interface_lint
def test_bus_candidate_coordinator_delegates_by_theme_in_stable_order() -> None:
    facade = HWREPO / "design_lint_bus_candidates.py"
    modules = (
        "design_lint_i2c_candidates.py",
        "design_lint_spi_candidates.py",
        "design_lint_unconnected_interface_candidates.py",
        "design_lint_can_candidates.py",
        "design_lint_signal_pair_candidates.py",
    )

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all((HWREPO / name).is_file() for name in modules)

    tree = ast.parse(facade.read_text(encoding="utf-8"), filename=facade.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bus_candidates"
    )
    calls = sorted(
        (
            node.lineno,
            node.func.id,
        )
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )
    candidate_constructions = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
    ]

    assert [name for _, name in calls] == [
        "i2c_pullup_candidates",
        "spi_bias_candidates",
        "unconnected_interface_candidates",
        "can_candidates",
        "complementary_signal_candidates",
        "named_differential_pair_candidates",
        "i2c_address_candidates",
        "i2c_responder_coverage_candidates",
    ]
    assert not candidate_constructions, "Bus dispatch should not construct lint findings."


def test_control_and_digital_peer_rule_refs_point_to_their_owners() -> None:
    catalog = HWREPO / "design-lint-rules.json"
    text = catalog.read_text(encoding="utf-8")

    assert "kicad_tooling/hwrepo/control_inputs.py#" not in text
    assert "kicad_tooling/hwrepo/control_input_inventory.py#unconnected_control_inputs" in text
    assert (
        "kicad_tooling/hwrepo/control_input_bias.py#control_input_bias_heuristic_coverage" in text
    )
    assert "kicad_tooling/hwrepo/digital_peer_voltage_review.py#" not in text
    assert (
        "kicad_tooling/hwrepo/digital_peer_voltage_scan.py#unmapped_spi_peer_voltage_reviews"
        in text
    )
    assert (
        "kicad_tooling/hwrepo/digital_peer_voltage_scan.py#unmapped_serial_peer_voltage_reviews"
        in text
    )
