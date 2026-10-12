"""Keep USB-C contract and shared analysis states in bounded model owners."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import analysis_state_models, usb_c_models
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

ANALYSIS_STATE_MODEL_NAMES = ("AnalysisPending", "AnalysisNotApplicable")
USB_C_MODEL_NAMES = (
    "UsbCcResistorAttachment",
    "UsbCcControllerAttachment",
    "UsbCcAttachment",
    "UsbCcLineRequirement",
    "UsbCControllerRequirement",
    "UsbCNetPinAssignment",
    "UsbCVbusPathElement",
    "UsbCVbusPathRequirement",
    "UsbCProtectionComponentRequirement",
    "UsbCProtectionAnalysis",
    "UsbCVbusCapacitorRequirement",
    "UsbCVbusCapacitanceRequirement",
    "UsbCPortRequirement",
    "UsbCAnalysis",
)


def test_analysis_states_and_usb_c_models_have_bounded_owners_and_compat_exports() -> None:
    owners = (
        ("analysis_state_models.py", analysis_state_models, ANALYSIS_STATE_MODEL_NAMES),
        ("usb_c_models.py", usb_c_models, USB_C_MODEL_NAMES),
    )
    for filename, owner_module, model_names in owners:
        owner = HWREPO / filename
        assert line_count(owner) < IMPLEMENTATION_MAX_LINES
        tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
        definitions = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        assignments = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        assert set(model_names) <= definitions | assignments

        for name in model_names:
            model = getattr(owner_module, name)
            assert getattr(shared_models, name) is model
            if name != "UsbCcAttachment":
                assert (
                    model.__module__
                    == f"kicad_tooling.hwrepo.{owner_module.__name__.rsplit('.', 1)[-1]}"
                )


def test_internal_services_and_regressions_import_models_from_their_owners() -> None:
    model_names = set(ANALYSIS_STATE_MODEL_NAMES) | set(USB_C_MODEL_NAMES)
    legacy_imports: list[str] = []
    for scope in (REPO_ROOT / "kicad_tooling", REPO_ROOT / "tests"):
        for path in sorted(scope.rglob("*.py")):
            if path == HWREPO / "models.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.module is None:
                    continue
                is_compat_registry = (
                    node.level == 1 and node.module == "models"
                ) or node.module.endswith("hwrepo.models")
                if is_compat_registry:
                    imported = {item.name for item in node.names} & model_names
                    legacy_imports.extend(
                        f"{path.relative_to(REPO_ROOT)}: {name}" for name in sorted(imported)
                    )

    assert not legacy_imports, (
        "Internal services and regressions must import USB-C and analysis-state models "
        f"from their owners; compatibility imports: {legacy_imports}"
    )
