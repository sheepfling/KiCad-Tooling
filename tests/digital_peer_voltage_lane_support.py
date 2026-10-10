"""Shared synthetic hosted digital-peer fixture-lane execution."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from kicad_tooling.ci_hosted import HostedLog, digital_peer_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence, NetlistContract
from tests.design_lint_fixtures.component_peer_power import component_peer_power_netlist
from tests.design_lint_fixtures.digital_peer_serial import (
    serial_label_reference_netlist,
    serial_peer_netlist,
)
from tests.design_lint_fixtures.digital_peer_spi import (
    participant_netlist,
    peer_netlist,
    translator_peer_netlist,
)
from tests.serial_peer_reference_support import serial_connector_reference_netlist


@pytest.fixture(scope="session")
def digital_peer_fixture_results(tmp_path_factory):
    project_root = tmp_path_factory.mktemp("digital-peer-voltage-lane")
    image = (
        "fixture.invalid/kicad@sha256:"
        + "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    )
    config = SimpleNamespace(image=image, kicad_version="10.0.0")

    def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert root == project_root
        assert timeout == 600
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert image in argv
        script = argv[-1]
        assert 'test "$actual" = "10.0.0"' in script
        assert "kicad-cli sch erc --format json --severity-all" in script
        assert (
            "peer-control peer-fault peer-translator-control serial-control serial-fault serial-reference-fault serial-connector-control serial-connector-fault serial-label-control serial-label-fault component-peer-control component-peer-fault"
            in script
        )
        mounts = tuple((argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v"))
        fixture_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
        output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
        fixtures = Path(fixture_mount.removesuffix(":/fixtures:ro"))
        output = Path(output_mount.removesuffix(":/output:rw"))
        assert {item.name for item in fixtures.iterdir()} == {
            "multi-device.kicad_sch",
            "peer-control.kicad_sch",
            "peer-fault.kicad_sch",
            "peer-translator-control.kicad_sch",
            "serial-control.kicad_sch",
            "serial-fault.kicad_sch",
            "serial-reference-fault.kicad_sch",
            "serial-connector-control.kicad_sch",
            "serial-connector-fault.kicad_sch",
            "serial-label-control.kicad_sch",
            "serial-label-fault.kicad_sch",
            "component-peer-control.kicad_sch",
            "component-peer-fault.kicad_sch",
        }
        for case in (
            "multi-device",
            "peer-control",
            "peer-fault",
            "peer-translator-control",
            "serial-control",
            "serial-fault",
            "serial-reference-fault",
            "serial-connector-control",
            "serial-connector-fault",
            "serial-label-control",
            "serial-label-fault",
            "component-peer-control",
            "component-peer-fault",
        ):
            for run in ("first", "repeat"):
                (output / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} export {run}\n", encoding="utf-8"
                )
                if case.startswith("component-peer-"):
                    (output / f"{case}.{run}.erc.json").write_text(
                        json.dumps({"kicad_version": "10.0.0", "sheets": []}), encoding="utf-8"
                    )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-10-01T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    def fake_read_netlist(path: Path) -> NetlistContract:
        if path.name.startswith("peer-translator-control"):
            return translator_peer_netlist()
        if path.name.startswith("component-peer-control"):
            return component_peer_power_netlist(split_domains=False)
        if path.name.startswith("component-peer-fault"):
            return component_peer_power_netlist(split_domains=True)
        if path.name.startswith("peer-control"):
            return peer_netlist(split_supplies=False)
        if path.name.startswith("peer-fault"):
            return peer_netlist(split_supplies=True)
        if path.name.startswith("serial-control"):
            return serial_peer_netlist(split_supplies=False)
        if path.name.startswith("serial-fault"):
            return serial_peer_netlist(split_supplies=True)
        if path.name.startswith("serial-reference-fault"):
            return serial_peer_netlist(split_supplies=False, split_references=True)
        if path.name.startswith("serial-connector-control"):
            return serial_connector_reference_netlist(
                output_reference_net="GND_A", input_reference_net="GND_A"
            )
        if path.name.startswith("serial-connector-fault"):
            return serial_connector_reference_netlist()
        if path.name.startswith("serial-label-control"):
            return serial_label_reference_netlist(split_references=False)
        if path.name.startswith("serial-label-fault"):
            return serial_label_reference_netlist(split_references=True)
        return participant_netlist()

    log = HostedLog(project_root, "digital-peer-voltage")
    with (
        patch("kicad_tooling.hwrepo.electrical.selected_config", return_value=config),
        patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_run_command),
        patch("kicad_tooling.validate.read_netlist", side_effect=fake_read_netlist),
    ):
        digital_peer_fixture_lane(project_root, project="synthetic-project", image=image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith(
            ("spi-participant-fixture/", "component-peer-power-fixture/")
        )
    }
    return results
