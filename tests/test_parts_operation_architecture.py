"""Keep CLI and MCP purchasing preparation on one typed application operation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo import parts_workflow
from kicad_tooling.hwrepo.models import PurchasingReport
from kicad_tooling.hwrepo.parts_operation_models import PartsPreparationRequest

pytestmark = pytest.mark.architecture

REPOSITORY_ROOT = Path(__file__).parents[1]
PACKAGE = REPOSITORY_ROOT / "kicad_tooling"


def test_parts_preparation_request_is_strict_and_domain_owned() -> None:
    path = PACKAGE / "hwrepo/parts_operation_models.py"
    assert len(path.read_text(encoding="utf-8").splitlines()) < 500
    assert set(PartsPreparationRequest.model_fields) == {
        "project_id",
        "output",
        "native_summary",
        "requested_preferences",
        "boards",
        "spare_percent",
        "spare_minimum",
        "cli",
        "runner_mode",
    }
    with pytest.raises(ValidationError):
        PartsPreparationRequest(
            project_id="controller",
            output=Path("build/parts/review"),
            opaque_options={"output": "outside"},
        )
    for values in (
        {"boards": 0},
        {"spare_percent": 101},
        {"spare_minimum": -1},
    ):
        with pytest.raises(ValidationError):
            PartsPreparationRequest(
                project_id="controller",
                output=Path("build/parts/review"),
                **values,
            )


def test_typed_operation_maps_to_the_shared_planner_and_retains_one_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path.resolve()
    output = root / "build/parts/review"
    native_summary = root / "build/native/controller/summary.json"
    preferences = root / "projects/controller/docs/purchasing.json"
    request = PartsPreparationRequest(
        project_id="controller",
        output=output,
        native_summary=native_summary,
        requested_preferences=preferences,
        boards=5,
        spare_percent=10,
        spare_minimum=2,
        runner_mode="local",
        cli="kicad-cli",
    )
    selected_runner = object()
    prepare_calls: list[tuple[object, ...]] = []
    saved: list[tuple[Path, PurchasingReport]] = []
    report = PurchasingReport(
        project_id="controller",
        status="BLOCKED",
        receipt_dir=str(output),
        issues=("synthetic architecture seam",),
    )

    monkeypatch.setattr(
        parts_workflow, "_selected_netlist_runner", lambda _request: selected_runner
    )
    monkeypatch.setattr(
        parts_workflow, "prepare", lambda *args: (prepare_calls.append(args), report)[1]
    )
    monkeypatch.setattr(
        parts_workflow, "save_report", lambda path, value: saved.append((path, value))
    )

    result = parts_workflow.prepare_request(root, request)

    assert result is report
    assert prepare_calls == [
        (
            root,
            "controller",
            output,
            selected_runner,
            native_summary,
            preferences,
            5,
            10,
            2,
        )
    ]
    assert saved == [(output, report)]


@pytest.mark.parametrize("relative_path", ("parts.py", "hwrepo/mcp_parts.py"))
def test_cli_and_mcp_use_the_shared_typed_operation(relative_path: str) -> None:
    source = (PACKAGE / relative_path).read_text(encoding="utf-8")

    assert "PartsPreparationRequest" in source
    assert "prepare_request" in source
    assert "parts_workflow.prepare(" not in source
