"""Electrical-analysis inputs are typed and rechecked around simulation."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.electrical import bound_inputs, load_analysis, selected_config
from kicad_tooling.hwrepo.electrical_report_models import BoundElectricalInputs
from kicad_tooling.hwrepo.electrical_runner import analyze
from tests.electrical_simulation_support import ISLAND, NA, PROJECT, install_fixture
from tests.support import reference_root

pytestmark = [pytest.mark.template_checkout]


def test_bound_inputs_are_typed_and_rechecked_after_execution(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    shutil.copytree(reference_root(), root)
    contract = install_fixture(root).model_copy(
        update={"power": NA, "high_frequency": NA, "grounding": NA}
    )
    write_model(root / ISLAND / "tests/electrical.json", contract)

    config = selected_config(root, PROJECT)
    assert load_analysis(root, config) is not None
    before = bound_inputs(root, config, contract)
    assert isinstance(before, BoundElectricalInputs)
    roles = {role for entry in before.entries for role in entry.roles}
    assert {
        "design-source",
        "project-manifest",
        "project-checks",
        "electrical-requirements",
    } <= roles

    with patch(
        "kicad_tooling.hwrepo.electrical.bound_inputs",
        side_effect=[before, BoundElectricalInputs(entries=())],
    ):
        report = analyze(root, PROJECT)
    assert report.status == "FAIL"
    assert "changed during" in report.checks[-1].detail
