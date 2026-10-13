"""Keep USB path contract models in their interface owner."""

from __future__ import annotations

import ast
import json

import pytest

from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo import (
    usb_data_path_component_models,
    usb_data_path_models,
    usb_reference_pin_models,
    usb_superspeed_reference_models,
)
from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

USB_DATA_PATH_MODEL_NAMES = (
    "UsbDataSeriesResistorRequirement",
    "UsbDataPathLineRequirement",
    "UsbDataInterfaceRequirement",
    "UsbDataPathMap",
)
USB_DATA_PATH_OWNER_ONLY_MODEL_NAMES = ("UsbDataPathInlineComponentRequirement",)
USB_DATA_PATH_COMPONENT_MODEL_NAMES = (
    "UsbDataPathInlinePinRequirement",
    "UsbDataPathProtectionShuntDataPinRequirement",
    "UsbDataPathProtectionShuntRequirement",
)


def test_usb_data_path_models_have_a_bounded_theme_owner_and_compat_exports() -> None:
    owner = HWREPO / "usb_data_path_models.py"
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    definitions = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert set(USB_DATA_PATH_MODEL_NAMES + USB_DATA_PATH_OWNER_ONLY_MODEL_NAMES) <= definitions

    for name in USB_DATA_PATH_MODEL_NAMES:
        model = getattr(usb_data_path_models, name)
        assert getattr(shared_models, name) is model
        assert model.__module__ == "kicad_tooling.hwrepo.usb_data_path_models"

    for name in USB_DATA_PATH_OWNER_ONLY_MODEL_NAMES:
        model = getattr(usb_data_path_models, name)
        assert model.__module__ == "kicad_tooling.hwrepo.usb_data_path_models"
        assert not hasattr(shared_models, name)


def test_usb_component_pin_maps_live_in_their_theme_owner() -> None:
    owner = HWREPO / "usb_data_path_component_models.py"
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    definitions = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert set(USB_DATA_PATH_COMPONENT_MODEL_NAMES) <= definitions

    for name in USB_DATA_PATH_COMPONENT_MODEL_NAMES:
        model = getattr(usb_data_path_component_models, name)
        assert model.__module__ == "kicad_tooling.hwrepo.usb_data_path_component_models"
        assert not hasattr(shared_models, name)
    assert usb_data_path_models.UsbDataPathInlinePinRequirement is (
        usb_data_path_component_models.UsbDataPathInlinePinRequirement
    )


def test_usb_reference_pin_model_has_a_bounded_owner_and_compat_exports() -> None:
    owner = HWREPO / "usb_reference_pin_models.py"
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    definitions = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert "UsbReferencePinRequirement" in definitions

    model = usb_reference_pin_models.UsbReferencePinRequirement
    assert model.__module__ == "kicad_tooling.hwrepo.usb_reference_pin_models"
    assert usb_data_path_models.UsbReferencePinRequirement is model
    assert shared_models.UsbReferencePinRequirement is model


def test_usb_superspeed_reference_models_have_a_bounded_interface_owner() -> None:
    owner = HWREPO / "usb_superspeed_reference_models.py"
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    definitions = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert "UsbSuperspeedReferencePathRequirement" in definitions

    model = usb_superspeed_reference_models.UsbSuperspeedReferencePathRequirement
    assert model.__module__ == "kicad_tooling.hwrepo.usb_superspeed_reference_models"
    assert usb_data_path_models.UsbSuperspeedReferencePathRequirement is model
    assert not hasattr(shared_models, "UsbSuperspeedReferencePathRequirement")


