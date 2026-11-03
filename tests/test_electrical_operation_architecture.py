"""Keep CLI, MCP, verification and release on the typed electrical operation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.electrical_operation_models import ElectricalAnalysisRequest

pytestmark = pytest.mark.architecture

REPOSITORY_ROOT = Path(__file__).parents[1]
PACKAGE = REPOSITORY_ROOT / "kicad_tooling"


def test_electrical_analysis_request_is_strict_and_domain_owned() -> None:
    path = PACKAGE / "hwrepo/electrical_operation_models.py"
    assert len(path.read_text(encoding="utf-8").splitlines()) < 500
    assert set(ElectricalAnalysisRequest.model_fields) == {
        "project_id",
        "output",
        "native_summary",
        "cli",
        "ngspice",
        "runner_mode",
    }
    with pytest.raises(ValidationError):
        ElectricalAnalysisRequest(
            project_id="controller",
            opaque_options={"runner": "container"},
        )


@pytest.mark.parametrize(
    "relative_path",
    (
        "electrical.py",
        "hwrepo/mcp_electrical.py",
        "hwrepo/project_verification.py",
        "hwrepo/releasing.py",
        "hwrepo/electrical_runner.py",
    ),
)
def test_application_routes_use_the_typed_analysis_operation(relative_path: str) -> None:
    source = (PACKAGE / relative_path).read_text(encoding="utf-8")

    assert "ElectricalAnalysisRequest" in source
    assert "analyze_request" in source


def test_mcp_maps_runner_choice_into_the_shared_request() -> None:
    source = (PACKAGE / "hwrepo/mcp_electrical.py").read_text(encoding="utf-8")

    assert "runner_mode=runner" in source
    assert "electrical_runner.analyze(" not in source
