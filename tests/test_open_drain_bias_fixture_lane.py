"""Orchestration checks for native open-output bias regression fixtures."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from kicad_tooling.ci_hosted import HostedLog, open_drain_bias_fixture_lane
from kicad_tooling.hwrepo.contracts import KiCadErcReport, KiCadErcViolation
from kicad_tooling.hwrepo.models import CommandEvidence, ComponentContract, NetlistContract
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]


def bias_netlist(*, output_type: str, rail: str, dnp: bool) -> NetlistContract:
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic open-output driver", footprint="Synthetic:SOIC"
            ),
            "U2": ComponentContract(value="Synthetic digital input", footprint="Synthetic:SOIC"),
            "R1": ComponentContract(value="10k", footprint="Synthetic:0603"),
        },
        nets={
            "ALERT_N": ("U2.1", "U1.2", "R1.1"),
            rail: ("R1.2",),
        },
        dnp_components=("R1",) if dnp else (),
        component_symbols={
            "U1": "Synthetic:OpenOutputProbe",
            "U2": "Synthetic:OpenOutputProbe",
            "R1": "Device:R",
        },
        pin_functions={
            "U2.1": "OPEN_OUTPUT",
            "U1.2": "INPUT_PEER",
            "U2.2": "INPUT_PEER",
            "R1.1": "~",
            "R1.2": "~",
        },
        pin_electrical_types={
            "U2.1": output_type,
            "U1.2": "input",
            "U2.2": "input",
            "R1.1": "passive",
            "R1.2": "passive",
        },
        component_pin_numbers={
            "U1": ("1", "2"),
            "U2": ("1", "2"),
            "R1": ("1", "2"),
        },
    )


def test_native_lane_checks_both_bias_polarities_and_dnp_faults(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    image = "fixture.invalid/kicad@sha256:" + "a" * 64
    config = SimpleNamespace(image=image, kicad_version="10.0.0")
    observed = {
        "collector-control": bias_netlist(output_type="open_collector", rail="+3V3", dnp=False),
        "collector-fault": bias_netlist(output_type="open_collector", rail="+3V3", dnp=True),
        "emitter-control": bias_netlist(output_type="open_emitter", rail="GND", dnp=False),
        "emitter-fault": bias_netlist(output_type="open_emitter", rail="GND", dnp=True),
    }

    def fake_run_command(root_arg: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert root_arg == root
        assert timeout == 600
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert image in argv
        assert 'test "$actual" = "10.0.0"' in argv[-1]
        assert "collector-control collector-fault" in argv[-1]
        assert "emitter-control emitter-fault" in argv[-1]
        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        assert len(mounts) == 2
        fixture_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
        output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
        fixtures = Path(fixture_mount.removesuffix(":/fixtures:ro"))
        output = Path(output_mount.removesuffix(":/output:rw"))
        assert {item.name for item in fixtures.iterdir()} == {
            f"{case}.kicad_sch" for case in observed
        }
        for case in observed:
            for run in ("first", "repeat"):
                (output / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} netlist {run}\n", encoding="utf-8"
                )
                (output / f"{case}.{run}.erc.json").write_text(
                    '{"kicad_version":"10.0.0","sheets":[{"violations":[]}]}',
                    encoding="utf-8",
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-10-01T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    def fake_read_netlist(path: Path) -> NetlistContract:
        case = path.name.split(".", 1)[0]
        return observed[case]

    log = HostedLog(root, "open-drain-bias")
    with (
        patch("kicad_tooling.hwrepo.electrical.selected_config", return_value=config),
        patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_run_command),
        patch("kicad_tooling.validate.read_netlist", side_effect=fake_read_netlist),
        patch(
            "kicad_tooling.ci_hosted.read_kicad_erc_report",
            return_value=KiCadErcReport(
                kicad_version="10.0.0",
                violations=tuple(
                    KiCadErcViolation(
                        type=warning,
                        severity="warning",
                        description=None,
                        items=(),
                    )
                    for warning in (
                        "footprint_link_issues",
                        "isolated_pin_label",
                        "lib_symbol_issues",
                    )
                ),
            ),
        ),
    ):
        open_drain_bias_fixture_lane(
            root,
            project="synthetic-project",
            image=image,
            log=log,
        )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("open-drain-bias-fixture/")
    }
    assert set(results) == {
        "open-drain-bias-fixture/native-export",
        *(f"open-drain-bias-fixture/{case}" for case in observed),
    }
    for case, result in results.items():
        if case.endswith("native-export"):
            continue
        is_fault = case.endswith("fault")
        is_emitter = "emitter" in case
        expected_finding = (
            (
                "signal.open_emitter_input_without_visible_bias"
                if is_emitter
                else "signal.open_collector_input_without_visible_bias"
            )
            if is_fault
            else "none"
        )
        assert result["lint_status"] == "REVIEW"
        assert result["bias_rule_status"] == ("REVIEW" if is_fault else "PASS")
        assert result["bias_findings"] == expected_finding
        expected_rules = {"component.peer_signal_input_unconnected"}
        if is_fault:
            expected_rules.add(expected_finding)
        assert set(result["findings"].split(";")) == expected_rules
        assert result["peer_input_coverage_status"] == "EVALUATED"
        assert result["peer_input_coverage_netlist_sha256"] == result["netlist_sha256"]
        assert result["peer_input_coverage_candidate_count"] == 1
        assert result["peer_input_coverage_finding_count"] == 1
        assert result["open_output_type"] == ("open_emitter" if is_emitter else "open_collector")
        assert result["erc_errors"] == "0"
        assert set(result["erc_warning_types"].split(";")) == {
            "footprint_link_issues",
            "isolated_pin_label",
            "lib_symbol_issues",
        }
        assert result["repeatable"] == "true"
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_erc_sha256"])
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]


@pytest.mark.template_checkout
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_OPEN_DRAIN_FIXTURES") != "1",
    reason="native open-output bias fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version", "image"),
    (
        pytest.param(
            "controller",
            "10.0.0",
            "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            id="controller-kicad-10.0.0",
        ),
        pytest.param(
            "raspberry-pi-status-led",
            "10.0.5",
            "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
            id="raspberry-pi-status-led-kicad-10.0.5",
        ),
    ),
)
def test_native_exports_distinguish_bias_polarity_and_dnp_faults(
    project: str, version: str, image: str
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, open_drain_bias_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config

    repository = Path(__file__).resolve().parents[1]
    acceptance = repository / "build/ci"
    acceptance.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=f"native-open-drain-project-{project}-", dir=acceptance))
    shutil.copytree(
        reference_root(),
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    expected_hashes = {
        "collector-control": "bdb0b34256ef9bac90b7fba687abe5998400c29da2f2467cd1a43e8b1029c177",
        "collector-fault": "bb4d7075d2892bf2991a3b840ba1db956cdf6a2f6caba1538ef1381c0d937714",
        "emitter-control": "3f2bcdb733865867bef38ba1fe790518e8aa35225e04117220dcac07e53645f0",
        "emitter-fault": "b987e6f281edc13de3587614cb3bb19ed80bfeeaccde783dcf1492ef598826e1",
    }
    expected_netlist_hashes = {
        "collector-control": "bb5b9b6e92a414fd42ee6afe6318e341a6a535bd7d4e1983dc69d3c977758e34",
        "collector-fault": "6913b490585e072c7641a1800540bb4859b0009d68d4e4428ad2925417f85b20",
        "emitter-control": "4dce56e48d3b8082026f65dad1d9dd69b7466224ad617786566396aae6f74c9d",
        "emitter-fault": "6efc7bd50862e1190ebd70962b50dfbfe813f74d51aa8f88d2b7f2f3bc385588",
    }
    expected_cases = {
        "collector-control": ("none", "open_collector", "none"),
        "collector-fault": (
            "signal.open_collector_input_without_visible_bias",
            "open_collector",
            "R1",
        ),
        "emitter-control": ("none", "open_emitter", "none"),
        "emitter-fault": (
            "signal.open_emitter_input_without_visible_bias",
            "open_emitter",
            "R1",
        ),
    }
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == image
    log = HostedLog(root, f"native-open-drain-{project}")
    open_drain_bias_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("open-drain-bias-fixture/")
    }
    assert set(results) == {
        "open-drain-bias-fixture/native-export",
        *(f"open-drain-bias-fixture/{case}" for case in expected_cases),
    }
    for case, (bias_finding, output_type, dnp_resistor) in expected_cases.items():
        result = results[f"open-drain-bias-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["lint_status"] == "REVIEW"
        assert result["bias_rule_status"] == ("REVIEW" if bias_finding != "none" else "PASS")
        assert result["bias_findings"] == bias_finding
        expected_findings = {"component.peer_signal_input_unconnected"}
        if bias_finding != "none":
            expected_findings.add(bias_finding)
        assert set(result["findings"].split(";")) == expected_findings
        assert result["peer_input_coverage_status"] == "EVALUATED"
        assert result["peer_input_coverage_netlist_sha256"] == result["netlist_sha256"]
        assert result["peer_input_coverage_candidate_count"] == 1
        assert result["peer_input_coverage_finding_count"] == 1
        assert result["open_output_type"] == output_type
        assert result["input_type"] == "input"
        assert result["dnp_resistor"] == dnp_resistor
        assert result["kicad_version"] == version
        assert result["erc_errors"] == "0"
        assert set(result["erc_warning_types"].split(";")) == {
            "footprint_link_issues",
            "isolated_pin_label",
            "lib_symbol_issues",
        }
        assert result["repeatable"] == "true"
        assert result["source_sha256"] == expected_hashes[case]
        assert result["normalized_netlist_sha256"] == expected_netlist_hashes[case]
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_erc_sha256"])
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
        receipt = root / result["command_receipt"]
        assert receipt.is_file()
        command = json.loads(receipt.read_text())
        mounts = tuple(
            command["argv"][index + 1]
            for index, item in enumerate(command["argv"][:-1])
            if item == "-v"
        )
        assert len(mounts) == 2
        assert sum(item.endswith(":/fixtures:ro") for item in mounts) == 1
        assert sum(item.endswith(":/output:rw") for item in mounts) == 1
