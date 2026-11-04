"""Guard shared candidate evidence projection ownership."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_types import CandidateEvidenceProjection
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]

_THEME_OWNERS = (
    "design_lint_can_termination_candidate_evidence.py",
    "design_lint_i2c_pullup_candidate_evidence.py",
    "design_lint_i2c_address_candidate_evidence.py",
    "design_lint_usb_data_path_candidate_evidence.py",
)


def test_source_projection_container_has_one_shared_owner() -> None:
    shared_owner = HWREPO / "design_lint_types.py"

    assert CandidateEvidenceProjection.__module__ == "kicad_tooling.hwrepo.design_lint_types"
    assert line_count(shared_owner) < IMPLEMENTATION_MAX_LINES
    for filename in _THEME_OWNERS:
        tree = ast.parse((HWREPO / filename).read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "design_lint_types"
            and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
            for node in tree.body
        ), filename
        assert not any(
            isinstance(node, ast.ClassDef) and node.name.endswith("EvidenceProjection")
            for node in tree.body
        ), filename


def test_candidate_evidence_projection_copies_and_freezes_its_fields() -> None:
    source = {"signal": ("SDA",)}
    projection = CandidateEvidenceProjection(
        rule_id="bus.i2c_missing_pullup",
        evidence=source,
    )
    source["signal"] = ("OTHER",)

    assert projection.evidence == {"signal": ("SDA",)}
    with pytest.raises(TypeError):
        projection.evidence["signal"] = ("OTHER",)  # type: ignore[index]