def test_internal_services_import_usb_path_models_from_the_owner() -> None:
    legacy_imports: list[str] = []
    component_model_imports: list[str] = []
    reference_pin_imports: list[str] = []
    superspeed_model_imports: list[str] = []
    for path in sorted((REPO_ROOT / "kicad_tooling").rglob("*.py")):
        if path == HWREPO / "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if (
                node.module == "models"
                and node.level == 1
                or node.module == "kicad_tooling.hwrepo.models"
            ):
                imported = {item.name for item in node.names} & set(USB_DATA_PATH_MODEL_NAMES)
                legacy_imports.extend(f"{path.name}: {name}" for name in sorted(imported))
            if node.module in {"usb_data_path_models", "kicad_tooling.hwrepo.usb_data_path_models"}:
                imported = {item.name for item in node.names} & set(
                    USB_DATA_PATH_COMPONENT_MODEL_NAMES
                )
                if imported and path != HWREPO / "usb_data_path_models.py":
                    component_model_imports.extend(
                        f"{path.name}: {name}" for name in sorted(imported)
                    )
                imported_names = {item.name for item in node.names}
                if "UsbReferencePinRequirement" in imported_names and path not in {
                    HWREPO / "usb_data_path_models.py",
                    HWREPO / "models.py",
                }:
                    reference_pin_imports.append(path.name)
                if (
                    "UsbSuperspeedReferencePathRequirement" in imported_names
                    and path != HWREPO / "usb_data_path_models.py"
                ):
                    superspeed_model_imports.append(path.name)

    assert not legacy_imports, (
        "Internal services must import USB path models from usb_data_path_models; "
        f"legacy imports: {legacy_imports}"
    )
    assert not component_model_imports, (
        "Internal services must import exact component pin models from "
        "usb_data_path_component_models; "
        f"legacy imports: {component_model_imports}"
    )
    assert not reference_pin_imports, (
        "Internal services must import USB reference-pin requirements from "
        "usb_reference_pin_models; "
        f"legacy imports: {reference_pin_imports}"
    )
    assert not superspeed_model_imports, (
        "Internal services must import SuperSpeed reference requirements from "
        "usb_superspeed_reference_models; "
        f"legacy imports: {superspeed_model_imports}"
    )


def test_inline_component_check_has_a_bounded_interface_owner() -> None:
    owner = HWREPO / "usb_data_path_inline_components.py"
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "check_usb_inline_component" in functions
    assert "design_lint.py" not in owner.read_text(encoding="utf-8")

    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(
        item for item in catalog["rules"] if item["rule_id"] == "bus.usb_data_path_mismatch"
    )
    assert (
        "kicad_tooling/hwrepo/usb_data_path_inline_components.py#check_usb_inline_component"
        in rule["implementation_refs"]
    )


def test_protection_shunt_checks_have_bounded_theme_owners() -> None:
    modules = (
        ("usb_data_path_component_checks.py", "check_usb_component_pin_map"),
        ("usb_data_path_protection_shunts.py", "protection_shunt_mismatches"),
    )
    for filename, function_name in modules:
        owner = HWREPO / filename
        assert line_count(owner) < IMPLEMENTATION_MAX_LINES
        tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
        functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert function_name in functions

    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(
        item for item in catalog["rules"] if item["rule_id"] == "bus.usb_data_path_mismatch"
    )
    assert (
        "kicad_tooling/hwrepo/usb_data_path_protection_shunts.py#protection_shunt_mismatches"
        in rule["implementation_refs"]
    )
    assert (
        "kicad_tooling/hwrepo/usb_superspeed_reference_contract.py#usb_superspeed_reference_mismatches"
        in rule["implementation_refs"]
    )


def test_superspeed_reference_contract_has_a_bounded_owner_and_catalog_reference() -> None:
    owner = HWREPO / "usb_superspeed_reference_contract.py"
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "usb_superspeed_reference_mismatches" in functions

    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(
        item for item in catalog["rules"] if item["rule_id"] == "bus.usb_data_path_mismatch"
    )
    assert (
        "kicad_tooling/hwrepo/usb_superspeed_reference_contract.py#usb_superspeed_reference_mismatches"
        in rule["implementation_refs"]
    )
