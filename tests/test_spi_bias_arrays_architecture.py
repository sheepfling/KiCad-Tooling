"""Keep the SPI bias-array contract and evidence service theme-owned."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo import spi_bias_array_paths, spi_models
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def test_spi_array_models_remain_in_the_spi_theme_owner() -> None:
    owner = HWREPO / "spi_models.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    definitions = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}

    assert {"SpiBiasArrayChannelRequirement", "SpiBiasResistorArrayRequirement"} <= definitions
    assert spi_models.SpiBiasArrayChannelRequirement.__module__.endswith("spi_models")
    assert spi_models.SpiBiasResistorArrayRequirement.__module__.endswith("spi_models")
    assert not hasattr(shared_models, "SpiBiasArrayChannelRequirement")
    assert not hasattr(shared_models, "SpiBiasResistorArrayRequirement")


def test_native_array_evidence_has_one_shared_spi_owner() -> None:
    helper = HWREPO / "spi_bias_array_paths.py"
    assert line_count(helper) < IMPLEMENTATION_MAX_LINES
    assert spi_bias_array_paths.SpiBiasArrayChannelEvidence.__module__.endswith(
        "spi_bias_array_paths"
    )

    expected_imports = {
        "spi_contract.py": {"spi_bias_array_checks"},
        "spi_bias_heuristics.py": {"spi_bias_array_channel_evidence"},
    }
    for filename, expected_names in expected_imports.items():
        tree = ast.parse((HWREPO / filename).read_text(encoding="utf-8"), filename=filename)
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "spi_bias_array_paths"
            and expected_names <= {alias.name for alias in node.names}
            for node in tree.body
        ), f"{filename} must reuse the shared SPI array evidence service"
