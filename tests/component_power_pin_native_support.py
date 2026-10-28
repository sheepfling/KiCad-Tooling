"""Shared orchestration assertions for component power-pin fixture lanes."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast

import pytest

from kicad_tooling import ci_hosted_connector_return_context as connector_return_context
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import CommandEvidence, NetlistContract
from tests.json_types import JsonObject
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES


class ComponentPowerPinLane(Protocol):
    """Native fixture lane signature shared by component power-pin checks."""

    def __call__(self, root: Path, *, project: str, image: str, log: HostedLog) -> None: ...


def component_power_pin_lane_results(log: HostedLog, *, stage_prefix: str) -> dict[str, JsonObject]:
    """Select result events emitted by one component power-pin lane."""
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    prefix = f"{stage_prefix}/"
    return {item["stage"]: item for item in events if item.get("stage", "").startswith(prefix)}


def assert_mocked_component_power_pin_lane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    lane: ComponentPowerPinLane,
    cases: tuple[str, ...],
    observed_contracts: Mapping[str, NetlistContract],
    stage_prefix: str,
    fault_case: str,
    expected_rule_id: str,
    expected_subject: str,
    expected_control_status: str = "PASS",
    expected_control_findings: str = "none",
) -> None:
    """Verify one isolated fault/control export through the shared native adapter."""
    root = tmp_path.resolve()
    image = PINNED_NATIVE_KICAD_IMAGES["10.0.0"]
    config = SimpleNamespace(image=image, kicad_version="10.0.0")

    def fake_run_command(
        command_root: Path, argv: tuple[str, ...], timeout: int
    ) -> CommandEvidence:
        assert command_root == root
        assert timeout == 600
        assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert image in argv
        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        assert len(mounts) == 2
        source_directory = Path(
            next(item for item in mounts if item.endswith(":/fixtures:ro")).removesuffix(
                ":/fixtures:ro"
            )
        )
        output_directory = Path(
            next(item for item in mounts if item.endswith(":/output:rw")).removesuffix(
                ":/output:rw"
            )
        )
        assert {item.name for item in source_directory.iterdir()} == {
            f"{case}.kicad_sch" for case in cases
        }
        for case in cases:
            for run in ("first", "repeat"):
                (output_directory / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} {run}\n", encoding="utf-8"
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-10-12T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    def fake_read_netlist(path: Path) -> NetlistContract:
        return observed_contracts[path.name.split(".", 1)[0]]

    monkeypatch.setattr(connector_return_context, "selected_config", lambda *_args: config)
    monkeypatch.setattr(connector_return_context, "run_command", fake_run_command)
    monkeypatch.setattr(connector_return_context, "read_netlist", fake_read_netlist)

    log = HostedLog(root, f"{stage_prefix}-unit")
    lane(root, project="synthetic", image=image, log=log)
    results = component_power_pin_lane_results(log, stage_prefix=stage_prefix)
    expected_stages = {
        f"{stage_prefix}/native-export",
        *(f"{stage_prefix}/{case}" for case in cases),
    }
    assert set(results) == expected_stages

    fault = results[f"{stage_prefix}/{fault_case}"]
    assert fault["lint_status"] == "REVIEW"
    assert expected_rule_id in fault["findings"].split(",")
    assert expected_subject in fault["subjects"].split(";")
    control_case = next(case for case in cases if case != fault_case)
    control = results[f"{stage_prefix}/{control_case}"]
    assert control["lint_status"] == expected_control_status
    assert control["findings"] == expected_control_findings
    assert_native_fixture_mounts(
        root, cast(str, results[f"{stage_prefix}/native-export"]["command_receipt"])
    )
