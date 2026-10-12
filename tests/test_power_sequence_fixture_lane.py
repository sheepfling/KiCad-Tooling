"""Synthetic orchestration checks for the mapped power-sequence lane."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted import HostedLog, power_sequence_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence
from tests.power_sequence_support import (
    power_sequence_netlist,
    power_sequence_output_cycle_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]


@pytest.fixture
def power_sequence_fixture_lane_context(tmp_path: Path) -> SimpleNamespace:
    image = "fixture.invalid/kicad@sha256:" + "c" * 64
    config = SimpleNamespace(image=image, kicad_version="10.0.0")
    return SimpleNamespace(root=tmp_path, image=image, config=config)


def test_native_export_checks_mapped_sequence_faults_and_controls(
    power_sequence_fixture_lane_context: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = power_sequence_fixture_lane_context.root
    image = power_sequence_fixture_lane_context.image
    config = power_sequence_fixture_lane_context.config

    def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert root == power_sequence_fixture_lane_context.root.resolve()
        assert timeout == 600
        assert "--network" in argv
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert image in argv
        script = argv[-1]
        assert 'test "$actual" = "10.0.0"' in script
        assert "kicad-cli sch export netlist" in script
        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        assert len(mounts) == 2
        fixture_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
        output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
        fixtures = Path(fixture_mount.removesuffix(":/fixtures:ro"))
        output = Path(output_mount.removesuffix(":/output:rw"))
        assert {item.name for item in fixtures.iterdir() if item.suffix == ".kicad_sch"} == {
            "control.kicad_sch",
            "open-enable.kicad_sch",
            "output-enable-cycle.kicad_sch",
        }
        for case in ("control", "open-enable", "output-enable-cycle"):
            for run in ("first", "repeat"):
                (output / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} export {run}\n", encoding="utf-8"
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-09-30T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    def fake_read_netlist(path: Path):
        if path.name.startswith("output-enable-cycle"):
            return power_sequence_output_cycle_netlist(cycle=True)
        observed = (
            power_sequence_netlist(fault="open-enable")
            if path.name.startswith("open-enable")
            else power_sequence_netlist()
        )
        nets = dict(observed.nets)
        if path.name.startswith("open-enable"):
            nets["FLOATING_ENABLE"] = nets.pop("FLOATING")
        nets["GOOD_B"] = ("U2.3",)
        return observed.model_copy(update={"nets": nets})

    monkeypatch.setattr("kicad_tooling.hwrepo.electrical.selected_config", lambda *_args: config)
    monkeypatch.setattr("kicad_tooling.hwrepo.contract_coach.run_command", fake_run_command)
    monkeypatch.setattr("kicad_tooling.validate.read_netlist", fake_read_netlist)

    log = HostedLog(root, "power-sequence")
    power_sequence_fixture_lane(root, project="synthetic-project", image=image, log=log)

    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("power-sequence-fixture/")
    }
    control = results["power-sequence-fixture/control"]
    fault = results["power-sequence-fixture/open-enable"]
    native = results["power-sequence-fixture/native-export"]
    assert control["status"] == "PASS"
    assert control["lint_status"] == "PASS"
    assert control["power_sequence_findings"] == "none"
    assert control["observed_enable_net"] == "GOOD_A"
    assert fault["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert fault["power_sequence_findings"] == "power.mapped_sequence_dependency_mismatch"
    assert fault["observed_enable_net"] == "FLOATING_ENABLE"
    cycle = results["power-sequence-fixture/output-enable-cycle"]
    assert cycle["status"] == "PASS"
    assert cycle["lint_status"] == "REVIEW"
    assert cycle["power_sequence_findings"] == "power.mapped_sequence_dependency_mismatch"
    assert cycle["observed_enable_cycle_stages"] == "rail-a,rail-b"
    for case in (control, fault, cycle):
        assert case["repeatable"] == "true"
        assert case["normalized_netlist_sha256"] == case["repeat_normalized_netlist_sha256"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == "10.0.0"
    assert native["repeatability_basis"] == "canonical_native_netlist"
    assert (root / native["command_receipt"]).is_file()


def test_unsupported_native_version_fails_before_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = "fixture.invalid/kicad@sha256:" + "c" * 64
    config = SimpleNamespace(image=image, kicad_version="9.0.0")
    invoked = False

    def unexpected_run_command(*_args: object, **_kwargs: object) -> CommandEvidence:
        nonlocal invoked
        invoked = True
        raise AssertionError("unsupported KiCad version must fail before export")

    monkeypatch.setattr("kicad_tooling.hwrepo.electrical.selected_config", lambda *_args: config)
    monkeypatch.setattr("kicad_tooling.hwrepo.contract_coach.run_command", unexpected_run_command)
    with pytest.raises(ValueError, match="do not cover KiCad 9.0.0"):
        power_sequence_fixture_lane(
            tmp_path,
            project="synthetic-project",
            image=image,
            log=HostedLog(tmp_path, "unsupported-version"),
        )
    assert not invoked
