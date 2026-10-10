"""Keep USB path contract models in their interface owner."""

from __future__ import annotations

import ast
import json

import pytest

from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo import usb_data_path_models
from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

USB_DATA_PATH_MODEL_NAMES = (
    "UsbDataSeriesResistorRequirement",
    "UsbDataPathLineRequirement",
    "UsbReferencePinRequirement",
    "UsbDataInterfaceRequirement",
    "UsbDataPathMap",
)
USB_DATA_PATH_OWNER_ONLY_MODEL_NAMES = (
    "UsbDataPathInlinePinRequirement",
    "UsbDataPathInlineComponentRequirement",
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


def test_internal_services_import_usb_path_models_from_the_owner() -> None:
    legacy_imports: list[str] = []
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

    assert not legacy_imports, (
        "Internal services must import USB path models from usb_data_path_models; "
        f"legacy imports: {legacy_imports}"
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
