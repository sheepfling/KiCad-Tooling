"""Synthetic runner for portable connector-return hosted-lane regressions."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted import HostedLog, connector_return_lint_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence, NetlistContract
from tests.connector_return_fixture_support import connector_return_fixture_contracts


@pytest.fixture
def connector_return_fixture_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SimpleNamespace:
    """Run the isolated fake-native lane and return its report events by stage."""
    root = tmp_path
    image = "fixture.invalid/kicad@sha256:" + "a" * 64
    config = SimpleNamespace(image=image, kicad_version="10.0.0")
    observed = connector_return_fixture_contracts()

    def fake_run_command(
        command_root: Path, argv: tuple[str, ...], timeout: int
    ) -> CommandEvidence:
        assert command_root == root.resolve()
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
            f"{case}.kicad_sch" for case in observed
        }
        for case in observed:
            for run in ("first", "repeat"):
                (output_directory / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} netlist with export timestamp {run}\n",
                    encoding="utf-8",
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-09-29T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    def fake_read_netlist(path: Path) -> NetlistContract:
        return observed[path.name.split(".", 1)[0]]

    monkeypatch.setattr("kicad_tooling.hwrepo.electrical.selected_config", lambda *_args: config)
    monkeypatch.setattr("kicad_tooling.hwrepo.contract_coach.run_command", fake_run_command)
    monkeypatch.setattr("kicad_tooling.validate.read_netlist", fake_read_netlist)
    log = HostedLog(root, "connector-return")
    connector_return_lint_fixture_lane(
        root,
        project="synthetic-project",
        image=image,
        log=log,
    )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("connector-return-fixture/")
    }
    return SimpleNamespace(root=root, version=config.kicad_version, cases=observed, results=results)
