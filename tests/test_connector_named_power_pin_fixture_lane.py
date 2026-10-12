"""Focused synthetic command-lane tests for named connector power-pin fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import CommandEvidence, DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures.connector_power_cases import named_connector_power_pin_cases
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
    pytest.mark.return_path_lint,
]


def test_lane_exports_only_named_pin_faults_and_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_connector_named_power_pin_lane import (
        connector_named_power_pin_fixture_lane,
    )
    from kicad_tooling.ci_hosted_connector_named_power_pins import (
        NAMED_CONNECTOR_POWER_PIN_CASES,
    )

    version = "10.0.0"
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    project_root, _ = synthetic_design_lint_project(
        tmp_path, DesignLintPolicy(), kicad_version=version, image=image
    )
    config = SimpleNamespace(image=image, kicad_version=version)
    observed = named_connector_power_pin_cases()

    def fake_run_command(
        command_root: Path, argv: tuple[str, ...], timeout: int
    ) -> CommandEvidence:
        assert command_root == project_root
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
            f"{case}.kicad_sch" for case in NAMED_CONNECTOR_POWER_PIN_CASES
        }
        for case in NAMED_CONNECTOR_POWER_PIN_CASES:
            for run in ("first", "repeat"):
                (output_directory / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} {run}\n", encoding="utf-8"
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-10-12T00:00:00+00:00",
            returncode=0,
            stdout=f"kicad_version={version}\n",
        )

    def fake_read_netlist(path: Path) -> NetlistContract:
        return observed[path.name.split(".", 1)[0]]

    monkeypatch.setattr("kicad_tooling.hwrepo.electrical.selected_config", lambda *_: config)
    monkeypatch.setattr("kicad_tooling.hwrepo.contract_coach.run_command", fake_run_command)
    monkeypatch.setattr("kicad_tooling.validate.read_netlist", fake_read_netlist)

    log = HostedLog(project_root, "named-connector-power-pin-unit")
    connector_named_power_pin_fixture_lane(project_root, project="controller", image=image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    prefix = "connector-named-power-pin-fixture/"
    results = {
        event["stage"]: event for event in events if event.get("stage", "").startswith(prefix)
    }

    assert set(results) == {
        f"{prefix}native-export",
        *(f"{prefix}{case}" for case in NAMED_CONNECTOR_POWER_PIN_CASES),
    }
    assert results[f"{prefix}unconnected-named-supply-fault"]["findings"] == (
        "connector.unconnected_supply_pin"
    )
    assert results[f"{prefix}unconnected-named-return-fault"]["findings"] == (
        "connector.unconnected_return_pin"
    )
    assert results[f"{prefix}unconnected-named-power-control"]["findings"] == "none"
    assert_native_fixture_mounts(project_root, results[f"{prefix}native-export"]["command_receipt"])
