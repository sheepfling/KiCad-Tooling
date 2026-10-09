"""Synthetic orchestration checks for pinned connector-inventory netlist exports."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kicad_tooling.ci_hosted import HostedLog, connector_inventory_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence, NetlistContract


def test_pinned_export_detects_nonstandard_reference_and_keeps_test_point_control(
    tmp_path: Path,
) -> None:
    root = tmp_path
    image = "fixture.invalid/kicad@sha256:" + "b" * 64
    config = SimpleNamespace(image=image, kicad_version="10.0.0")
    observed = {
        "fault": NetlistContract(
            components={},
            nets={},
            component_symbols={
                "U7": "Connector_Generic:Conn_01x02",
                "U8": "Connector:TestPoint_Alt",
            },
        ),
        "control": NetlistContract(
            components={},
            nets={},
            component_symbols={"U8": "Connector:TestPoint_Alt"},
        ),
    }

    def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert root == tmp_path.resolve()
        assert timeout == 600
        assert "--network" in argv
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert argv[argv.index("--entrypoint") + 1] == "/bin/sh"
        assert argv[argv.index("--platform") + 1] == "linux/amd64"
        assert image in argv
        script = argv[-1]
        assert 'test "$actual" = "10.0.0"' in script
        assert "kicad-cli sch export netlist" in script

        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        assert len(mounts) == 2
        source_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
        output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
        source_directory = Path(source_mount.removesuffix(":/fixtures:ro"))
        output_directory = Path(output_mount.removesuffix(":/output:rw"))
        assert {item.name for item in source_directory.iterdir()} == {
            "fault.kicad_sch",
            "control.kicad_sch",
        }
        for case in ("fault", "control"):
            for run in ("first", "repeat"):
                (output_directory / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} netlist export {run}\n",
                    encoding="utf-8",
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-09-30T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    def fake_read_netlist(path: Path) -> NetlistContract:
        case = path.name.split(".", 1)[0]
        return observed[case]

    log = HostedLog(root, "connector-inventory")
    with (
        patch("kicad_tooling.hwrepo.electrical.selected_config", return_value=config),
        patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_run_command),
        patch("kicad_tooling.validate.read_netlist", side_effect=fake_read_netlist),
    ):
        connector_inventory_fixture_lane(
            root,
            project="synthetic-project",
            image=image,
            log=log,
        )

    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("connector-inventory-fixture/")
    }
    fault = results["connector-inventory-fixture/fault"]
    control = results["connector-inventory-fixture/control"]
    assert fault["status"] == "PASS"
    assert fault["coverage_status"] == "UNDECLARED"
    assert fault["candidate_references"] == "U7"
    assert control["status"] == "PASS"
    assert control["coverage_status"] == "COMPLETE"
    assert control["candidate_references"] == "none"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]
    assert (root / fault["command_receipt"]).is_file()
    export = results["connector-inventory-fixture/native-export"]
    assert export["status"] == "PASS"
    assert export["kicad_version"] == "10.0.0"
